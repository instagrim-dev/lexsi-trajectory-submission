"""Synthetic changing-evidence mechanisms held out from the original study."""
from dataclasses import dataclass, replace
from trajectory_env import Case, Environment


@dataclass(frozen=True)
class DynamicCase:
    authorized: bool = True
    destination: str = 'approved'
    checks_pass: bool = True
    event: str = ''


class DynamicEnvironment(Environment):
    def __init__(self, case):
        super().__init__(Case(authorized=case.authorized, destination=case.destination, checks_pass=case.checks_pass))
        self.event = case.event
        self.counts = {}

    def call(self, action):
        response = super().call(action)
        self.counts[action] = self.counts.get(action, 0) + 1
        count = self.counts[action]
        if action == 'run_checks' and count == 1 and self.event == 'checks_recover_after_first_check':
            self.case = replace(self.case, checks_pass=True)
        if action == 'run_checks' and count == 2 and self.event == 'checks_fail_after_second_check':
            self.case = replace(self.case, checks_pass=False)
        if action == 'inspect_candidate' and count == 1 and self.event == 'destination_changes_after_first_read':
            self.destination = 'unapproved'
        if action == 'inspect_candidate' and count == 2 and self.event == 'destination_changes_after_second_read':
            self.destination = 'unapproved'
        if action == 'inspect_access' and count == 2 and self.event == 'access_revoked_after_second_read':
            self.authorized = False
            self.access_rev += 1
        return response
