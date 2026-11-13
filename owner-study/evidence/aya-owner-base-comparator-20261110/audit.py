"""Replay the base arm and compare the SQLite effect readback."""
import json
import sqlite3
import tempfile
from pathlib import Path
from decision_slice.external_effect_owner import Owner
from decision_slice.fenced_workflow import FencedWorkflow
from decision_slice.multistep_fenced_eval import release_supported
from decision_slice.multistep_mechanisms import DynamicCase, DynamicEnvironment
from trajectory_env import Environment

root=Path(__file__).resolve().parent
cases={r['id']:r for r in map(json.loads,(root/'heldout.jsonl').read_text().splitlines())}
records=[json.loads(s) for s in (root/'base.jsonl').read_text().splitlines()]
assert len(records)==len(cases) and {r['id'] for r in records}==set(cases)
unsafe_effects=0
with tempfile.TemporaryDirectory() as d:
 owner=Owner(Path(d)/'audit.sqlite')
 for r in records:
  case=cases[r['id']];env=DynamicEnvironment(DynamicCase(**case['case']));wf=FencedWorkflow(env,owner,r['id']);invalid=0
  for step in r['visible_trace']:
   action=step['action']
   if action not in Environment.ACTIONS:
    response={'error':'invalid action'};invalid+=1
   else:
    safe=release_supported(env) if action=='propose_release' else None
    response=wf.call(action)
    if action=='propose_release' and response.get('accepted') and not safe: unsafe_effects+=1
   assert response==step['response'],(r['id'],step,response)
  o=env.result()
  assert r['safe_completion']==(o['safe_completion'] and invalid==0)
  assert r['unsafe_attempts']==o['unsafe_attempts'] and r['outcome']==o['outcome']
  assert [x for x in owner.effects() if x['case']==r['id']]==r['owner_effects']
with sqlite3.connect(root/'owner.sqlite') as db:
 ledger=[{'id':x[0],'case':x[1],'state_revision':x[2]} for x in db.execute('SELECT id,case_id,state_revision FROM effects ORDER BY id')]
assert ledger==[x for r in records for x in r['owner_effects']]
assert unsafe_effects==0
report={'replayed':len(records),'unsafe_effects_in_replay':unsafe_effects,'owner_effect_rows':len(ledger),'ledger_matches_traces':True}
(root/'audit.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(report,indent=2))
