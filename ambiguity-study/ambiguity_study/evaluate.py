"""Matched Tiny Aya study with common free-form clarification and probing tools.

Hidden task intent is never shown before an understandable question. Candidate
qualification before clarification accepts either legitimate interpretation;
the hidden independent acceptance is scored only after a candidate is submitted.
"""
from __future__ import annotations
import argparse, hashlib, json, time
from pathlib import Path
from typing import Any
from ambiguity_study import benchmark
from ambiguity_study.model import TinyAya, AdaptionPolicy, write_event
from ambiguity_study.prompt import SYSTEM
from ambiguity_study.train_data import FAMILIES as TRAIN_FAMILIES

MAX_TURNS = 4
MAX_QUESTIONS = 2
MAX_NEW_TOKENS = 384


def modes(family: str) -> tuple[str, str]:
    return ('line', 'subtotal') if family == 'finance' else ('earliest', 'latest')


def qualify(task: dict, code: Any, known: bool) -> dict:
    """Evaluate only information the task or operator has made available."""
    inputs = benchmark.cases(task['family'], 'plausibility')
    result = benchmark.execute(task['family'], code, inputs)
    values = result.get('values', [])
    valid_modes = [m for m in modes(task['family']) if values == [benchmark.expected(task['family'], m, x) for x in inputs]]
    permitted = [task['mode']] if known or not task['ambiguous'] else list(modes(task['family']))
    passed = result['status'] == 'ok' and any(x in valid_modes for x in permitted)
    # The returned evidence reports candidate behavior and all publicly possible
    # outputs, not the hidden selection. A clarified/explicit task may expose its
    # specified expected behavior.
    allowed = {m: [benchmark.expected(task['family'], m, x) for x in inputs] for m in permitted}
    return {**result, 'passed': passed, 'inputs': inputs, 'allowed': allowed}


def _witness(task: dict, response: dict) -> dict | None:
    if not all(k in response for k in ('left_code', 'right_code', 'witness')):
        return None
    if not isinstance(response['witness'], dict):
        return {'valid': False, 'reason': 'invalid_witness', 'workers': 0, 'seconds': 0}
    return benchmark.validate_witness(task, response['left_code'], response['right_code'], response['witness'])


def _witness_feedback(witness: dict | None) -> str:
    if witness is None:
        return 'No two candidate functions and input were supplied.'
    if not witness['valid']:
        return 'The supplied candidate functions and input did not establish a valid divergent interpretation: '+witness['reason']+'.'
    left=witness['left']['values'][-1]
    right=witness['right']['values'][-1]
    return f'The candidate functions produce {left} and {right} on the submitted input, and both fit a plausible interpretation. The correct interpretation is not determined.'


def run_task(task: dict, arm: str, model: Any, events: Path) -> dict:
    started = time.monotonic()
    messages = [{'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': json.dumps(benchmark.public_view(task), sort_keys=True)}]
    known = not task['ambiguous']
    latest_witness = False
    questions = useful_questions = unnecessary_questions = invalid_questions = 0
    witness_attempts = valid_witnesses = checks = check_failures = workers = 0
    checker_s = 0.0
    model_starts = input_tokens = output_tokens = invalid_outputs = 0
    unknown_token_calls = 0
    wrong_commits = 0
    outcome = 'turn_budget_exhausted'
    accepted = False
    for turn in range(1, MAX_TURNS + 1):
        result = model.infer(messages, arm=arm, task=task['id'], turn=turn)
        model_starts += 1
        if result.get('input_tokens') is None or result.get('output_tokens') is None:
            unknown_token_calls += 1
        else:
            input_tokens += result['input_tokens']; output_tokens += result['output_tokens']
        response = result.get('parsed')
        if result.get('error') or not isinstance(response, dict):
            invalid_outputs += 1
            messages += [{'role':'assistant','content':result.get('raw', '')},
                         {'role':'user','content':'Invalid response. Return one JSON action as instructed.'}]
            continue
        messages.append({'role':'assistant','content':json.dumps(response, ensure_ascii=False)})
        action = response.get('action')
        if action in ('probe', 'ask'):
            witness = _witness(task, response)
            if witness is not None:
                witness_attempts += 1; workers += witness['workers']; checker_s += witness['seconds']
                checks += 1; check_failures += not witness['valid']
                latest_witness = witness['valid']
                if witness['valid']: valid_witnesses += 1
                write_event(events, {'arm':arm,'task':task['id'],'turn':turn,'stage':'witness','result':witness,
                    'training_witness_repeated': any(response.get('witness') == f[6] for f in TRAIN_FAMILIES),
                    'training_code_repeated': any(response.get(k) in (f[4],f[5]) for f in TRAIN_FAMILIES for k in ('left_code','right_code'))})
            if action == 'probe':
                messages.append({'role':'user','content':'Probe result: '+_witness_feedback(witness)})
                continue
            question = response.get('question')
            questions += 1
            if questions > MAX_QUESTIONS:
                outcome = 'question_budget_exhausted'; break
            answer = benchmark.user_answer(task, question) if isinstance(question,str) else None
            if answer is None:
                invalid_questions += 1
                messages.append({'role':'user','content':'I could not identify which rule your question asks about. Please ask more specifically or solve.'})
            else:
                if task['ambiguous'] and not known: useful_questions += 1
                else: unnecessary_questions += 1
                known = True
                messages.append({'role':'user','content':'Operator answer: '+answer})
            write_event(events, {'arm':arm,'task':task['id'],'turn':turn,'stage':'question',
                                 'understood':answer is not None,'necessary':task['ambiguous'],
                                 'witness_linked':bool(latest_witness),'question':question})
            continue
        if action == 'solve':
            code=response.get('code')
            q=qualify(task,code,known)
            workers += q['workers']; checker_s += q['seconds']; checks += 1; check_failures += not q['passed']
            write_event(events, {'arm':arm,'task':task['id'],'turn':turn,'stage':'qualification','result':q})
            if not q['passed']:
                feedback={'status':q['status'],'values':q.get('values',[]),'inputs':q['inputs'],
                          'compiler_output':q.get('output','')[-2000:]}
                if known: feedback['required_outputs'] = q['allowed']
                messages.append({'role':'user','content':'Qualification failed: '+json.dumps(feedback)})
                continue
            final=benchmark.evaluate_code(task,code)
            workers += final['workers']; checker_s += final['seconds']; checks += 1; check_failures += not final['passed']
            write_event(events, {'arm':arm,'task':task['id'],'turn':turn,'stage':'independent_acceptance','result':final})
            accepted=bool(final['passed'])
            if accepted:
                outcome='accepted'
            elif final['status']=='ok':
                outcome='wrong_submitted_repair';wrong_commits += 1
            else:
                outcome='acceptance_worker_failure'
            break
        invalid_outputs += 1
        messages.append({'role':'user','content':'Invalid action. Return a valid JSON action.'})
    return {'arm':arm,'task':task['id'],'family':task['family'],'hidden_mode':task['mode'],
            'ambiguous':task['ambiguous'],'accepted':accepted,'outcome':outcome,'wrong_submitted_repairs':wrong_commits,
            'questions':questions,'useful_questions':useful_questions,'unnecessary_questions':unnecessary_questions,
            'invalid_questions':invalid_questions,'witness_attempts':witness_attempts,'valid_witnesses':valid_witnesses,
            'checks':checks,'check_failures':check_failures,'go_workers':workers,'checker_s':checker_s,
            'model_starts':model_starts,'input_tokens':input_tokens,'output_tokens':output_tokens,
            'unknown_token_calls':unknown_token_calls,'invalid_outputs':invalid_outputs,'elapsed_s':time.monotonic()-started}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True); parser.add_argument('--adapter'); parser.add_argument('--arm',required=True,choices=['generic','trained','generic-adaption'])
    parser.add_argument('--out',required=True); parser.add_argument('--limit',type=int); args=parser.parse_args()
    root=Path(args.out); root.mkdir(parents=True, exist_ok=True)
    journal=root/f'{args.arm}-model.jsonl'; events=root/f'{args.arm}-checks.jsonl'; rows=root/f'{args.arm}-assignments.jsonl'
    for p in (journal,events,rows):
        if p.exists(): raise SystemExit(f'will not overwrite {p}')
    tasks=benchmark.tasks('eval')
    if args.limit is not None: tasks=tasks[:args.limit]
    (root/f'{args.arm}-plan.json').write_text(json.dumps({'arm':args.arm,'tasks':[x['id'] for x in tasks],
        'system_sha256':hashlib.sha256(SYSTEM.encode()).hexdigest(),'turn_budget':MAX_TURNS,'question_budget':MAX_QUESTIONS,
        'max_new_tokens':MAX_NEW_TOKENS,'device_contract':'local Tiny Aya; MPS if available',
        'baseline':'same model, prompt, tools, budgets, free questions, executable probes, and feedback; adapter differs'}, indent=2)+'\n')
    total_start=time.monotonic()
    model=AdaptionPolicy(args.model,journal,MAX_NEW_TOKENS) if args.arm=='generic-adaption' else TinyAya(args.model,args.adapter,journal,MAX_NEW_TOKENS)
    for task in tasks:
        row=run_task(task,args.arm,model,events);write_event(rows,row)
        print(args.arm,task['id'],row['outcome'],'questions',row['questions'],'witnesses',row['valid_witnesses'],flush=True)
    (root/f'{args.arm}-wall.json').write_text(json.dumps({'elapsed_s':time.monotonic()-total_start,'model_initialization_s':model.initialization_seconds})+'\n')

if __name__ == '__main__': main()
