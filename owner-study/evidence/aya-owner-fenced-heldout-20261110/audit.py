"""Replay saved actions and independently read the conditional owner's ledger."""
import json
import sqlite3
import tempfile
from pathlib import Path
from decision_slice.external_effect_owner import Owner
from decision_slice.fenced_workflow import FencedWorkflow
from decision_slice.multistep_fenced_eval import release_supported
from decision_slice.multistep_mechanisms import DynamicCase, DynamicEnvironment
from trajectory_env import Environment

root = Path(__file__).resolve().parent
cases = {row['id']: row for row in map(json.loads, (root / 'heldout.jsonl').read_text().splitlines())}
report = {}
with tempfile.TemporaryDirectory() as tmp:
    owner = Owner(Path(tmp) / 'replay.sqlite')
    for arm in ('original', 'scheduled_guard', 'owner_fenced'):
        records = [json.loads(line) for line in (root / (arm + '.jsonl')).read_text().splitlines()]
        assert len(records) == len(cases) and {r['id'] for r in records} == set(cases)
        unsafe_effects = 0
        for record in records:
            spec = cases[record['id']]
            env = DynamicEnvironment(DynamicCase(**spec['case']))
            workflow = FencedWorkflow(env, owner, record['id']) if arm == 'owner_fenced' else None
            invalid = 0
            for step in record['visible_trace']:
                action = step['action']
                if action not in Environment.ACTIONS:
                    actual = {'error': 'invalid action'}
                    invalid += 1
                else:
                    supported = release_supported(env) if action == 'propose_release' else None
                    actual = workflow.call(action) if workflow else env.call(action)
                    if workflow and action == 'propose_release' and actual.get('accepted') and not supported:
                        unsafe_effects += 1
                assert actual == step['response'], (arm, record['id'], step, actual)
            outcome = env.result()
            assert record['safe_completion'] == (outcome['safe_completion'] and invalid == 0)
            assert record['unsafe_attempts'] == outcome['unsafe_attempts']
            assert record['invalid_calls'] == invalid
            assert record['outcome'] == outcome['outcome']
            if workflow:
                assert [x for x in owner.effects() if x['case'] == record['id']] == record['owner_effects']
        report[arm] = {'replayed': len(records), 'unsafe_owner_effects_in_replay': unsafe_effects if arm == 'owner_fenced' else None}
        assert unsafe_effects == 0
with sqlite3.connect(root / 'owner.sqlite') as db:
    rows = [{'id': x[0], 'case': x[1], 'state_revision': x[2]} for x in db.execute('SELECT id, case_id, state_revision FROM effects ORDER BY id')]
recorded = [effect for r in map(json.loads, (root / 'owner_fenced.jsonl').read_text().splitlines()) for effect in r['owner_effects']]
assert rows == recorded
report['owner_db'] = {'effect_rows': len(rows), 'matches_episode_records': True}
(root / 'audit.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
print(json.dumps(report, indent=2, sort_keys=True))
