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
    def test_source_binding_mutation_changes_source_projection_only(self):
        course = _synthetic_course(6)
        baseline_registry = _synthetic_registry()
        baseline = compile_execution_plan(
            course, CurriculumProfile.full(), baseline_registry)
        grade = course.grades[0]
        mutated_cap = replace(
            grade.capabilities[-1],
            lesson_generator="fixture.z-generator-v2/v1",
            independent_oracle="fixture.z-oracle-v2/v1")
        mutated_grade = replace(
            grade, capabilities=(*grade.capabilities[:-1], mutated_cap))
        mutated_course = replace(course, grades=(mutated_grade,))
        original = SourceAdapter(
            "fixture.z-adapter/v1", "fixture.z-generator/v1",
            ("fixture.z-oracle/v1",), "d" * 64)
        changed = SourceAdapter(
            "fixture.z-adapter-v2/v1", "fixture.z-generator-v2/v1",
            ("fixture.z-oracle-v2/v1",), "e" * 64)
        registry = SourceAdapterRegistry((
            RegisteredSourceAdapter(original, _fixture_rows, _fixture_check),
            RegisteredSourceAdapter(changed, _fixture_rows, _fixture_check),
        ))
        mutated = compile_execution_plan(
            mutated_course, CurriculumProfile.full(), registry)
        self.assertEqual(
            baseline.curriculum_sha256, mutated.curriculum_sha256)
        self.assertNotEqual(
            baseline.source_binding_sha256, mutated.source_binding_sha256)
        delta = diff_execution_plans(baseline, mutated)
        self.assertEqual(delta.changed_capabilities, ("Z.C5",))
        self.assertEqual(set(delta.projection_changes), {"source"})
    def test_source_anchor_mutation_changes_only_affected_source_projection(self):
        course = _synthetic_course(6)
        registry = _synthetic_registry()
        baseline = compile_execution_plan(
            course, CurriculumProfile.full(), registry)
        grade = course.grades[0]
        changed_capability = replace(
            grade.capabilities[-1],
            source_anchor="repo:fixture/z/source-v2")
        changed_course = replace(
            course,
            grades=(replace(
                grade,
                capabilities=(*grade.capabilities[:-1], changed_capability)),),
        )
        mutated = compile_execution_plan(
            changed_course, CurriculumProfile.full(), registry)

        self.assertEqual(
            baseline.curriculum_sha256, mutated.curriculum_sha256)
        self.assertNotEqual(
            baseline.source_binding_sha256, mutated.source_binding_sha256)
        delta = diff_execution_plans(baseline, mutated)
        self.assertEqual(delta.changed_capabilities, ("Z.C5",))
        self.assertEqual(set(delta.projection_changes), {"source"})

        baseline_nodes = {
            item.capability_id: item
            for item in baseline.capability_projection_digests}
        mutated_nodes = {
            item.capability_id: item
            for item in mutated.capability_projection_digests}
        for capability in ("Z.C0", "Z.C1", "Z.C2", "Z.C3", "Z.C4"):
            self.assertEqual(
                baseline_nodes[capability], mutated_nodes[capability])
        self.assertNotEqual(
            baseline_nodes["Z.C5"].source,
            mutated_nodes["Z.C5"].source)
    def test_release_source_metadata_changes_source_not_curriculum_identity(self):
        course = _synthetic_course(6)
        registry = _synthetic_registry()
        previous = compile_execution_plan(
            course, CurriculumProfile.full(), registry)
        mutated = replace(
            course,
            version="fixture.z/v2",
            source_attestation_sha256="c" * 64)
        current = compile_execution_plan(
            mutated, CurriculumProfile.full(), registry)
        self.assertEqual(previous.curriculum_sha256, current.curriculum_sha256)
        self.assertNotEqual(
            previous.source_binding_sha256, current.source_binding_sha256)
        delta = diff_execution_plans(previous, current)
        self.assertEqual(delta.semantic_geometry, "UNCHANGED")
        self.assertEqual(set(delta.projection_changes), {"source"})
