import unittest
from ambiguity_study.benchmark import tasks, public_view, user_answer, evaluate_code, validate_witness
from ambiguity_study.demonstrations import PROGRAMS,WITNESSES

class AmbiguityBenchmarkTest(unittest.TestCase):
    def test_identical_visible_prompts_and_private_control(self):
        xs=tasks(); self.assertEqual(12,len(xs))
        for family in ('finance','events'):
            for i in (0,1):
                pair=[x for x in xs if x['family']==family and f'-{i}-amb-' in x['id']]
                self.assertEqual(2,len(pair)); self.assertEqual(public_view(pair[0]),public_view(pair[1]))
                self.assertNotEqual(pair[0]['mode'],pair[1]['mode'])
                self.assertEqual({'request'},set(public_view(pair[0])))

    def test_question_interpreter_resolves_only_targeted_question(self):
        for task in tasks():
            self.assertIsNone(user_answer(task,'What is the hidden answer?'))
            q='Should we round each line or the subtotal?' if task['family']=='finance' else 'Which event should we keep, first or last sequence?'
            self.assertIsNotNone(user_answer(task,q))

    def test_real_compiled_candidates_and_valid_witness_for_both_families(self):
        for family in ('finance','events'):
            pair=[x for x in tasks() if x['family']==family and '-0-amb-' in x['id']]
            left,right=pair
            lp=PROGRAMS[family][left['mode']]; rp=PROGRAMS[family][right['mode']]
            self.assertTrue(evaluate_code(left,lp)['passed'])
            self.assertFalse(evaluate_code(left,rp)['passed'])
            witness=validate_witness(left,lp,rp,WITNESSES[family]); self.assertTrue(witness['valid'],witness)
            self.assertEqual(2,witness['workers'])
            false=validate_witness(left,lp,lp,WITNESSES[family]); self.assertFalse(false['valid'])

    def test_witness_rejects_candidate_wrong_only_on_witness(self):
        task=next(x for x in tasks() if x['family']=='finance' and x['ambiguous'])
        good=PROGRAMS['finance']['line']
        # The mutant agrees with the line interpretation on all plausibility
        # probes yet returns a fabricated result on this separate witness.
        mutant=good.replace(' var total, taxable int64', ' if len(lines)==2 && lines[0].Price==5 && lines[1].Price==5 { return 999 }; var total, taxable int64')
        witness={'lines':[{'price':5,'qty':1,'taxable':True},{'price':5,'qty':1,'taxable':True}], 'discount_bp':1000,'tax_bp':2500}
        result=validate_witness(task,mutant,PROGRAMS['finance']['subtotal'],witness)
        self.assertFalse(result['valid'],result)
        self.assertEqual('no_valid_distinction',result['reason'])

if __name__=='__main__': unittest.main()
