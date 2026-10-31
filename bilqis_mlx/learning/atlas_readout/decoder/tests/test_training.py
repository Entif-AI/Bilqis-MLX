"""A real backward pass through source-active feedback and typed heads."""
from dataclasses import replace
import unittest
import numpy as np
import mlx.core as mx
from bilqis_mlx.learning.atlas_readout import (
    predict_typed, answer_loss, DecisionOutput, ControlAction,
)
from bilqis_mlx.learning.atlas_readout.decoder.tests.helpers import case
from bilqis_mlx.learning.atlas_readout.decoder.tests.test_prediction import role_plan


class DecoderTrainingTests(unittest.TestCase):
    def test_executed_heads_feedback_identity_and_hidden_receive_gradients(self):
        memory,context,plan,semantics,params=case();plan=role_plan(plan)
        plan=replace(plan,decisions=(replace(plan.decisions[0],
            legal_values=(ControlAction.EMIT_VALUE,ControlAction.EMIT_UNKNOWN)),*plan.decisions[1:]))
        targets=(DecisionOutput('control',ControlAction.EMIT_VALUE),
                 DecisionOutput('value',plan.decisions[1].legal_values[0]),
                 DecisionOutput('role',plan.decisions[2].legal_values[0]),
                 DecisionOutput('end',ControlAction.END_FRAME))
        def objective(tree):
            parameters,hidden=tree
            active=replace(semantics,banks=(replace(semantics.banks[0],
                              weights=parameters['identity.bank.0']),))
            output=predict_typed(replace(memory,hidden=hidden),context,plan,active,parameters,targets)
            return answer_loss(output,targets,{t.decision_id:True for t in targets}).total
        gradients,hidden_gradient=mx.grad(objective)((params,memory.hidden))
        for name in ('identity.bank.0','features.role','readout.control','readout.control_bias',
                     'readout.role_query','readout.feedback','readout.query','readout.key',
                     'readout.value','readout.output','readout.state_norm','readout.output_norm'):
            with self.subTest(parameter=name):
                self.assertTrue(bool(mx.all(mx.isfinite(gradients[name]))))
                self.assertGreater(float(mx.sum(mx.abs(gradients[name]))),0)
        self.assertGreater(float(mx.sum(mx.abs(hidden_gradient[:5]))),0)
        np.testing.assert_array_equal(np.asarray(hidden_gradient[5:]),0)
        self.assertEqual(float(mx.sum(mx.abs(gradients['identity.bank.0'][0]))),0)
