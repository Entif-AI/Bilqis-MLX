import unittest
from types import SimpleNamespace

from bilqis_mlx.boolean_identification import REPRESENTATION_VARIATION
from bilqis_mlx.boolean_composite import (
    PRESENTATION as COMPOSITE_PRESENTATION,
    REPRESENTATION_VARIATION as COMPOSITE_REPRESENTATION_VARIATION,
)
from bilqis_mlx.live_grade_b import (
    OUTER_LANDMARK_PRESENTATION,
    OUTER_LANDMARK_VARIATION,
)
from bilqis_mlx.learning.teacher_geometry import (
    AND_IMPLIES_EPOCH,
    COMPOSITE_EPOCH,
    IDBOOLOPS_EPOCH,
    active_epoch,
    context_scope,
    row_matches_epoch,
)


def release(capability, axes):
    execution = SimpleNamespace(variation_axes=tuple(axes))
    return SimpleNamespace(
        execution_plan=SimpleNamespace(
            capability_map={capability: execution}))


class TeacherGeometryTests(unittest.TestCase):
    def test_only_authorized_changed_capabilities_open_new_geometry_epochs(self):
        self.assertEqual(
            active_epoch(
                release("B.IDBOOLOPS", (REPRESENTATION_VARIATION,)),
                "B.IDBOOLOPS"),
            IDBOOLOPS_EPOCH)
        self.assertEqual(
            active_epoch(
                release("B.AND", (OUTER_LANDMARK_VARIATION,)),
                "B.AND"),
            AND_IMPLIES_EPOCH)
        self.assertEqual(
            active_epoch(
                release("B.IMPLIES", (OUTER_LANDMARK_VARIATION,)),
                "B.IMPLIES"),
            AND_IMPLIES_EPOCH)
        self.assertIsNone(
            active_epoch(
                release("B.IFF", (OUTER_LANDMARK_VARIATION,)),
                "B.IFF"))
        self.assertEqual(
            active_epoch(
                release("B.COMPOSITE", (COMPOSITE_REPRESENTATION_VARIATION,)),
                "B.COMPOSITE"),
            COMPOSITE_EPOCH)

    def test_geometry_epoch_partitions_teacher_context_without_rewriting_base_scope(self):
        base = "bilqis.mlx.grade-a-b-c-live/20261016-v1/6"
        self.assertEqual(context_scope(base, None), base)
        self.assertEqual(
            context_scope(base, AND_IMPLIES_EPOCH),
            base + "/geometry=" + AND_IMPLIES_EPOCH)

    def test_old_and_implies_misses_do_not_replay_into_new_geometry(self):
        old = {
            "capability": "B.AND",
            "record": {"task": "evaluate"},
        }
        current = {
            "capability": "B.AND",
            "record": {
                "task": "evaluate",
                "presentation": OUTER_LANDMARK_PRESENTATION,
            },
        }
        self.assertFalse(row_matches_epoch(old, AND_IMPLIES_EPOCH))
        self.assertTrue(row_matches_epoch(current, AND_IMPLIES_EPOCH))

    def test_old_idboolops_misses_do_not_replay_into_new_geometry(self):
        old = {
            "capability": "B.IDBOOLOPS",
            "record": {"observations": [{
                "operands": [{"kind": "literal", "value": False},
                             {"kind": "literal", "value": True}],
                "result": True,
            }]},
        }
        current = {
            "capability": "B.IDBOOLOPS",
            "record": {"observations": [{
                "assignments": {"P": False, "Q": True},
                "result": True,
            }]},
        }
        self.assertFalse(row_matches_epoch(old, IDBOOLOPS_EPOCH))
        self.assertTrue(row_matches_epoch(current, IDBOOLOPS_EPOCH))

    def test_old_composite_misses_do_not_replay_into_new_geometry(self):
        old = {
            "capability": "B.COMPOSITE",
            "record": {"task": "evaluate"},
        }
        current = {
            "capability": "B.COMPOSITE",
            "record": {
                "task": "evaluate",
                "presentation": COMPOSITE_PRESENTATION,
            },
        }
        self.assertFalse(row_matches_epoch(old, COMPOSITE_EPOCH))
        self.assertTrue(row_matches_epoch(current, COMPOSITE_EPOCH))
