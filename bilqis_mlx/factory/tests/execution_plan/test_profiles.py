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
    def test_boolean_kernel_is_profile_data_not_a_minimal_release_or_provider(self):
        course, registry = _synthetic_boolean_course()
        full = compile_execution_plan(
            course, CurriculumProfile.full(), registry)
        profile = CurriculumProfile(
            "boolean-kernel/and-iff",
            grades=(GradeProfile(
                "B",
                enabled_capabilities=(
                    "B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"),
                capabilities=(
                    CapabilityProfile(
                        "B.COMPOSITE",
                        provider_parameters=(("operators", ("AND", "IFF")),)),
                    CapabilityProfile(
                        "B.IDBOOLOPS",
                        provider_parameters=(("operators", ("AND", "IFF")),),
                        answer_family_values=(("boolean_operator", ("AND", "IFF")),)),
                ),
            ),),
        )
        kernel = compile_execution_plan(course, profile, registry)

        self.assertEqual(
            kernel.grade_map["B"].capabilities,
            ("B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"))
        self.assertEqual(
            kernel.grade_map["B"].teaching_stages,
            (("B.AND", "B.IFF"), ("B.COMPOSITE",), ("B.IDBOOLOPS",)))
        self.assertEqual(
            kernel.capability_map["B.COMPOSITE"].provider_parameters,
            (("operators", ("AND", "IFF")),))
        id_family = kernel.capability_map["B.IDBOOLOPS"].answer_families
        self.assertEqual(
            tuple((family.kind, family.values) for family in id_family),
            (("boolean_operator", ("AND", "IFF")),))
        self.assertEqual(
            sum(cap.exam_item_count for cap in kernel.capabilities
                if cap.grade_id == "B"),
            48)
        self.assertEqual(
            kernel.grade_map["B"].cumulative_scope,
            tuple(cap.capability_id for cap in kernel.capabilities))
        rows = draw_execution_rows(
            None, {}, course, kernel, registry, seed=41)
        b_rows = [row for row in rows if row["capability"].startswith("B.")]
        self.assertEqual(len(b_rows), 48)
        composite = [row for row in b_rows if row["capability"] == "B.COMPOSITE"]
        identified = [row for row in b_rows if row["capability"] == "B.IDBOOLOPS"]
        self.assertEqual({row["operator"] for row in composite}, {"AND", "IFF"})
        self.assertEqual({row["operator"] for row in identified}, {"AND", "IFF"})
        self.assertEqual({row["gold"] for row in identified}, {"AND", "IFF"})

        delta = diff_execution_plans(full, kernel)
        self.assertEqual(
            set(delta.removed_capabilities),
            {"B.NOT", "B.OR", "B.XOR", "B.IMPLIES"})
        self.assertEqual(delta.added_capabilities, ())
        self.assertEqual(delta.revised_grades, ("B",))
        self.assertEqual(
            set(delta.projection_changes),
            {"roster", "schedule", "assessment", "source", "answer_schema",
             "coverage", "teaching"})
        full_nodes = {
            item.capability_id: item
            for item in full.capability_projection_digests}
        kernel_nodes = {
            item.capability_id: item
            for item in kernel.capability_projection_digests}
        for capability in (
                "A.C0", "A.C1", "A.C2", "A.C3", "A.C4", "A.C5"):
            self.assertEqual(full_nodes[capability], kernel_nodes[capability])
    def test_profile_can_disable_future_grade_as_canonical_prefix(self):
        course, registry = _synthetic_boolean_course()
        plan = compile_execution_plan(
            course,
            CurriculumProfile(
                "a-only",
                grades=(GradeProfile("B", enabled_capabilities=()),)),
            registry)

        self.assertEqual(
            tuple(grade.grade_id for grade in plan.grades),
            ("A",))
        self.assertEqual(
            {item.grade_id for item in plan.capabilities},
            {"A"})
