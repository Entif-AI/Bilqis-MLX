"""Source selection."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, select_source_lesson,
)


class SourceSelectionTests(CausalTeacherExperimentTests):
    def test_source_lesson_reserves_weak_semantic_before_policy_fill(self):
        target = {
            "id": "number-three", "capability": "C.NUMBER", "gold": "3",
            "source_id": "source-three", "tokens": [1, 3, 9],
            "answer_kind": "numeric_active",
        }
        current = [
            target,
            {"id": "number-two", "capability": "C.NUMBER", "gold": "2",
             "source_id": "source-two", "tokens": [1, 2, 9],
             "answer_kind": "numeric_active"},
            {"id": "eq-two", "capability": "C.NUMBER", "gold": "TRUE",
             "source_id": "source-two", "tokens": [1, 8, 2, 2, 9],
             "answer_kind": "binary"},
        ]
        prior = [
            {"id": "old-true", "capability": "B.NOT", "gold": "TRUE",
             "source_id": "old-true", "tokens": [1, 4, 9],
             "answer_kind": "binary"},
            {"id": "old-false", "capability": "B.NOT", "gold": "FALSE",
             "source_id": "old-false", "tokens": [1, 5, 9],
             "answer_kind": "binary"},
        ]

        exposures = {target["id"]: 0}
        for seed in range(11, 15):
            picked, control = select_source_lesson(
                current, prior, {"old": 16, "depth": 1, "contrast": 0.},
                targets=[target], target_exposures=exposures,
                reserved_support_slots=2, seed=seed, batch_size=8)
            self.assertIn(target["id"], {row["id"] for row in picked})
            self.assertEqual(control["weakness_targets_requested"], 1)
            self.assertEqual(control["weakness_targets_delivered"], 1)
            exposures[target["id"]] += 1

        self.assertEqual(exposures[target["id"]], 4)

    def test_champion_priority_target_wins_limited_weakness_slot(self):
        champion = {
            "id": "z-champion", "capability": "C.SUB", "gold": "3",
            "source_id": "champion", "tokens": [1, 3, 9],
            "answer_kind": "numeric_active",
        }
        ordinary = {
            "id": "a-ordinary", "capability": "C.SUB", "gold": "2",
            "source_id": "ordinary", "tokens": [1, 2, 9],
            "answer_kind": "numeric_active",
        }
        current = [
            champion, ordinary,
            {"id": "n1", "capability": "C.SUB", "gold": "1",
             "source_id": "n1", "tokens": [1, 1, 9],
             "answer_kind": "numeric_active"},
            {"id": "n0", "capability": "C.SUB", "gold": "0",
             "source_id": "n0", "tokens": [1, 0, 9],
             "answer_kind": "numeric_active"},
        ]
        _picked, control = select_source_lesson(
            current, [], {"old": 0, "depth": 1, "contrast": 0.},
            targets=[ordinary, champion],
            priority_target_ids={champion["id"]},
            target_exposures={ordinary["id"]: 0, champion["id"]: 0},
            reserved_support_slots=2, seed=7, batch_size=4)
        self.assertEqual(control["weakness_target_ids"], [champion["id"]])
        self.assertEqual(control["priority_weakness_targets_delivered"], 1)

    def test_typed_weakness_replay_preserves_one_complete_fresh_source_bundle(self):
        current = []
        for group in range(6):
            source_id = f"fresh-{group}"
            current.extend([
                {"id": f"{source_id}-numeric", "capability": "C.COUNT",
                 "gold": str(group), "source_id": source_id,
                 "tokens": [1, group, 9], "answer_kind": "numeric_active"},
                {"id": f"{source_id}-true", "capability": "C.COUNT",
                 "gold": "TRUE", "source_id": source_id,
                 "tokens": [1, group, 7, 9], "answer_kind": "binary"},
                {"id": f"{source_id}-false", "capability": "C.COUNT",
                 "gold": "FALSE", "source_id": source_id,
                 "tokens": [1, group, 8, 9], "answer_kind": "binary"},
            ])
        targets = [
            {"id": f"miss-{index}", "capability": "C.COUNT",
             "gold": "FALSE", "source_id": f"historic-{index}",
             "tokens": [1, 99, index, 9], "answer_kind": "binary"}
            for index in range(24)
        ]
        prior = [
            {"id": f"old-{index}", "capability": "A.IDENTITY",
             "gold": "TRUE" if index % 2 else "FALSE",
             "source_id": f"old-{index}", "tokens": [1, index, 9],
             "answer_kind": "binary"}
            for index in range(32)
        ]

        picked, control = select_source_lesson(
            [*current, *targets], prior,
            {"old": 16, "depth": 1, "contrast": 0.},
            targets=targets,
            target_exposures={row["id"]: 0 for row in targets},
            seed=41, batch_size=32)

        support_ids = set(control["fresh_support_ids"])
        self.assertEqual(len(support_ids), 3)
        support = [row for row in current if row["id"] in support_ids]
        self.assertEqual(len({row["source_id"] for row in support}), 1)
        self.assertEqual(
            {(row["answer_kind"], row["gold"]) for row in support},
            {("numeric_active", support[0]["source_id"].split("-")[-1]),
             ("binary", "TRUE"), ("binary", "FALSE")})
        self.assertTrue(support_ids <= {row["id"] for row in picked})
        self.assertLessEqual(control["weakness_targets_delivered"], 13)
        self.assertGreaterEqual(
            len([row for row in picked if row["id"] in {r["id"] for r in current}]),
            3)

    def test_weakness_replay_yields_when_fresh_support_fills_current_slice(self):
        source_id = "fresh-complete-family"
        fresh_family = [
            {"id": f"{source_id}-{index}", "capability": "C.SUCCESSOR",
             "gold": str(index), "source_id": source_id,
             "tokens": [1, index, 9], "answer_kind": "numeric_active"}
            for index in range(8)
        ]
        target = {
            "id": "historic-miss", "capability": "C.SUCCESSOR",
            "gold": "FALSE", "source_id": "historic-miss",
            "tokens": [1, 99, 9], "answer_kind": "binary",
        }
        prior = [
            {"id": f"old-{index}", "capability": "B.AND",
             "gold": "TRUE" if index % 2 else "FALSE",
             "source_id": f"old-{index}", "tokens": [1, index, 9],
             "answer_kind": "binary"}
            for index in range(32)
        ]

        picked, control = select_source_lesson(
            [*fresh_family, target], prior,
            {"old": 24, "depth": 1, "contrast": 0.},
            targets=[target], target_exposures={target["id"]: 0},
            seed=43, batch_size=32)

        self.assertEqual(len(picked), 32)
        self.assertEqual(control["fresh_support_delivered"], 8)
        self.assertEqual(control["weakness_targets_requested"], 0)
        self.assertEqual(control["weakness_targets_delivered"], 0)
        self.assertNotIn(target["id"], {row["id"] for row in picked})
