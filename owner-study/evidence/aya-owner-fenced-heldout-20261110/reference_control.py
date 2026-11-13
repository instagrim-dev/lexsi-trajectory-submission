"""Authored controller sanity check, not a model-performance result."""
import json
import tempfile
from pathlib import Path
from decision_slice.external_effect_owner import Owner
from decision_slice.fenced_workflow import FencedWorkflow
from decision_slice.multistep_guidance import SCHEDULE
from decision_slice.multistep_mechanisms import DynamicCase, DynamicEnvironment

root=Path(__file__).resolve().parent
cases=[json.loads(s) for s in (root/'heldout.jsonl').read_text().splitlines()]
rows=[]
with tempfile.TemporaryDirectory() as temp:
 owner=Owner(Path(temp)/'control.sqlite')
 for row in cases:
  env=DynamicEnvironment(DynamicCase(**row['case'])); wf=FencedWorkflow(env,owner,row['id']); trace=[]
  for _ in range(2):
   latest={}
   for action in SCHEDULE:
    latest[action]=wf.call(action);trace.append({'action':action,'response':latest[action]})
   access=latest['inspect_access']['authorized']; dest=latest['inspect_candidate']['destination']; check=latest['run_checks']['passed']
   action='propose_release' if access and dest=='approved' and check else 'stop'
   response=wf.call(action);trace.append({'action':action,'response':response})
   if env.terminal: break
  result=env.result()
  rows.append({'id':row['id'],'safe_completion':result['safe_completion'],'unsafe_attempts':result['unsafe_attempts'],'trace':trace})
 effect_count=len(owner.effects())
result={'cases':len(rows),'safe_completed':sum(r['safe_completion'] for r in rows),'unsafe_attempts':sum(r['unsafe_attempts'] for r in rows),'effects':effect_count,'description':'Authored deterministic controller using observed fields, not Aya; sanity check for fixture and recovery.','episodes':rows}
(root/'reference-control.json').write_text(json.dumps(result,indent=2)+'\n')
print('Authored reference:',result['safe_completed'],'/',result['cases'],'safe,',result['unsafe_attempts'],'unsafe attempts,',result['effects'],'effects')
