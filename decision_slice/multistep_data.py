"""Freeze stratified scripted training traces and separate held-out episodes."""
import hashlib,json
from pathlib import Path
from experiment import SCENARIOS,run_episode
from model_runner import build_messages
from reference_run import reference_policy

ROOT=Path(__file__).resolve().parent.parent

def make_splits():
    def load(name,n):
        rows=[json.loads(line) for line in (ROOT/'data'/f'{name}.jsonl').read_text().splitlines() if line.strip()]
        return [r for scenario in sorted(SCENARIOS) for r in sorted((x for x in rows if x['scenario']==scenario),key=lambda x:x['id'])[:n]]
    return load('train',4),load('test',3)

def make_demonstrations(train):
    examples=[]
    for case in train:
        episode=run_episode(case,reference_policy)
        if not episode['safe_completion']:raise ValueError('scripted reference failed')
        history=[]
        for step in episode['visible_trace']:
            examples.append({'case_id':case['id'],'task':case['prompt'],'history':list(history),
                 'messages':build_messages(case['prompt'],history),'action':step['action'],
                 'provenance':'scripted_reference_in_synthetic_environment'})
            history.append(step)
    return examples

def main():
    train,heldout=make_splits();demos=make_demonstrations(train)
    if {r['id'] for r in train}&{r['id'] for r in heldout}:raise ValueError('split overlap')
    out=ROOT/'data'/'multistep-v1';out.mkdir(parents=True,exist_ok=False)
    manifest={'schema':'trajectory.multistep-data/v1','selection':'first sorted IDs per scenario: 4 train, 3 test',
      'scope':'different wording, same six underlying simulator mechanisms; not unseen-mechanism generalization',
      'teacher':'deterministic scripted reference, not model-generated', 'files':{}}
    for name,rows in [('train-cases',train),('train-steps',demos),('heldout',heldout)]:
        data=''.join(json.dumps(x,sort_keys=True,ensure_ascii=False)+'\n' for x in rows).encode()
        (out/f'{name}.jsonl').write_bytes(data);manifest['files'][name]={'rows':len(rows),'sha256':hashlib.sha256(data).hexdigest()}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
