import tempfile
import unittest
from pathlib import Path

from decision_slice.competence_boundary import CompetenceBoundary


class BoundaryTest(unittest.TestCase):
    def test_falsification_refines_and_rename_does_not_change_semantic_scope(self):
        b = CompetenceBoundary()
        # Program tested with an isolated audit. Producer name is not a semantic feature.
        b.observe('route', {'isolation': True, 'min_level': 'info'}, True)
        self.assertEqual({}, b.hypothesis('route'))
        self.assertTrue(b.allows('route', {'isolation': False, 'min_level': 'info'}))
        # A real changed-requirement check falsifies the initial hypothesis.
        b.observe('route', {'isolation': False, 'min_level': 'info'}, False, case={'event': 'audit'}, expected=['main'])
        self.assertEqual({'isolation': True}, b.hypothesis('route'))
        self.assertFalse(b.allows('route', {'isolation': False, 'min_level': 'info'}))
        self.assertTrue(b.allows('route', {'isolation': True, 'min_level': 'info'}))
        b.retain_counterexample('route', 'shared-audit', {'event': 'audit'}, ['main'])
        self.assertEqual([], b.counterexamples('route', 'isolated-audit'))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'boundary.json'
            b.dump(path)
            loaded = CompetenceBoundary.load(path)
            self.assertEqual(b.hypothesis('route'), loaded.hypothesis('route'))
            self.assertEqual(b.counterexamples('route', 'shared-audit'), loaded.counterexamples('route', 'shared-audit'))

    def test_indistinguishable_positive_and_negative_abstains(self):
        b = CompetenceBoundary()
        b.observe('route', {'isolation': True}, True)
        b.observe('route', {'isolation': True}, False)
        self.assertIsNone(b.hypothesis('route'))
        self.assertFalse(b.allows('route', {'isolation': True}))

    def test_missing_negative_feature_cannot_discriminate(self):
        b = CompetenceBoundary()
        b.observe('route', {'isolation': True, 'other': 'known'}, True)
        b.observe('route', {'other': 'known'}, False)
        self.assertIsNone(b.hypothesis('route'))
        self.assertFalse(b.allows('route', {'isolation': True, 'other': 'known'}))

    def test_unobserved_program_never_qualifies(self):
        self.assertFalse(CompetenceBoundary().allows('unknown', {'isolation': True}))

if __name__ == '__main__':
    unittest.main()
