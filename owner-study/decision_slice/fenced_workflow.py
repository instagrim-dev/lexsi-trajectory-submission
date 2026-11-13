"""Connect synthetic tool observations to the existing conditional-effect owner.

The owner fences only access, destination and checks. This adapter is for the
DynamicEnvironment's changes to those three fields; it does not fence source
revision or demonstrate a real export.
"""
from trajectory_env import Environment


class FencedWorkflow:
    """Deliver tool actions while retaining the last coherent owner snapshot."""

    INSPECTIONS = frozenset(('inspect_access', 'inspect_candidate', 'run_checks'))

    def __init__(self, env, owner, case_id):
        if getattr(env.case, 'change', None) == 'source':
            raise ValueError('the owner does not fence source changes')
        self.env = env
        self.owner = owner
        self.case_id = case_id
        self.events = []
        self.latest = {}
        self.snapshot = None
        self._sync_owner()

    def _state(self):
        # This is the simulator-to-owner boundary, never a model observation.
        return {'access': bool(self.env.authorized),
                'destination': self.env.destination,
                'checks': bool(self.env.case.checks_pass)}

    def _sync_owner(self):
        state = self._state()
        current = self.owner.observe(self.case_id)
        for field, value in state.items():
            if current[field] != value:
                current = self.owner.change(self.case_id, field, value)
        return current

    def _coherent(self, snapshot):
        if not self.INSPECTIONS.issubset(self.latest):
            return False
        access = self.latest['inspect_access']
        candidate = self.latest['inspect_candidate']
        checks = self.latest['run_checks']
        return (access.get('authorized') is bool(snapshot['access'])
                and candidate.get('destination') == snapshot['destination']
                and checks.get('passed') is bool(snapshot['checks'])
                and isinstance(candidate.get('source_revision'), int)
                and candidate.get('source_revision') == checks.get('source_revision'))

    def call(self, action):
        if self.env.terminal:
            raise ValueError('episode already ended')
        if action not in Environment.ACTIONS:
            raise ValueError('unknown action: ' + str(action))
        if action in self.INSPECTIONS:
            # Capture before the observation: the simulator may change immediately
            # after returning that observation, which must invalidate this token.
            before = self.owner.observe(self.case_id)
            response = self.env.call(action)
            self.latest[action] = response.copy()
            self.snapshot = before if self._coherent(before) else None
            after = self._sync_owner()
            self.events.append({'action': action, 'response': response.copy(),
                                'owner_before': before, 'owner_after': after,
                                'coherent_snapshot': self.snapshot})
            return response
        if action != 'propose_release':
            response = self.env.call(action)
            self._sync_owner()
            self.events.append({'action': action, 'response': response.copy()})
            return response
        if self.snapshot is None:
            response = {'accepted': False, 'reason': 'incomplete_or_inconsistent_observations'}
            self.events.append({'action': action, 'response': response.copy()})
            return response
        result = self.owner.release(self.case_id, self.snapshot)
        if not result['applied']:
            response = {'accepted': False, 'reason': result['reason']}
            self.snapshot = None
        else:
            response = self.env.call(action)
            if not response.get('accepted'):
                raise RuntimeError('owner effect and simulator outcome disagree')
        self.events.append({'action': action, 'response': response.copy(),
                            'owner_result': result})
        return response
