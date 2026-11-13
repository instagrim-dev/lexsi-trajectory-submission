import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent

def read(name):
    return json.loads((root / name).read_text())

decisions = read('rerun-decisions-final.json')['decisions']
assert [(d['revision'], d['decision']) for d in decisions] == [(1, 'Use a 7 day grace period'), (2, 'Use a 14 day grace period')]
for number, state in ((1, 'accepted'), (2, 'applied')):
    proposal = read(f'rerun-proposal-{number}-final.json')
    assert proposal['proposal']['status'] == state
    selected = next(e for e in proposal['events'] if e['event_type'] == 'change_synthesis_selected')
    assert any(d['id'] == 'invoice-grace' and d['revision'] == number for d in selected['metadata']['intent_support']['decisions'])
    assert read(f'rerun-validation-{number}.json')['readiness']['state'] == 'passed'
assert (root / 'source-before-revision.sha256').read_text() == (root / 'rerun-stale-source.sha256').read_text()
http = read('application-http-observations.json')
assert any(x['request_id'] == 'f6cdfe62-e7c2-47cc-a0dc-50630da03dc1' and x['status'] == 409 for x in http)
assert any(x['request_id'] == 'e0c4b826-9f72-46b0-9e5e-a8dea8136d13' and x['status'] == 200 for x in http)
calls = [json.loads(line) for line in (root / 'live-model-calls.jsonl').read_text().splitlines()]
assert len(calls) >= 4
for call, value in zip(calls[-2:], (7, 14)):
    candidate = json.loads(call['candidate'])
    assert candidate == {'grace_days': value, 'tenant_guard': True, 'unpaid_only': True, 'audit': True}
    assert all(call['d1_output']['answers'][k]['choice'] == 'yes' for k in ('tenant_guard', 'eligible_only', 'audit'))
assert read('workspace/policy.json') == json.loads(calls[-1]['candidate'])
assert read('rerun-independent-check.json')['passed'] is True
files = ['live-model-calls.jsonl', 'rerun-decisions-final.json', 'rerun-proposal-1-final.json', 'rerun-proposal-2-final.json', 'rerun-validation-1.json', 'rerun-validation-2.json', 'application-http-observations.json', 'rerun-independent-check.json', 'workspace/policy.json']
(root / 'audit.json').write_text(json.dumps({'passed': True, 'sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}}, indent=2) + '\n')
print('Native revision evidence audit passed')
