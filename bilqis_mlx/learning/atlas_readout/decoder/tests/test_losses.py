"""Loss only uses executed legal decisions and supplied labels."""
from dataclasses import replace
import unittest
import numpy as np
import mlx.core as mx
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_readout import DecisionOutput, DecisionKind, DecodeStatus, predict_typed
from bilqis_mlx.learning.atlas_readout.decoder.prediction import ModelOutput, DecisionLogits, ExecutionMode
from bilqis_mlx.learning.atlas_readout.decoder.losses import answer_loss
from bilqis_mlx.learning.atlas_readout.decoder.tests.helpers import case


class TypedLossTests(unittest.TestCase):
    def test_primary_kind_means_and_absent_auxiliary_zero(self):
        fixture=case()
        plan=fixture[2]
        output=predict_typed(*fixture)
        spec=plan.decisions[1]
        target=DecisionOutput('value',spec.legal_values[0])
        actual=answer_loss(output,(target,),{'value':True})
        logits=np.asarray(next(d.logits for d in output.decisions if d.decision_id=='value'))
        expected=float(np.log(np.exp(logits-logits.max()).sum())+logits.max()-logits[0])
        self.assertAlmostEqual(float(actual.primary),expected,places=6)
        self.assertEqual(float(actual.role),0)
        self.assertEqual(float(actual.epistemic),0)
        self.assertEqual(float(actual.total),float(actual.primary))
        self.assertEqual(float(answer_loss(output,(),{'value':True}).total),0)
        self.assertEqual(float(answer_loss(output,(target,),{'value':False}).total),0)

    def test_masked_label_keeps_exact_zero_gradient(self):
        memory,context,plan,semantics,params=case()
        values=plan.decisions[1].legal_values
        def objective(query):
            changed={**params,'readout.query':query}
            output=predict_typed(memory,context,plan,semantics,changed)
            return answer_loss(output,(DecisionOutput('value',values[0]),),{'value':False}).total
        np.testing.assert_array_equal(np.asarray(mx.grad(objective)(params['readout.query'])),0)

    def test_replaced_or_caller_minted_logits_cannot_enter_supervision(self):
        output=predict_typed(*case())
        record=output.decisions[1]
        substituted=replace(output,decisions=(output.decisions[0],
            DecisionLogits(record.decision_id,record.kind,record.candidates,
                           mx.array([1.,2.],dtype=mx.float32)),*output.decisions[2:]))
        target=(DecisionOutput(record.decision_id,record.candidates[0]),)
        with self.assertRaises(BilqisError):
            answer_loss(substituted,target,{record.decision_id:True})
        with self.assertRaises(BilqisError):
            answer_loss(replace(output),target,{record.decision_id:True})
        self.assertTrue(bool(mx.isfinite(answer_loss(output,target,{record.decision_id:True}).total)))
        object.__setattr__(output, 'decisions', substituted.decisions)
        with self.assertRaises(BilqisError):
            answer_loss(output,target,{record.decision_id:True})

    def test_issued_logits_reject_mutated_legal_order_with_same_identities(self):
        output=predict_typed(*case())
        record=output.decisions[1]
        spec=next(d for d in output.plan.decisions if d.decision_id==record.decision_id)
        target=(DecisionOutput(record.decision_id,record.candidates[0]),)
        original=float(answer_loss(output,target,{record.decision_id:True}).total)
        object.__setattr__(spec,'legal_values',tuple(reversed(spec.legal_values)))
        object.__setattr__(record,'candidates',tuple(reversed(record.candidates)))
        with self.assertRaises(BilqisError):
            answer_loss(output,target,{record.decision_id:True})

    def test_unknown_label_id_or_nonboolean_mask_rejects(self):
        _, _, plan, _, _=case()
        output=ModelOutput(plan,(),(),DecodeStatus.UNRESOLVED,ExecutionMode.INFERENCE,None,True)
        with self.assertRaises(BilqisError):
            answer_loss(output,(),{'value':1})
        with self.assertRaises(BilqisError):
            answer_loss(output,(DecisionOutput('missing','wrong'),),{})
