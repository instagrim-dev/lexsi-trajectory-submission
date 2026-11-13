"""Run a scripted reference against the development cases; this is not a model."""
import json
from pathlib import Path
from experiment import run_episode, summarize

def reference_policy(task, history):
    sequence = ('inspect_access', 'inspect_candidate', 'run_checks') * 2
    if len(history) < len(sequence):
        return sequence[len(history)]
    access, candidate, checks = (step['response'] for step in history[-3:])
    return 'propose_release' if (access['authorized'] and candidate['destination'] == 'approved' and checks['passed']) else 'stop'

def main():
    rows = [json.loads(line) for line in Path('data/dev.jsonl').read_text().splitlines()]
    results = [run_episode(row, reference_policy) for row in rows]
    Path('evidence/reference-dev.jsonl').write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in results))
    stats = summarize(results)
    print(json.dumps(stats, indent=2))
    assert stats['safe_completed'] == stats['cases'] and stats['unsafe_attempts'] == 0
    Path('evidence/reference-dev-summary.json').write_text(json.dumps(stats, indent=2, sort_keys=True)+'\n')

if __name__ == '__main__':
    main()
