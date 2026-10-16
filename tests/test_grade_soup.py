"""Whole-student grade-soup contract; all fixtures are synthetic."""
import unittest
import numpy as np
from pathlib import Path
import tempfile

from bilqis_mlx.grade_soup import (
    grade_soup_recipe, needs_refresh, soup_vote_count, weighted_average,
    save_frozen_soup, verify_frozen_soup, retire_stale_soups,
)


def perfect(cap, sha, breadth=1, *, rubric="a" * 64):
    return {"rubric": rubric, "capability": cap, "correct": 12, "total": 12,
            "breadth": breadth, "perfect_capabilities": [cap, *(
                "A.OTHER" + str(i) for i in range(breadth-1))],
            "checkpoint": {"filename": "bundles/" + sha,
                           "sha256": sha * 64, "optimizer_step": 5,
                           "model_and_native_adamw": True}}


class GradeSoupTests(unittest.TestCase):
    def test_recipe_counts_capabilities_not_distinct_checkpoints(self):
        rows = {"k1": perfect("A.3", "1", 2),
                "k2": perfect("A.5", "1", 2),
                "k3": perfect("A.7", "2", 1),
                "k4": perfect("B.1", "3", 1)}
        plan = grade_soup_recipe(rows, "A", ("A.3", "A.5", "A.7", "A.11"))
        self.assertEqual(plan["vote_count"], 3)
        self.assertEqual(plan["coverage_peak"], 3)
        self.assertEqual({i["checkpoint"]["sha256"]: i["votes"] for i in plan["members"]},
                         {"1" * 64: 2, "2" * 64: 1})
        self.assertEqual(plan["perfect_capabilities"], ["A.3", "A.5", "A.7"])
        self.assertTrue(needs_refresh(None, plan))
        self.assertFalse(needs_refresh({**plan, "filename": "soups/old.safetensors"}, plan))

    def test_new_coverage_or_champion_displacement_refreshes_but_worse_ties_do_not(self):
        before = {"k1": perfect("A.3", "1", 2), "k2": perfect("A.5", "1", 2)}
        old = grade_soup_recipe(before, "A", ("A.3", "A.5", "A.7"))
        self.assertFalse(needs_refresh(old, grade_soup_recipe(dict(before), "A",
                                             ("A.3", "A.5", "A.7"))))
        after = {**before, "k3": perfect("A.7", "2")}
        self.assertTrue(needs_refresh(old, grade_soup_recipe(after, "A",
                                             ("A.3", "A.5", "A.7"))))
        replaced = {**before, "k2": perfect("A.5", "3", 3)}
        self.assertTrue(needs_refresh(old, grade_soup_recipe(replaced, "A",
                                             ("A.3", "A.5", "A.7"))))

    def test_vote_count_is_frozen_and_foreign_grade_dilution_uses_live_grade_count(self):
        snap = {"grade": "A", "vote_count": 7}
        self.assertEqual(soup_vote_count(snap, "A", 3), 7)
        self.assertAlmostEqual(soup_vote_count(snap, "B", 3), 7/3)
        self.assertAlmostEqual(soup_vote_count(snap, "C", 3), 7/3)
        self.assertEqual(soup_vote_count(snap, "B", 1), 7)
        self.assertEqual(soup_vote_count(snap, "B", 2), 3.5)
        self.assertEqual(snap["vote_count"], 7)

    def test_weight_soup_averages_per_role_and_cannot_mutate_ingredients(self):
        import mlx.core as mx
        left = {"embedding.weight": mx.array([[1., 3.]], dtype=mx.float32)}
        right = {"embedding.weight": mx.array([[7., 9.]], dtype=mx.float32)}
        fused = weighted_average(mx, ((2, left), (1, right)))
        np.testing.assert_allclose(np.asarray(fused["embedding.weight"]), [[3., 5.]])
        np.testing.assert_allclose(np.asarray(left["embedding.weight"]), [[1., 3.]])
        np.testing.assert_allclose(np.asarray(right["embedding.weight"]), [[7., 9.]])

    def test_frozen_file_is_exclusive_hash_verified_and_idempotent(self):
        import mlx.core as mx
        recipe = grade_soup_recipe({"a": perfect("A.3", "1")}, "A", ("A.3",))
        arrays = {"embedding.weight": mx.array([[3., 5.]], dtype=mx.float32)}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = save_frozen_soup(root, recipe, arrays, reserve_gib=0., token_count=1)
            self.assertEqual(verify_frozen_soup(root, first), root / first["filename"])
            second = save_frozen_soup(root, recipe, arrays, reserve_gib=0., token_count=1)
            self.assertEqual(first, second)
            self.assertEqual(len(list((root / "soups").iterdir())), 1)
            blob = root / first["filename"]
            blob.write_bytes(blob.read_bytes() + b"corrupt")
            with self.assertRaisesRegex(ValueError, "ARTIFACT_CHANGED"):
                verify_frozen_soup(root, first)

    def test_superseded_older_snapshots_retire_only_after_new_one_is_pinned(self):
        import mlx.core as mx
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshots = []
            for index in range(3):
                recipe = grade_soup_recipe({"cap": perfect("A.3", str(index+1))},
                                          "A", ("A.3",))
                snapshots.append(save_frozen_soup(
                    root, recipe,
                    {"embedding.weight": mx.array([[float(index)]], dtype=mx.float32)},
                    reserve_gib=0., token_count=1))
            latest = {**snapshots[2], "previous": {
                "filename": snapshots[1]["filename"],
                "sha256": snapshots[1]["sha256"]}}
            unknown = root / "soups" / "manual-custody.txt"
            unknown.write_text("do not touch")
            self.assertEqual(retire_stale_soups(root, {"A": latest}),
                             (snapshots[0]["filename"],))
            self.assertFalse((root / snapshots[0]["filename"]).exists())
            self.assertTrue((root / snapshots[1]["filename"]).exists())
            self.assertTrue((root / snapshots[2]["filename"]).exists())
            self.assertEqual(unknown.read_text(), "do not touch")
