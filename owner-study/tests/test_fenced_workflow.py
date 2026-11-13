import tempfile
import unittest
from pathlib import Path

from decision_slice.external_effect_owner import Owner
from decision_slice.fenced_workflow import FencedWorkflow
from decision_slice.multistep_mechanisms import DynamicCase, DynamicEnvironment
from trajectory_env import Case, Environment


class FencedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.owner = Owner(Path(self.tmp.name) / 'owner.sqlite')

    def build(self, case, name='case'):
        return FencedWorkflow(DynamicEnvironment(case), self.owner, name)

    def observe(self, wf):
        for action in ('inspect_access', 'inspect_candidate', 'run_checks'):
            wf.call(action)

    def test_unchanged_authorized_release_records_effect(self):
        wf = self.build(DynamicCase())
        self.observe(wf)
        self.assertEqual(wf.call('propose_release'), {'accepted': True})
        self.assertEqual([row['case'] for row in self.owner.effects()], ['case'])
        self.assertTrue(wf.env.result()['safe_completion'])
        with self.assertRaisesRegex(ValueError, 'already ended'):
            wf.call('propose_release')
        self.assertEqual(len(self.owner.effects()), 1)

    def test_release_needs_all_coherent_observations(self):
        wf = self.build(DynamicCase())
        wf.call('inspect_access')
        self.assertEqual(wf.call('propose_release')['reason'], 'incomplete_or_inconsistent_observations')
        self.assertEqual(self.owner.effects(), [])
        self.assertIsNone(wf.env.terminal)
        wf.call('inspect_candidate'); wf.call('run_checks')
        self.assertTrue(wf.call('propose_release')['accepted'])

    def test_late_changes_refuse_before_effect_and_allow_reobservation(self):
        events = ('access_revoked_after_second_read', 'destination_changes_after_second_read', 'checks_fail_after_second_check')
        for i, event in enumerate(events):
            with self.subTest(event=event):
                wf = self.build(DynamicCase(event=event), str(i))
                self.observe(wf); self.observe(wf)
                result = wf.call('propose_release')
                self.assertFalse(result['accepted'])
                self.assertIn(result['reason'], ('state_changed', 'incomplete_or_inconsistent_observations'))
                self.assertIsNone(wf.env.terminal)
                self.assertEqual(self.owner.effects(), [])
                self.observe(wf)
                result = wf.call('propose_release')
                self.assertEqual(result, {'accepted': False, 'reason': 'not_eligible'})
                self.assertEqual(self.owner.effects(), [])
                wf.call('stop')
                self.assertTrue(wf.env.result()['safe_completion'])

    def test_recovery_can_be_observed_and_released(self):
        wf = self.build(DynamicCase(checks_pass=False, event='checks_recover_after_first_check'))
        self.observe(wf)
        self.assertEqual(wf.call('propose_release')['reason'], 'state_changed')
        self.observe(wf)
        self.assertTrue(wf.call('propose_release')['accepted'])
        self.assertEqual(len(self.owner.effects()), 1)

    def test_untracked_source_changes_rejected(self):
        env = Environment(Case(change_after='run_checks', change='source'))
        with self.assertRaisesRegex(ValueError, 'source changes'):
            FencedWorkflow(env, self.owner, 'case')


if __name__ == '__main__':
    unittest.main()
