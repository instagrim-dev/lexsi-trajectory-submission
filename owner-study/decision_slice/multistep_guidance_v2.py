"""Correct consent requests when observed facts make consent insufficient."""
from decision_slice.multistep_guidance import guard_terminal as original_guard


def guard_terminal(action, history):
    if action == 'request_fresh_consent':
        latest = {}
        for step in history:
            if step['action'] in ('inspect_access', 'inspect_candidate', 'run_checks'):
                latest[step['action']] = step['response']
        access = latest.get('inspect_access', {})
        candidate = latest.get('inspect_candidate', {})
        checks = latest.get('run_checks', {})
        if (access.get('authorized') is True or
                candidate.get('destination') == 'unapproved' or
                checks.get('passed') is False):
            return 'stop', True
    return original_guard(action, history)
