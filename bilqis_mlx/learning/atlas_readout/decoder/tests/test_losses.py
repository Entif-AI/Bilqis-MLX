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
        executed=predict_typed(*fixture)
        spec=plan.decisions[1]
        record=DecisionLogits('value',DecisionKind.VALUE,spec.legal_values,
                              mx.array([1.,2.],dtype=mx.float32))
        output=replace(executed,decisions=(executed.decisions[0],record,executed.decisions[2]),
                       execution_mode=ExecutionMode.TEACHER_FORCED)
        actual=answer_loss(output,(DecisionOutput('value',spec.legal_values[0]),),{'value':True})
        self.assertAlmostEqual(float(actual.primary),float(np.log1p(np.exp(1))),places=6)
        self.assertEqual(float(actual.role),0)
        self.assertEqual(float(actual.epistemic),0)
        self.assertEqual(float(actual.total),float(actual.primary))
        self.assertEqual(float(answer_loss(output,(),{'value':True}).total),0)
        self.assertEqual(float(answer_loss(output,(DecisionOutput('value',spec.legal_values[0]),),
                                           {'value':False}).total),0)

    def test_masked_label_keeps_exact_zero_gradient(self):
        fixture=case()
        plan=fixture[2]
        executed=predict_typed(*fixture)
        values=plan.decisions[1].legal_values
        def objective(logits):
            output=replace(executed,decisions=(executed.decisions[0],
                DecisionLogits('value',DecisionKind.VALUE,values,logits),executed.decisions[2]),
                execution_mode=ExecutionMode.TEACHER_FORCED)
            return answer_loss(output,(DecisionOutput('value',values[0]),),{'value':False}).total
        np.testing.assert_array_equal(np.asarray(mx.grad(objective)(mx.array([1.,2.]))),[0,0])

    def test_unknown_label_id_or_nonboolean_mask_rejects(self):
        _, _, plan, _, _=case()
        output=ModelOutput(plan,(),(),DecodeStatus.UNRESOLVED,ExecutionMode.INFERENCE,None,True)
        with self.assertRaises(BilqisError):
            answer_loss(output,(),{'value':1})
        with self.assertRaises(BilqisError):
            answer_loss(output,(DecisionOutput('missing','wrong'),),{})
