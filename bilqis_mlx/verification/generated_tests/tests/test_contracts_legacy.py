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

    def test_integer_type_rebuilds_every_dependent_family_but_not_unrelated_boolean(self):
        for kind in ("type:integer", "type:boolean"):
            self.assertEqual(set(select_families(kind)),
                             {f.name for f in FAMILIES if kind in f.dependencies})
        self.assertTrue({"integer.direct", "integer.truth", "integer.equivalence",
                         "integer.inverse_negation"} <= set(select_families("type:integer")))
        self.assertNotIn("boolean.constants",select_families("type:integer"))
        with self.assertRaisesRegex(ValueError, "SEMANTIC_TEST_SELECTOR"):
            select_families("type:imaginary")

    def test_existing_local_generated_suites_never_silently_use_old_integer_bound(self):
        if (ROOT / "current.json").exists():
            self.assertTrue(check_generated(self.parity,LEGACY,ROOT))
