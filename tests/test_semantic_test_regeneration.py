"""Behavioral proof of on-demand, dependency-aware regenerated examinations."""

import json
import os
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.pedagogical_parity import build_plan
from bilqis_mlx.semantic_test_generation import (
    FAMILIES, ROOT, check_generated, regenerate, select_families, status,
)

LEGACY = Path(__file__).resolve().parents[2] / "bilqis-triplets-v16"


class TestOnDemandRegeneration(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parity = build_plan(LEGACY)

    def test_integer_type_rebuilds_every_dependent_family_but_not_unrelated_boolean(self):
        for kind in ("type:integer", "type:boolean"):
            self.assertEqual(set(select_families(kind)),
                             {f.name for f in FAMILIES if kind in f.dependencies})
        self.assertTrue({"integer.direct", "integer.truth", "integer.equivalence",
                         "integer.inverse_negation"} <= set(select_families("type:integer")))
        self.assertNotIn("boolean.constants",select_families("type:integer"))
        with self.assertRaisesRegex(ValueError, "SEMANTIC_TEST_SELECTOR"):
            select_families("type:imaginary")

    def test_one_env_change_marks_all_integer_dependent_tests_stale(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            with patch.dict(os.environ, {"BILQIS_INTEGER_MAX": "3"}):
                first = regenerate(self.parity, LEGACY, directory, selector="all",
                                   seed=401, count=30)
                self.assertTrue(check_generated(self.parity, LEGACY, directory))
                stable = first["suites"]["boolean.constants"]["sha256"]
            with patch.dict(os.environ, {"BILQIS_INTEGER_MAX": "9"}):
                observed = status(self.parity, directory, selector="type:integer")
                self.assertEqual(set(observed["stale"]),
                                 set(select_families("type:integer")))
                with self.assertRaisesRegex(ValueError, "SEMANTIC_TEST_STALE"):
                    check_generated(self.parity, LEGACY, directory)
                newer = regenerate(self.parity, LEGACY, directory,
                                   selector="type:integer", seed=401, count=30)
                self.assertTrue(check_generated(self.parity, LEGACY, directory))
                self.assertEqual(newer["suites"]["boolean.constants"]["sha256"],stable)
                self.assertEqual(newer["integer_max"],9)
                for family in select_families("type:integer"):
                    self.assertEqual(newer["suites"][family]["dependency_state"][
                                     "type:integer"],9)

    def test_integer_suite_is_immutable_between_explicit_regeneration_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            first = regenerate(self.parity, LEGACY, directory,
                               selector="type:integer", seed=12, count=28)
            current = (directory / "current.json").read_bytes()
            repeat = regenerate(self.parity, LEGACY, directory,
                                selector="type:integer", seed=12, count=28)
            self.assertEqual(first,repeat)
            self.assertEqual(current,(directory / "current.json").read_bytes())
            changed = regenerate(self.parity, LEGACY, directory,
                                 selector="type:integer", seed=13, count=28)
            self.assertNotEqual(first["release_sha256"],changed["release_sha256"])
            self.assertTrue((directory / "releases" / first["release_sha256"]).exists())

    def test_generated_eval_rows_never_expose_a_train_source_under_eval_partition(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            manifest = regenerate(self.parity, LEGACY, directory,
                                  selector="type:integer", seed=3, count=45)
            root=directory / "releases" / manifest["release_sha256"]
            owners={}
            for suite in manifest["suites"].values():
                data=json.loads((root / suite["artifact"]).read_text())
                for case in data["cases"]:
                    self.assertEqual(owners.setdefault(case["source_id"],
                                           case["partition"]),case["partition"])
                    self.assertIn(case["partition"],("development","sealed_proposed"))

    def test_readback_fails_if_a_generated_expectation_is_tampered(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            manifest=regenerate(self.parity,LEGACY,directory,
                                selector="type:integer",seed=97,count=32)
            root=directory / "releases" / manifest["release_sha256"]
            filename=root / manifest["suites"]["integer.truth"]["artifact"]
            filename.write_text(filename.read_text()+"\nCORRUPTED")
            with self.assertRaisesRegex(ValueError,"SEMANTIC_TEST_INTEGRITY"):
                check_generated(self.parity,LEGACY,directory)

    def test_nonselected_suite_is_preserved_at_byte_level(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            first=regenerate(self.parity,LEGACY,directory,selector="all",
                             seed=400,count=35)
            old=(directory / "releases" / first["release_sha256"] /
                 first["suites"]["boolean.constants"]["artifact"]).read_bytes()
            later=regenerate(self.parity,LEGACY,directory,
                             selector="family:integer.direct",seed=401,count=35)
            actual=(directory / "releases" / later["release_sha256"] /
                    later["suites"]["boolean.constants"]["artifact"]).read_bytes()
            self.assertEqual(old,actual)

    def test_existing_local_generated_suites_never_silently_use_old_integer_bound(self):
        if (ROOT / "current.json").exists():
            self.assertTrue(check_generated(self.parity,LEGACY,ROOT))


if __name__ == "__main__":
    import unittest
    unittest.main()
