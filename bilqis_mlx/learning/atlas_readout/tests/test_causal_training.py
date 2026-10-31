"""B10.3 causal teacher forcing, legal loss masking, and fallback behavior."""
from dataclasses import replace
import unittest

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
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
from bilqis_mlx.learning.atlas_readout.tests.helpers import banks, snapshot
from bilqis_mlx.learning.atlas_readout.tests.plan_helpers import concept, plan
from bilqis_mlx.semantics.frame_schema import ConceptRef


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

    def test_teacher_legality_replays_the_teacher_forced_prefix(self):
        from bilqis_mlx.learning.atlas_readout.causal_training import (
            _teacher_prefix_state,
        )

        state = start_decoding(plan((
            D("control", "agent", 0, K.CONTROL,
              (C.EMIT_VALUE, C.EMIT_UNKNOWN)),
            D("later", None, 0, K.EPISTEMIC, ("yes", "no"), ("control",)),
        )))
        state = commit_decisions(state, (O("control", C.EMIT_VALUE),))
        replayed = _teacher_prefix_state(
            state, 1, {"control": C.EMIT_UNKNOWN})
        self.assertEqual(
            replayed.committed, (O("control", C.EMIT_UNKNOWN),))

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

    def test_teacher_forcing_rejects_illegal_parent_target(self):
        from bilqis_mlx.learning.atlas_readout.causal_training import decision_hidden

        state = self._state()
        with self.assertRaises(BilqisError):
            decision_hidden(
                mx.zeros((768,), dtype=mx.float32),
                state,
                "child",
                {"readout.feedback": mx.eye(768, dtype=mx.float32)},
                teacher_targets={"parent": "forged"})

        dynamic = start_decoding(plan((
            D("parent", "agent", 0, K.CONTROL, (C.EMIT_UNKNOWN, C.END_FRAME)),
            D("child", None, 0, K.EPISTEMIC, ("known", "unknown"), ("parent",)),
        )))
        dynamic = commit_decisions(dynamic, (O("parent", C.EMIT_UNKNOWN),))
        with self.assertRaises(BilqisError):
            decision_hidden(
                mx.zeros((768,), dtype=mx.float32),
                dynamic,
                "child",
                {"readout.feedback": mx.eye(768, dtype=mx.float32)},
                teacher_targets={"parent": C.END_FRAME})

    def test_concept_feedback_is_exact_active_tied_identity_row(self):
        from bilqis_mlx.learning.atlas_readout.causal_training import encode_feedback_value

        source = snapshot()
        source = replace(
            source,
            semantic_lookup=tuple(sorted(
                (entry.semantic_id, position)
                for position, entry in enumerate(source.abi_entries))),
        )
        entry = source.abi_entries[0]
        concept = ConceptRef(
            entry.semantic_id, source.release_sha256, entry.index,
            ("urn:type:Entity",), "synthetic:source")
        active_banks = banks(source)
        encoded = encode_feedback_value(
            concept, snapshot=source, banks=active_banks)
        bank_index, row = divmod(entry.index, 8192)
        self.assertTrue(bool(mx.array_equal(
            encoded, active_banks[bank_index].weights[row])))
        changed = (
            replace(active_banks[0], active_semantic_digest="e" * 64),
            *active_banks[1:],
        )
        with self.assertRaises(BilqisError):
            encode_feedback_value(concept, snapshot=source, banks=changed)

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

    def test_value_loss_accepts_typed_concept_domain_and_masks_illegal_value(self):
        from bilqis_mlx.learning.atlas_readout import typed_decision_loss

        allowed = concept()
        other = replace(allowed, semantic_id="urn:concept:B", abi_index=12)
        head = TypedHeadLogits(
            mx.array([0.25, 100.0], dtype=mx.float32),
            (allowed, other),
            "answer.structured-frame/v1",
            allowed.semantic_release,
        )
        loss = typed_decision_loss(head, allowed, legal_values=(allowed,))
        self.assertAlmostEqual(float(loss), 0.0, places=6)
        gradient = mx.grad(
            lambda logits: typed_decision_loss(
                TypedHeadLogits(
                    logits, (allowed, other), "answer.structured-frame/v1",
                    allowed.semantic_release),
                allowed,
                legal_values=(allowed,)))(head.logits)
        self.assertEqual(gradient.tolist(), [0.0, 0.0])

    def test_value_loss_accepts_role_occurrence_domain(self):
        from bilqis_mlx.learning.atlas_readout.causal_training import typed_decision_loss
        from bilqis_mlx.semantics.frame_schema import BindingState, RoleOccurrence

        value = RoleOccurrence("agent", 0, concept=concept(), state=BindingState.VALUE)
        head = TypedHeadLogits(
            mx.array([0.0], dtype=mx.float32), (value,),
            "answer.structured-frame/v1", value.concept.semantic_release)
        self.assertEqual(
            float(typed_decision_loss(head, value, legal_values=(value,))), 0.0)

    def test_invalid_neural_decision_returns_explicit_fallback_request(self):
        from bilqis_mlx.learning.atlas_readout import (
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
        from_string = commit_neural_decision(
            state, "control", C.EMIT_UNKNOWN.value)
        self.assertIs(from_string.status, NeuralDecisionStatus.COMMITTED)
        self.assertEqual(
            from_string.state.committed, (O("control", C.EMIT_UNKNOWN),))

    def test_neural_decision_boundary_errors_remain_errorbus_failures(self):
        from bilqis_mlx.learning.atlas_readout import commit_neural_decision

        state = start_decoding(plan((
            D("control", "agent", 0, K.CONTROL, (C.EMIT_UNKNOWN,)),
            D("end", None, 0, K.CONTROL, (C.END_FRAME,), ("control",)),
        )))
        with self.assertRaises(BilqisError):
            commit_neural_decision(state, "missing", C.EMIT_UNKNOWN)
        committed = commit_decisions(state, (O("control", C.EMIT_UNKNOWN),))
        with self.assertRaises(BilqisError):
            commit_neural_decision(committed, "control", C.EMIT_UNKNOWN)

    def test_current_gold_cannot_change_current_decision_hidden_state(self):
        from bilqis_mlx.learning.atlas_readout import decision_hidden

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
