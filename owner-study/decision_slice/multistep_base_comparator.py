"""Run base Tiny Aya through the frozen conditional-owner workflow."""
import argparse
import hashlib
import json
import platform
import time
from pathlib import Path
from decision_slice.external_effect_owner import Owner
from decision_slice.fenced_workflow import FencedWorkflow
from decision_slice.multistep_fenced_eval import release_supported
from decision_slice.multistep_guidance import SCHEDULE, terminal_messages
from decision_slice.multistep_guidance_v2 import guard_terminal
from decision_slice.multistep_mechanisms import DynamicCase, DynamicEnvironment
from experiment import summarize
from model_runner import parse_action


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(); p.add_argument('--out', required=True); p.add_argument('--model', required=True); a = p.parse_args()
    out = Path(a.out); plan = json.loads((out / 'plan.json').read_text())
    if sha(out / 'heldout.jsonl') != plan['cases_sha256']:
        raise ValueError('frozen cases changed')
    for filename, expected in plan['source_sha256'].items():
        if sha(filename) != expected:
            raise ValueError('frozen source changed: ' + filename)
    import torch, transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.model, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(a.model, local_files_only=True, torch_dtype='auto')
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    model.to(device).eval()
    owner = Owner(out / 'owner.sqlite')
    rows = [json.loads(s) for s in (out / 'heldout.jsonl').read_text().splitlines() if s]
    results = []
    with (out / 'base.jsonl').open('x') as f:
        for row in rows:
            env = DynamicEnvironment(DynamicCase(**row['case']))
            workflow = FencedWorkflow(env, owner, row['id'])
            history, outputs, interventions = [], [], []
            scheduled = invalid = model_proposals = unsupported = requests = refusals = 0
            start = time.monotonic()
            for _ in range(plan['max_steps']):
                if scheduled < len(SCHEDULE):
                    action = SCHEDULE[scheduled]; scheduled += 1
                else:
                    x = tok.apply_chat_template(terminal_messages(row['prompt'], history), tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors='pt').to(device)
                    with torch.inference_mode():
                        y = model.generate(**x, do_sample=False, max_new_tokens=plan['max_new_tokens'], pad_token_id=tok.eos_token_id)
                    raw = tok.decode(y[0][x['input_ids'].shape[-1]:], skip_special_tokens=True).strip()
                    outputs.append(raw); proposed = parse_action(raw)
                    if proposed == 'propose_release':
                        model_proposals += 1; unsupported += int(not release_supported(env))
                    if proposed not in ('stop', 'request_fresh_consent', 'propose_release'):
                        invalid += 1; history.append({'action': raw, 'response': {'error': 'invalid action'}}); continue
                    action, changed = guard_terminal(proposed, history)
                    if changed: interventions.append({'proposed': proposed, 'executed': action})
                if action == 'propose_release': requests += 1
                response = workflow.call(action)
                if action == 'propose_release' and not response.get('accepted'):
                    refusals += 1; scheduled = 0
                history.append({'action': action, 'response': response})
                if env.terminal: break
            outcome = env.result()
            result = {'id': row['id'], 'scenario': row['scenario'], 'safe_completion': outcome['safe_completion'] and invalid == 0,
                      'unsafe_attempts': outcome['unsafe_attempts'], 'invalid_calls': invalid, 'authorized_case': outcome['authorized_case'],
                      'outcome': outcome['outcome'], 'visible_trace': history, 'raw_model_outputs': outputs, 'model_calls': len(outputs),
                      'model_release_proposals': model_proposals, 'unsupported_model_release_proposals': unsupported,
                      'guard_interventions': interventions, 'owner_requests': requests, 'owner_refusals': refusals,
                      'owner_effects': [e for e in owner.effects() if e['case'] == row['id']], 'owner_events': workflow.events,
                      'elapsed_seconds': round(time.monotonic()-start, 3)}
            f.write(json.dumps(result, sort_keys=True)+'\n'); f.flush(); results.append(result)
            print(row['id'], 'safe=', result['safe_completion'], 'unsafe=', result['unsafe_attempts'], flush=True)
    summary = summarize(results)
    for name in ('model_calls','model_release_proposals','unsupported_model_release_proposals','owner_requests','owner_refusals'):
        summary[name] = sum(r[name] for r in results)
    summary['guard_interventions'] = sum(len(r['guard_interventions']) for r in results)
    summary['owner_effects'] = sum(len(r['owner_effects']) for r in results)
    summary['total_steps'] = sum(len(r['visible_trace']) for r in results)
    summary['elapsed_seconds'] = round(sum(r['elapsed_seconds'] for r in results),3)
    (out / 'base-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    (out / 'runtime.json').write_text(json.dumps({'model':a.model,'adapter_loaded':False,'device':device,'python':platform.python_version(),
         'torch':str(torch.__version__),'transformers':transformers.__version__,'plan_sha256':sha(out/'plan.json')},indent=2,sort_keys=True)+'\n')


if __name__ == '__main__': main()
