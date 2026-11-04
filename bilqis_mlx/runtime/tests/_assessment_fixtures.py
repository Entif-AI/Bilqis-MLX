"""Shared fixtures for current/historical assessment lifecycle tests."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.runtime.assessment import (
    _candidate_cohort, _generalization_cohort, _grade_test_cohort, _promotion_cohort,
    load_championship_cohort,
)
from bilqis_mlx.generated_assessment import make_cohort
from bilqis_mlx.trainer import choose_lesson_batch
from bilqis_mlx.live_grade_a import live_course
from bilqis_mlx.curriculum.scheduler import start_new

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "vendor" / "legacy-v16"

class BaseGradeAssessmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        cls.course = live_course(accepted_grade_a(cls.manifest))
        _, _, cls.graph, _, _ = read_sources(SOURCE)

    def receipt(self):
        school = start_new(self.course, Checkpoint("a" * 64, "bundles/inert", 7, True))
        return {"school": asdict(school), "generation": 1, "run_id": "classroom-fixture",
                "source_manifest_sha256": self.manifest["manifest_sha256"]}

    def draw(self, root, receipt):
        return _grade_test_cohort(root, receipt, self.manifest, self.course, SOURCE, self.graph)

__all__ = [name for name in globals() if not name.startswith("__")]
