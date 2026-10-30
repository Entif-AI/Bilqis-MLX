"""B10.3 causal teacher forcing, legal loss masking, and fallback behavior."""
import unittest

import mlx.core as mx

from bilqis_mlx.learning.atlas_readout.control import ControlAction as C
from bilqis_mlx.learning.atlas_readout.decisions import (
    DecisionOutput as O,
    commit_decisions,
    start_decoding,
)
from bilqis_mlx.learning.atlas_readout.plan import (
    DecisionKind as K,
    DecisionSpec as D,
)
from bilqis_mlx.learning.atlas_readout.records import TypedHeadLogits
from bilqis_mlx.learning.atlas_readout.tests.plan_helpers import plan


class CausalTrainingTests(unittest.TestCase):
    def setUp(self):
        mx.set_default_device(mx.cpu)

    def _state(self):
        nodes = (
            D("parent", None, 0, K.EPISTEMIC, ("known", "unknown")),
            D("child", None, 0, K.EPISTEMIC, ("yes", "no"), ("parent",)),
            D("descendant", None, 0, K.EPISTEMIC, ("later-a", "later-b"), ("child",)),
        )
        state = start_decoding(plan(nodes))
        return commit_decisions(state, (O("parent", "unknown"),))

    def test_training_feedback_uses_only_declared_earlier_parent_targets(self):
        from bilqis_mlx.learning.atlas_readout.causal_training import decision_hidden

        state = self._state()
        anchor = mx.arange(768, dtype=mx.float32) / 1000
        parameters = {"readout.feedback": mx.eye(768, dtype=mx.float32)}
        first = decision_hidden(
            anchor, state, "child", parameters,
            teacher_targets={
                "parent": "known",
                "child": "yes",
                "descendant": "later-a",
            })
        changed_future = decision_hidden(
            anchor, state, "child", parameters,
            teacher_targets={
                "parent": "known",
                "child": "no",
                "descendant": "later-b",
            })
        changed_parent = decision_hidden(
            anchor, state, "child", parameters,
            teacher_targets={
                "parent": "unknown",
                "child": "yes",
                "descendant": "later-a",
            })
        self.assertTrue(bool(mx.allclose(first, changed_future)))
        self.assertFalse(bool(mx.allclose(first, changed_parent)))

    def test_inference_feedback_uses_committed_parent_not_teacher_target(self):
        from bilqis_mlx.learning.atlas_readout.causal_training import decision_hidden

        state = self._state()
        anchor = mx.zeros((768,), dtype=mx.float32)
        parameters = {"readout.feedback": mx.eye(768, dtype=mx.float32)}
        inferred = decision_hidden(anchor, state, "child", parameters)
        forced = decision_hidden(
            anchor, state, "child", parameters,
            teacher_targets={"parent": "known"})
        self.assertFalse(bool(mx.allclose(inferred, forced)))

    def test_legal_mask_excludes_illegal_control_logit_and_missing_auxiliary(self):
        from bilqis_mlx.learning.atlas_readout.causal_training import typed_decision_loss

        logits = mx.array([0.0, 1.0, 100.0, 200.0], dtype=mx.float32)
        head = TypedHeadLogits(
            logits,
            tuple(action.value for action in C),
            "answer.control/v1",
            "a" * 64,
        )
        loss = typed_decision_loss(
            head, C.EMIT_VALUE,
            legal_values=(C.EMIT_VALUE, C.EMIT_UNKNOWN))
        expected = mx.logsumexp(mx.array([0.0, 1.0], dtype=mx.float32))
        self.assertAlmostEqual(float(loss), float(expected), places=6)
        self.assertEqual(
            float(typed_decision_loss(
                head, None,
                legal_values=(C.EMIT_VALUE, C.EMIT_UNKNOWN),
                supplied=False)),
            0.0,
        )

        def loss(values):
            current = TypedHeadLogits(
                values,
                tuple(action.value for action in C),
                "answer.control/v1",
                "a" * 64,
            )
            return typed_decision_loss(
                current, C.EMIT_VALUE,
                legal_values=(C.EMIT_VALUE, C.EMIT_UNKNOWN))

        gradient = mx.grad(loss)(logits)
        self.assertEqual(gradient.tolist()[2:], [0.0, 0.0])

    def test_illegal_target_fails_closed_instead_of_entering_loss(self):
        from bilqis_mlx.learning.atlas_readout.causal_training import typed_decision_loss
        from bilqis_mlx.errors import BilqisError

        head = TypedHeadLogits(
            mx.array([0.0, 1.0, 2.0, 3.0], dtype=mx.float32),
            tuple(action.value for action in C),
            "answer.control/v1",
            "a" * 64,
        )
        with self.assertRaises(BilqisError):
            typed_decision_loss(
                head, C.EMIT_ALTERNATIVES,
                legal_values=(C.EMIT_VALUE, C.EMIT_UNKNOWN))

    def test_invalid_neural_decision_returns_explicit_fallback_request(self):
        from bilqis_mlx.learning.atlas_readout.causal_training import (
            NeuralDecisionStatus,
            commit_neural_decision,
        )

        state = start_decoding(plan((
            D("control", "agent", 0, K.CONTROL, (C.EMIT_UNKNOWN,)),
            D("end", None, 0, K.CONTROL, (C.END_FRAME,), ("control",)),
        )))
        rejected = commit_neural_decision(state, "control", C.EMIT_VALUE)
        self.assertIs(rejected.status, NeuralDecisionStatus.FALLBACK_REQUIRED)
        self.assertEqual(rejected.state, state)
        self.assertEqual(
            rejected.reason,
            "BAMF_B10_NEURAL_OUTPUT_ILLEGAL",
        )
        accepted = commit_neural_decision(state, "control", C.EMIT_UNKNOWN)
        self.assertIs(accepted.status, NeuralDecisionStatus.COMMITTED)
        self.assertEqual(accepted.state.committed, (O("control", C.EMIT_UNKNOWN),))

    def test_current_gold_cannot_change_current_decision_hidden_state(self):
        from bilqis_mlx.learning.atlas_readout.causal_training import decision_hidden

        state = start_decoding(plan((
            D("step1", None, 0, K.EPISTEMIC, ("known", "unknown")),
            D("step2", None, 0, K.EPISTEMIC, ("yes", "no"), ("step1",)),
        )))
        anchor = mx.arange(768, dtype=mx.float32) / 500
        parameters = {"readout.feedback": mx.eye(768, dtype=mx.float32)}
        yes = decision_hidden(
            anchor, state, "step1", parameters,
            teacher_targets={"step1": "known", "step2": "yes"})
        no = decision_hidden(
            anchor, state, "step1", parameters,
            teacher_targets={"step1": "unknown", "step2": "no"})
        self.assertTrue(bool(mx.allclose(yes, no)))


if __name__ == "__main__":
    unittest.main()
