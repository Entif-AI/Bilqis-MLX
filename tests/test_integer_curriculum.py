"""Environment-bounded, seeded semantic curriculum contract (no live training)."""

import os
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.integer_curriculum import IntegerScope, generate_integer_curriculum
from bilqis_mlx.pedagogical_parity import build_plan


LEGACY = Path(__file__).resolve().parents[2] / "bilqis-triplets-v16"


class IntegerCurriculumTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parity = build_plan(LEGACY)

    def test_one_environment_variable_controls_the_integer_semantic_range(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True):
            self.assertEqual(IntegerScope.from_environment(
                self.parity, env_file=Path(temp)/"absent.env").maximum, 3)
        with patch.dict(os.environ, {"BILQIS_INTEGER_MAX": "9"}):
            self.assertEqual(IntegerScope.from_environment(self.parity).maximum, 9)
            rows = generate_integer_curriculum(self.parity, LEGACY, seed=91, count=36)
            self.assertEqual(rows["integer_max"], 9)
            self.assertEqual(len(rows["heads"]["numeric_active"]["values"]), 10)
        self.assertEqual(len(self.parity["heads"]["semantic_token"]["values"]), 222)

    def test_one_local_env_file_changes_all_integer_generators(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            filename=Path(tmp)/".env"
            filename.write_text("# single source of integer semantics\nBILQIS_INTEGER_MAX=9\n")
            self.assertEqual(IntegerScope.from_environment(
                self.parity, env_file=filename).maximum,9)
            filename.write_text("BILQIS_INTEGER_MAX=3\nBILQIS_INTEGER_MAX=9\n")
            with self.assertRaisesRegex(ValueError,"INTEGER_SCOPE_DUPLICATED"):
                IntegerScope.from_environment(self.parity, env_file=filename)
            with patch.dict(os.environ,{"BILQIS_INTEGER_MAX":"7"}):
                self.assertEqual(IntegerScope.from_environment(
                    self.parity, env_file=filename).maximum,7)

    def test_bad_range_and_unattested_token_boundaries_fail_closed(self):
        for value in ("", "not-a-number", "-1", "101", "1.5"):
            with self.subTest(value=value), patch.dict(os.environ,
                    {"BILQIS_INTEGER_MAX": value}):
                with self.assertRaisesRegex(ValueError, "INTEGER_SCOPE_"):
                    IntegerScope.from_environment(self.parity)

    def test_seeded_passes_vary_but_replay_bit_for_bit(self):
        a = generate_integer_curriculum(self.parity, LEGACY, seed=3, count=40,
                                        maximum=7)
        b = generate_integer_curriculum(self.parity, LEGACY, seed=3, count=40,
                                        maximum=7)
        c = generate_integer_curriculum(self.parity, LEGACY, seed=4, count=40,
                                        maximum=7)
        self.assertEqual(a, b)
        self.assertNotEqual(a["rows"], c["rows"])

    def test_every_direct_answer_is_paired_with_both_oracled_truth_values(self):
        generated = generate_integer_curriculum(self.parity, LEGACY,
                                                seed=20, count=50, maximum=9)
        for family in generated["rows"]:
            direct, true_row, false_row = family["views"]
            self.assertEqual(direct["answer_kind"], "numeric_active")
            self.assertEqual(true_row["gold"], "TRUE")
            self.assertEqual(false_row["gold"], "FALSE")
            self.assertEqual({r["source_id"] for r in family["views"]},
                             {family["source_id"]})
            number = int(direct["gold"])
            self.assertLessEqual(number, generated["integer_max"])
            self.assertEqual(direct["native_output"]["identity"],
                             "school.number." + str(number))

    def test_stable_source_partition_is_never_shared_across_split_or_pass(self):
        seen = {}
        for seed in range(5):
            generated = generate_integer_curriculum(self.parity, LEGACY,
                                                    seed=seed, count=80, maximum=9)
            for family in generated["rows"]:
                identifier, split = family["source_id"], family["partition"]
                self.assertIn(split, ("train", "development", "sealed"))
                self.assertEqual(seen.setdefault(identifier, split), split)

    def test_number_range_restricts_lessons_not_vocabulary_ability(self):
        generated = generate_integer_curriculum(self.parity, LEGACY,
                                                seed=42, count=30, maximum=3)
        self.assertEqual(len(generated["heads"]["numeric_active"]["values"]), 4)
        self.assertEqual(len(generated["heads"]["semantic_token"]["values"]), 222)
        self.assertEqual(len(generated["heads"]["numeric_full_101"]["values"]), 101)
        self.assertFalse(generated["qualification_authorized"])

    def test_disposable_mlx_student_actually_learns_source_examples(self):
        from bilqis_mlx.integer_learning_smoke import run_smoke
        result = run_smoke(self.parity, LEGACY, seed=100, count=20,
                           steps=100, maximum=3)
        self.assertLess(result["source_loss_after"],
                        result["source_loss_before"])
        for kind in ("numeric_active","semantic_token","evidence"):
            before=result["train_before"][kind]
            after=result["train_after"][kind]
            self.assertGreater(after["correct"],before["correct"])
            self.assertEqual(after["correct"],after["total"])
        self.assertEqual(result["scope"],"DISPOSABLE_SYNTHETIC_STUDENT_ONLY")
        self.assertEqual(result["claim"],
                         "EXPOSED_ACQUISITION_NOT_SEALED_QUALIFICATION")


if __name__ == "__main__":
    import unittest
    unittest.main()
