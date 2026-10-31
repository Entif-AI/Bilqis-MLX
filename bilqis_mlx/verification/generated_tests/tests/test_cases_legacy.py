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
