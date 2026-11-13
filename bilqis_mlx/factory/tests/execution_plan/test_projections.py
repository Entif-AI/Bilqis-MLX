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
    def test_constructor_and_answer_domain_mutation_changes_only_dependent_projections(self):
        course, registry = _synthetic_boolean_course()
        baseline = compile_execution_plan(
            course, CurriculumProfile.full(), registry)
        profiled = compile_execution_plan(
            course,
            CurriculumProfile(
                "id-domain-narrowing",
                grades=(GradeProfile(
                    "B",
                    capabilities=(CapabilityProfile(
                        "B.IDBOOLOPS",
                        provider_parameters=(("operators", ("AND", "IFF")),),
                        answer_family_values=(
                            ("boolean_operator", ("AND", "IFF")),),
                    ),),
                ),),
            ),
            registry,
        )

        delta = diff_execution_plans(baseline, profiled)
        self.assertEqual(delta.added_capabilities, ())
        self.assertEqual(delta.removed_capabilities, ())
        self.assertEqual(delta.changed_capabilities, ("B.IDBOOLOPS",))
        self.assertEqual(delta.revised_grades, ("B",))
        self.assertEqual(
            set(delta.projection_changes),
            {"assessment", "source", "answer_schema"})
    def test_stage_mutation_changes_schedule_only(self):
        course, registry = _synthetic_boolean_course()
        baseline = compile_execution_plan(
            course, CurriculumProfile.full(), registry)
        grade_b = course.grades[1]
        mutated_course = replace(
            course,
            grades=(course.grades[0], replace(
                grade_b,
                teaching_stages=(
                    ("B.NOT", "B.AND"),
                    ("B.OR", "B.XOR"),
                    ("B.IMPLIES", "B.IFF"),
                    ("B.COMPOSITE",),
                    ("B.IDBOOLOPS",),
                ))))
        staged = compile_execution_plan(
            mutated_course,
            CurriculumProfile.full(),
            registry,
        )
        lineage = PlanLineage.from_semantic_catalogs(
            baseline, staged, ("token-0",), ("token-0",))
        delta = diff_execution_plans(
            baseline, staged, lineage=lineage)
        self.assertEqual(
            set(delta.changed_capabilities),
            {"B.OR", "B.XOR", "B.IMPLIES", "B.IFF",
             "B.COMPOSITE", "B.IDBOOLOPS"})
        self.assertEqual(set(delta.projection_changes), {"schedule"})
    def test_prerequisite_mutation_changes_schedule_projection_only(self):
        course, registry = _synthetic_boolean_course()
        baseline = compile_execution_plan(
            course, CurriculumProfile.full(), registry)
        grade = course.grades[1]
        mutated_cap = replace(
            grade.capabilities[-1],
            prerequisites=("A.C0", "A.C1", "A.C2"))
        mutated_grade = replace(
            grade, capabilities=(*grade.capabilities[:-1], mutated_cap))
        mutated_course = replace(
            course, grades=(course.grades[0], mutated_grade))
        mutated = compile_execution_plan(
            mutated_course, CurriculumProfile.full(), registry)
        lineage = PlanLineage.from_semantic_catalogs(
            baseline, mutated, ("token-0",), ("token-0",))
        delta = diff_execution_plans(
            baseline, mutated, lineage=lineage)
        self.assertEqual(delta.changed_capabilities, ("B.IDBOOLOPS",))
        self.assertEqual(set(delta.projection_changes), {"schedule"})
