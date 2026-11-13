"""Validate paired evaluation bindings and compare per-episode results."""
import argparse,json
from pathlib import Path

def compare(before,after):
    a={r['id']:r for r in before};b={r['id']:r for r in after}
    if not a or len(a)!=len(before) or len(b)!=len(after) or a.keys()!=b.keys():raise ValueError('pair IDs differ or repeat')
    def metrics(rows):
        return {'safe_completed':sum(bool(x['safe_completion']) for x in rows),'unsafe_attempt_cases':sum(x['unsafe_attempts']>0 for x in rows),
                'unsafe_attempts':sum(x['unsafe_attempts'] for x in rows),'invalid_calls':sum(x['invalid_calls'] for x in rows),
                'total_steps':sum(len(x['visible_trace']) for x in rows)}
    improved=[i for i in a if not a[i]['safe_completion'] and b[i]['safe_completion']]
    regressed=[i for i in a if a[i]['safe_completion'] and not b[i]['safe_completion']]
    return {'cases':len(a),'before':metrics(before),'after':metrics(after),'improved_cases':improved,'regressed_cases':regressed}

def main():
    p=argparse.ArgumentParser();p.add_argument('--before',required=True);p.add_argument('--after',required=True);p.add_argument('--train-meta',required=True);p.add_argument('--plan',required=True);p.add_argument('--out',required=True);args=p.parse_args()
    before=Path(args.before);after=Path(args.after);sa=json.loads((before/'summary.json').read_text());sb=json.loads((after/'summary.json').read_text())
    keys=('model','revision_claim','heldout_sha256','plan_sha256','system_prompt_sha256','decoding','max_new_tokens','max_episode_steps','device','python','torch','transformers')
    if any(sa.get(k)!=sb.get(k) for k in keys) or sa.get('adapter') is not None or not sb.get('adapter_sha256'):raise ValueError('paired model or evaluation bindings differ')
    train=json.loads(Path(args.train_meta).read_text());plan=json.loads(Path(args.plan).read_text())
    if train['training_steps_sha256']!=plan['train_steps_sha256'] or train['system_prompt_sha256']!=plan['system_prompt_sha256'] or train['optimizer_steps']!=plan['training_optimizer_steps']:raise ValueError('training differs from frozen plan')
    load=lambda d:[json.loads(x) for x in (d/'results.jsonl').read_text().splitlines() if x.strip()]
    value=compare(load(before),load(after));value['scope']='Paired frozen episodes; same synthetic mechanisms as training.'
    with Path(args.out).open('x') as f:json.dump(value,f,indent=2);f.write('\n')
    print(json.dumps(value,indent=2))
if __name__=='__main__':main()
