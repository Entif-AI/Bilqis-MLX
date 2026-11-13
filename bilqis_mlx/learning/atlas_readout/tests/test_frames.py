"""Only completed source-valid bindings become frame answers."""
from dataclasses import replace
import unittest
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_schema import BindingState, RoleOccurrence
from bilqis_mlx.learning.atlas_readout.control import ControlAction as C
from bilqis_mlx.learning.atlas_readout.plan import DecisionKind as K, DecisionSpec as D
from bilqis_mlx.learning.atlas_readout.decisions import (
    DecisionOutput as O, DecodeState, DecodeStatus, start_decoding, commit_decisions,
)
from bilqis_mlx.learning.atlas_readout.frames import can_end_frame, publish_frame, FrameAnswer
from bilqis_mlx.learning.atlas_readout.tests.plan_helpers import plan, concept


def frame_plan(value, action=C.EMIT_VALUE):
    return plan((D('control', 'agent', 0, K.CONTROL, (action,)),
                 D('value', 'agent', 0, K.VALUE, (value,), ('control',)),
                 D('end', None, 0, K.CONTROL, (C.END_FRAME,), ('control',))))


def close_value(value, action=C.EMIT_VALUE):
    state = commit_decisions(start_decoding(frame_plan(value, action)), (O('control', action),))
    state = commit_decisions(state, (O('value', value),))
    return commit_decisions(state, (O('end', C.END_FRAME),))


class FrameOutputTests(unittest.TestCase):
    def test_concept_publication_preserves_generation_and_source_identity(self):
        state = close_value(concept())
        answer = publish_frame(state)
        self.assertEqual(answer.bindings[0].concept, concept())
        self.assertEqual(answer.schema_id, 'frame:fixture')
        self.assertEqual(answer.revision, 1)
        self.assertEqual(answer.generation_binding, 'generation:fixture')
        self.assertEqual(answer.semantic_release, concept().semantic_release)

    def test_unknown_and_explicit_none_have_distinct_typed_outputs(self):
        p = plan((D('unknown', 'agent', 0, K.CONTROL, (C.EMIT_UNKNOWN,)),
                  D('end', None, 0, K.CONTROL, (C.END_FRAME,), ('unknown',))))
        state = commit_decisions(start_decoding(p), (O('unknown', C.EMIT_UNKNOWN),))
        state = commit_decisions(state, (O('end', C.END_FRAME),))
        unknown = publish_frame(state).bindings[0]
        none = publish_frame(close_value(RoleOccurrence('agent', 0, state=BindingState.NONE))).bindings[0]
        self.assertIs(unknown.state, BindingState.UNKNOWN)
        self.assertIs(none.state, BindingState.NONE)
        self.assertNotEqual(unknown, none)

    def test_alternatives_require_matching_control_parent(self):
        value = RoleOccurrence('agent', 0, state=BindingState.ALTERNATIVES, alternatives=(concept(),))
        answer = publish_frame(close_value(value, C.EMIT_ALTERNATIVES))
        self.assertEqual(answer.bindings[0].alternatives, (concept(),))
        state = commit_decisions(start_decoding(frame_plan(value)), (O('control', C.EMIT_VALUE),))
        with self.assertRaises(BilqisError):
            commit_decisions(state, (O('value', value),))

    def test_wrong_source_type_cannot_end_or_publish(self):
        value = replace(concept(), type_ids=('OtherType',))
        state = commit_decisions(start_decoding(frame_plan(value)), (O('control', C.EMIT_VALUE),))
        state = commit_decisions(state, (O('value', value),))
        self.assertFalse(can_end_frame(state))
        self.assertIs(state.status, DecodeStatus.UNRESOLVED)
        with self.assertRaises(BilqisError):
            commit_decisions(state, (O('end', C.END_FRAME),))
        with self.assertRaises(BilqisError):
            FrameAnswer(state.plan, (RoleOccurrence('agent', 0, concept=value),))

    def test_duplicate_coordinate_and_altered_state_reject(self):
        answer = publish_frame(close_value(concept()))
        with self.assertRaises(BilqisError):
            FrameAnswer(answer.plan, answer.bindings * 2)
        closed = close_value(concept())
        with self.assertRaises(BilqisError):
            DecodeState(closed.plan, closed.committed + (O('end', C.END_FRAME),))
        with self.assertRaises(BilqisError):
            replace(closed, schema_version='old')
