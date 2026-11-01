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

from bilqis_mlx.paths import LEGACY_SOURCE

LEGACY = LEGACY_SOURCE


class TestOnDemandRegeneration(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parity = build_plan(LEGACY)

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
