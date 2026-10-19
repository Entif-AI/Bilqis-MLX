from unittest import TestCase

from bilqis_mlx.learning.championship_identity import (
    build_school_identity, enforce_school_identity)


def _identity(course="a", graph="b", release="c", width=8):
    return build_school_identity(
        course_sha256=course * 64,
        semantic_graph_sha256=graph * 64,
        parameter_shapes={"embedding.weight": [222, width], "head.weight": [width, 4]},
        factory_release_sha256=release * 64)


class ChampionshipIdentityTests(TestCase):
    def test_identity_is_deterministic_and_shape_sensitive(self):
        self.assertEqual(_identity(), _identity())
        self.assertNotEqual(_identity()["sha256"], _identity(width=9)["sha256"])
        self.assertNotEqual(_identity()["sha256"], _identity(course="d")["sha256"])
        self.assertNotEqual(_identity()["sha256"], _identity(graph="d")["sha256"])
        self.assertNotEqual(_identity()["sha256"], _identity(release="d")["sha256"])

    def test_identity_drift_archives_and_clears_all_live_authority(self):
        epoch = {
            "active_roles": {"A.X": {"capability": "A.X"}},
            "active_grade_soups": {"A": {"vote_count": 1}},
            "settled_matchups": {"A.X|1|2": {"winner_sha256": "1" * 64}},
            "championship_school_identity": _identity(),
            "championship_eligibility_after_step": 3,
        }
        student = {"sha256": "d" * 64, "optimizer_step": 11}
        result, changed = enforce_school_identity(
            epoch, _identity(course="e"), generation=20, student=student)
        self.assertTrue(changed)
        self.assertEqual(result["active_roles"], {})
        self.assertEqual(result["active_grade_soups"], {})
        self.assertEqual(result["settled_matchups"], epoch["settled_matchups"])
        self.assertEqual(result["championship_eligibility_after_step"], 11)
        historic = result["school_identity_history"][-1]
        self.assertEqual(historic["active_roles"], epoch["active_roles"])
        self.assertEqual(historic["active_grade_soups"], epoch["active_grade_soups"])
        self.assertEqual(historic["starting_student"], student)
        self.assertEqual(result["superseded_active_championships"][-1], historic)

    def test_same_identity_is_idempotent(self):
        identity = _identity()
        epoch = {"active_roles": {}, "active_grade_soups": {},
                 "settled_matchups": {}, "championship_school_identity": identity}
        student = {"sha256": "d" * 64, "optimizer_step": 11}
        first, changed = enforce_school_identity(
            epoch, identity, generation=20, student=student)
        self.assertFalse(changed)
        self.assertEqual(first, epoch)
