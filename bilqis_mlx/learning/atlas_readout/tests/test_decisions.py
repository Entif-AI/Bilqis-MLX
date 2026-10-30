"""Dependency commits consume only earlier outputs under explicit finite budgets."""
from dataclasses import replace
import unittest
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_readout.control import ControlAction as C
from bilqis_mlx.learning.atlas_readout.plan import DecisionKind as K, DecisionSpec as D
from bilqis_mlx.learning.atlas_readout.decisions import (
    DecisionOutput as O, DecodeStatus, start_decoding, ready_decisions,
    commit_decisions, parent_outputs,
)
from bilqis_mlx.learning.atlas_readout.frames import can_end_frame, publish_frame
from bilqis_mlx.learning.atlas_readout.tests.plan_helpers import plan, concept
from bilqis_mlx.learning.atlas_readout.tests.test_plan import standard_decisions


def two_independent():
    return (D('a', 'agent', 0, K.CONTROL, (C.EMIT_VALUE, C.EMIT_UNKNOWN)),
            D('b', 'theme', 0, K.CONTROL, (C.EMIT_UNKNOWN,)),
            D('v', 'agent', 0, K.VALUE, (concept(),), ('a',)),
            D('z', None, 0, K.CONTROL, (C.END_FRAME,), ('a', 'b')))


class DecisionTests(unittest.TestCase):
    def test_independent_ready_batch_and_dependent_wait(self):
        state = start_decoding(plan(two_independent()))
        self.assertEqual([x.decision_id for x in ready_decisions(state)], ['a', 'b'])
        with self.assertRaises(BilqisError):
            commit_decisions(state, (O('a', C.EMIT_VALUE), O('v', concept())))
        after = commit_decisions(state, (O('b', C.EMIT_UNKNOWN), O('a', C.EMIT_VALUE)))
        self.assertEqual(state.committed, ())
        self.assertEqual([x.decision_id for x in ready_decisions(after)], ['v'])
        self.assertEqual(parent_outputs(after, 'v'), (C.EMIT_VALUE,))
        done = commit_decisions(after, (O('v', concept()),))
        self.assertTrue(can_end_frame(done))
        closed = commit_decisions(done, (O('z', C.END_FRAME),))
        self.assertIs(closed.status, DecodeStatus.COMPLETE)
        self.assertEqual([b.key for b in publish_frame(closed).bindings], [('agent', 0), ('theme', 0)])
        with self.assertRaises(BilqisError):
            commit_decisions(closed, (O('v', concept()),))

    def test_early_end_and_uncommitted_parent_reject(self):
        source = standard_decisions()
        source = (source[0], source[1], replace(source[2], depends_on=()))
        state = start_decoding(plan(source))
        with self.assertRaises(BilqisError):
            parent_outputs(state, 'value')
        with self.assertRaises(BilqisError):
            commit_decisions(state, (O('end', C.END_FRAME),))
        with self.assertRaises(BilqisError):
            publish_frame(state)

    def test_sixty_four_decisions_return_partial(self):
        nodes = tuple(D(f'e{i:02}', None, 0, K.EPISTEMIC, ('UNKNOWN',)) for i in range(65))
        state = start_decoding(plan(nodes))
        self.assertEqual(len(ready_decisions(state)), 64)
        state = commit_decisions(state, tuple(O(d.decision_id, 'UNKNOWN') for d in ready_decisions(state)))
        self.assertIs(state.status, DecodeStatus.PARTIAL)
        self.assertEqual(len(state.committed), 64)
        self.assertEqual(ready_decisions(state), ())
        with self.assertRaises(BilqisError):
            commit_decisions(state, (O('e64', 'UNKNOWN'),))

    def test_combined_position_budget_and_zero_remaining(self):
        nodes = tuple(D(f'e{i}', None, 0, K.EPISTEMIC, ('UNKNOWN',)) for i in range(3))
        state = start_decoding(plan(nodes, prefix=1022))
        self.assertEqual(len(ready_decisions(state)), 2)
        after = commit_decisions(state, tuple(O(d.decision_id, 'UNKNOWN') for d in ready_decisions(state)))
        self.assertIs(after.status, DecodeStatus.PARTIAL)
        self.assertIs(start_decoding(plan(nodes, prefix=1024)).status, DecodeStatus.PARTIAL)

    def test_role_string_cannot_be_a_control_and_duplicate_batch_rejects(self):
        state = start_decoding(plan(standard_decisions()))
        for outputs in ((O('control', 'agent'),), (O('control', C.EMIT_VALUE), O('control', C.EMIT_VALUE))):
            with self.assertRaises(BilqisError):
                commit_decisions(state, outputs)

    def test_dependent_result_uses_committed_parent_value(self):
        nodes = (D('parent', None, 0, K.EPISTEMIC, ('known', 'unknown')),
                 D('child', None, 0, K.EPISTEMIC, ('known', 'unknown'), ('parent',)))
        state = commit_decisions(start_decoding(plan(nodes)), (O('parent', 'known'),))
        child_value = parent_outputs(state, 'child')[0]
        after = commit_decisions(state, (O('child', child_value),))
        self.assertEqual(after.committed[-1].value, 'known')
        self.assertIs(after.status, DecodeStatus.UNRESOLVED)

    def test_end_frame_is_a_single_commit_publication_barrier(self):
        nodes = (D('control', 'agent', 0, K.CONTROL, (C.EMIT_UNKNOWN,)),
                 D('aux', None, 0, K.EPISTEMIC, ('UNKNOWN',), ('control',)),
                 D('end', None, 0, K.CONTROL, (C.END_FRAME,), ('control',)))
        state = commit_decisions(start_decoding(plan(nodes)), (O('control', C.EMIT_UNKNOWN),))
        self.assertEqual([d.decision_id for d in ready_decisions(state)], ['aux', 'end'])
        with self.assertRaises(BilqisError):
            commit_decisions(state, (O('aux', 'UNKNOWN'), O('end', C.END_FRAME)))
        closed = commit_decisions(state, (O('end', C.END_FRAME),))
        self.assertIs(closed.status, DecodeStatus.COMPLETE)
        self.assertEqual([o.decision_id for o in closed.committed], ['control', 'end'])
