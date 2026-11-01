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
