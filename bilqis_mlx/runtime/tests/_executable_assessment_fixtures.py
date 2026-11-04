"""Shared fixtures for executable-v2 assessment tests."""
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bilqis_mlx.curriculum import BOOLEAN_OPERATORS
from bilqis_mlx.factory.assessment import assessment_scope_contract
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.tests.test_executable_consumers import _profile
from bilqis_mlx.factory.tests.test_executable_release import _boolean_answers
from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_boolean_course
from bilqis_mlx.runtime.assessment import (
    _draw_executable_scope_cohort, _generalization_executable_cohort,
    _load_executable_cohort, _persist_executable_cohort,
    _promotion_executable_cohort, _routine_executable_cohort,
    load_championship_cohort,
)
from bilqis_mlx.runtime.admission import _persist_executable_factory_release
from bilqis_mlx.generated_assessment import make_cohort
from bilqis_mlx.trainer import _verify_live_rubric_lineage

class BaseExecutableAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.course, self.registry = _synthetic_boolean_course()
        self.curriculum, self.bindings = from_legacy_course(self.course)
        self.answers = _boolean_answers()
        self.graph = {"tokens": ["fixture.padding", "cogal.value.false",
            "cogal.value.true", *(f"cogal.operator.{value}" for value in BOOLEAN_OPERATORS)]}
        self.full = compile_executable_factory_release(
            self.curriculum, self.bindings, CurriculumProfile.full(), self.registry,
            self.answers, source_root=None, graph=self.graph, verification_seed=47)
        self.reduced = compile_executable_factory_release(
            self.curriculum, self.bindings, _profile(), self.registry, self.answers,
            source_root=None, graph=self.graph, verification_seed=47,
            predecessor=self.full)
        self.manifest = {"manifest_sha256": "c" * 64}
        self.a_scope = tuple(item.capability_id for item in self.full.execution_plan.capabilities
                             if item.grade_id == "A")

    def draw(self, release, scope, seed=53):
        return _draw_executable_scope_cohort(None, self.graph, release, self.registry,
                                             capabilities=scope, seed=seed)

    def receipt(self):
        return {"run_id": "v2-assessment-fixture", "generation": 1,
                "qualification_cohort_v2": None,
                "burned_generalization_cohorts_v2": []}

__all__ = [name for name in globals() if not name.startswith("__")]
