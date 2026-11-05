from dataclasses import replace
import unittest

from bilqis_mlx.curriculum import (
    AnswerFamily, BINARY, BOOLEAN_OPERATORS, Capability, Course, Grade,
)
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from bilqis_mlx.factory.execution import (
    CapabilityProfile, CurriculumProfile, GradeProfile, PlanLineage,
    compile_execution_plan, diff_execution_plans,
)
from bilqis_mlx.factory.generation import draw_execution_rows
from bilqis_mlx.factory.model import SourceAdapter
from bilqis_mlx.factory.tests.execution_plan.fixtures import (
    _fixture_rows,
    _fixture_check,
    _boolean_fixture_rows,
    _boolean_fixture_check,
    _synthetic_course,
    _synthetic_registry,
    _synthetic_boolean_course,
)


class ExecutionPlanTests(unittest.TestCase):
    def test_semantic_curriculum_change_requires_lineage_and_classifies_model_geometry(self):
        course, registry = _synthetic_boolean_course()
        previous = compile_execution_plan(
            course, CurriculumProfile.full(), registry)
        grade = course.grades[1]
        changed_capability = replace(
            grade.capabilities[-1],
            prerequisites=("A.C0", "A.C1", "A.C2"))
        changed_grade = replace(
            grade,
            capabilities=(*grade.capabilities[:-1], changed_capability))
        changed_course = replace(
            course, grades=(course.grades[0], changed_grade))
        current = compile_execution_plan(
            changed_course, CurriculumProfile.full(), registry)
        self.assertNotEqual(
            previous.curriculum_sha256, current.curriculum_sha256)
        with self.assertRaisesRegex(ValueError, "LINEAGE_REQUIRED"):
            diff_execution_plans(previous, current)

        unchanged = PlanLineage.from_semantic_catalogs(
            previous, current, ("a", "b"), ("a", "b"))
        delta = diff_execution_plans(
            previous, current, lineage=unchanged)
        self.assertEqual(delta.semantic_geometry, "UNCHANGED")

        expanded = PlanLineage.from_semantic_catalogs(
            previous, current, ("a", "b"), ("a", "b", "c"))
        delta = diff_execution_plans(
            previous, current, lineage=expanded)
        self.assertEqual(delta.semantic_geometry, "APPEND_ONLY_EXPANSION")

        incompatible = PlanLineage.from_semantic_catalogs(
            previous, current, ("a", "b"), ("b", "a"))
        delta = diff_execution_plans(
            previous, current, lineage=incompatible)
        self.assertEqual(delta.semantic_geometry, "INCOMPATIBLE")
    def test_same_curriculum_can_expand_semantic_geometry(self):
        course, registry = _synthetic_boolean_course()
        previous = compile_execution_plan(
            course, CurriculumProfile.full(), registry)
        current = compile_execution_plan(
            course, CurriculumProfile.full(), registry)
        lineage = PlanLineage.from_semantic_catalogs(
            previous, current, ("a", "b"), ("a", "b", "c"))
        delta = diff_execution_plans(
            previous, current, lineage=lineage)
        self.assertEqual(
            delta.semantic_geometry, "APPEND_ONLY_EXPANSION")
