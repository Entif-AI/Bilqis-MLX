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
    def test_profile_cannot_disable_required_earlier_capabilities(self):
        course, registry = _synthetic_boolean_course()
        with self.assertRaisesRegex(
                ValueError,
                "FACTORY_PROFILE_DISABLED_PREREQUISITE:B.NOT"):
            compile_execution_plan(
                course,
                CurriculumProfile(
                    "invalid-gap",
                    grades=(GradeProfile("A", enabled_capabilities=()),)),
                registry)
    def test_jit_profile_can_skip_unrelated_inactive_grade(self):
        from bilqis_mlx.factory.curriculum_definition import (
            from_legacy_course, GradeSpec, CapabilitySourceBinding,
        )
        from bilqis_mlx.factory.tests.test_executable_release import _boolean_answers
        course, registry = _synthetic_boolean_course()
        curriculum, bindings = from_legacy_course(course)
        cap = replace(curriculum.grades[0].capabilities[0],
                      capability_id="D.COPULAR_IDENTITY", prerequisites=("A.C0",))
        curriculum = replace(curriculum, grades=(*curriculum.grades,
            GradeSpec("D", (cap,), ((cap.capability_id, 12),), ((cap.capability_id,),))))
        source = bindings.bindings[0]
        bindings = replace(bindings, bindings=(*bindings.bindings,
            CapabilitySourceBinding(cap.capability_id, source.source_anchor,
                                    source.generator_id, source.oracle_id)))
        plan = compile_execution_plan(curriculum, CurriculumProfile("thin-jit", grades=(
            GradeProfile("B", enabled_capabilities=()),)), registry,
            source_bindings=bindings, answer_registry=_boolean_answers())
        self.assertEqual(tuple(g.grade_id for g in plan.grades), ("A", "D"))
        self.assertEqual(plan.grades[-1].cumulative_scope,
                         (*plan.grades[0].capabilities, "D.COPULAR_IDENTITY"))
    def test_profile_cannot_invent_capability_or_answer_value(self):
        course = _synthetic_course(6)
        registry = _synthetic_registry()
        with self.assertRaisesRegex(ValueError, "CAPABILITY_OUTSIDE_GRADE"):
            compile_execution_plan(
                course,
                CurriculumProfile("bad", grades=(GradeProfile(
                    "Z", enabled_capabilities=("Z.C0", "Z.MADE_UP"),
                ),)),
                registry,
            )
        with self.assertRaisesRegex(
                ValueError, "ANSWER_VALUES_NOT_CANONICAL_SUBSET"):
            compile_execution_plan(
                course,
                CurriculumProfile("bad-answer", grades=(GradeProfile(
                    "Z", capabilities=(CapabilityProfile(
                        "Z.C0",
                        answer_family_values=(("binary", ("TRUE", "MAYBE")),),
                    ),),
                ),)),
                registry,
            )
    def test_profile_cannot_invent_provider_dimension_or_values(self):
        course, registry = _synthetic_boolean_course()
        with self.assertRaisesRegex(ValueError, "PROVIDER_DIMENSION_UNDECLARED"):
            compile_execution_plan(
                course,
                CurriculumProfile("bad-dimension", grades=(GradeProfile(
                    "B", capabilities=(CapabilityProfile(
                        "B.COMPOSITE",
                        provider_parameters=(("made_up", ("x",)),)),),
                ),)),
                registry,
            )
    def test_profile_must_keep_declared_prerequisites_executable(self):
        course, registry = _synthetic_boolean_course()
        with self.assertRaisesRegex(ValueError, "DISABLED_PREREQUISITE:B.NOT"):
            compile_execution_plan(
                course,
                CurriculumProfile(
                    "dangling-prerequisite",
                    grades=(GradeProfile(
                        "A",
                        enabled_capabilities=(
                            "A.C0", "A.C2", "A.C3", "A.C4", "A.C5"),
                    ),),
                ),
                registry,
            )
        with self.assertRaisesRegex(
                ValueError, "PROVIDER_VALUES_NOT_CANONICAL_SUBSET"):
            compile_execution_plan(
                course,
                CurriculumProfile("bad-values", grades=(GradeProfile(
                    "B", capabilities=(CapabilityProfile(
                        "B.COMPOSITE",
                        provider_parameters=(("operators", ("IFF", "AND")),)),),
                ),)),
                registry,
            )
