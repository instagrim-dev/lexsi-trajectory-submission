"""Loopback-only controlled effect owner for an external-service experiment."""
import argparse
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


class Owner:
    def __init__(self, database):
        self.database = str(database)
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS state(case_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, access INTEGER NOT NULL, destination TEXT NOT NULL, checks INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS effects(id INTEGER PRIMARY KEY, case_id TEXT NOT NULL, state_revision INTEGER NOT NULL);''')

    def connect(self):
        conn = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def ensure(db, case):
        db.execute('INSERT OR IGNORE INTO state VALUES (?,1,1,?,1)', (case, 'approved'))

    def observe(self, case):
        with self.connect() as db:
            self.ensure(db, case)
            row = db.execute('SELECT revision, access, destination, checks FROM state WHERE case_id=?', (case,)).fetchone()
            return dict(row)

    def change(self, case, field, value):
        if field not in ('access', 'destination', 'checks'):
            raise ValueError('unsupported state field')
        if field in ('access', 'checks') and not isinstance(value, bool):
            raise ValueError('expected boolean')
        if field == 'destination' and value not in ('approved', 'unapproved'):
            raise ValueError('unsupported destination')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.ensure(db, case)
            db.execute('UPDATE state SET ' + field + '=?, revision=revision+1 WHERE case_id=?', (value, case))
            db.execute('COMMIT')
        return self.observe(case)

    def release(self, case, observed):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.ensure(db, case)
            current = dict(db.execute('SELECT revision, access, destination, checks FROM state WHERE case_id=?', (case,)).fetchone())
            if current != observed:
                db.execute('COMMIT')
                return {'applied': False, 'reason': 'state_changed', 'current': current}
            if not current['access'] or current['destination'] != 'approved' or not current['checks']:
                db.execute('COMMIT')
                return {'applied': False, 'reason': 'not_eligible', 'current': current}
            cursor = db.execute('INSERT INTO effects(case_id,state_revision) VALUES (?,?)', (case, current['revision']))
            db.execute('COMMIT')
            return {'applied': True, 'effect_id': cursor.lastrowid, 'current': current}

    def effects(self):
        with self.connect() as db:
            return [{'id': r['id'], 'case': r['case_id'], 'state_revision': r['state_revision']} for r in db.execute('SELECT * FROM effects ORDER BY id')]


def main():
    p = argparse.ArgumentParser(); p.add_argument('--database', required=True); a = p.parse_args()
    owner = Owner(a.database)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def respond(self, value, status=200):
            data = json.dumps(value).encode(); self.send_response(status)
            self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
        def do_GET(self):
            url = urlparse(self.path)
            if url.path == '/observe': self.respond(owner.observe(parse_qs(url.query)['case'][0]))
            elif url.path == '/effects': self.respond(owner.effects())
            else: self.respond({'error': 'not found'}, 404)
        def do_POST(self):
            try:
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path == '/change': self.respond(owner.change(body['case'], body['field'], body['value']))
                elif self.path == '/release': self.respond(owner.release(body['case'], body['observed']))
                else: self.respond({'error': 'not found'}, 404)
            except (KeyError, ValueError, json.JSONDecodeError) as error:
                self.respond({'error': str(error)}, 400)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    print(server.server_address[1], flush=True)
    server.serve_forever()


if __name__ == '__main__': main()
