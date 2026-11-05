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
    def test_twelve_capability_v2_plan_preserves_legacy_cardinality(self):
        from bilqis_mlx.curriculum import validate
        from bilqis_mlx.factory.curriculum_definition import (
            CapabilitySpec, CapabilitySourceBinding, CurriculumDefinition,
            GradeSpec, SourceBindingSet, validate_curriculum_definition,
        )
        from bilqis_mlx.factory.tests.test_executable_release import _boolean_answers

        names = tuple(f"Z.C{i}" for i in range(12))
        capabilities = tuple(CapabilitySpec(
            name, "fixture", (f"z.op.{i}",), (f"z.op.{i}",),
            (names[i - 1],) if i else (), (),
            (AnswerFamily("binary", BINARY),),
        ) for i, name in enumerate(names))
        curriculum = CurriculumDefinition("fixture.twelve/v1", (GradeSpec(
            "Z", capabilities, tuple((name, 4) for name in names),
            tuple((name,) for name in names)),))
        bindings = SourceBindingSet(tuple(CapabilitySourceBinding(
            name, "repo:fixture/z", "fixture.z-generator/v1", "fixture.z-oracle/v1",
        ) for name in names), "b" * 64)
        validate_curriculum_definition(curriculum, answer_kinds=("binary",))
        plan = compile_execution_plan(
            curriculum, CurriculumProfile.full(), _synthetic_registry(),
            source_bindings=bindings, answer_registry=_boolean_answers())
        self.assertEqual(plan.grades[0].capabilities, names)
        self.assertEqual(plan.grades[0].cumulative_scope, names)
        self.assertEqual(tuple(cap.capability_id for cap in plan.capabilities), names)
        self.assertEqual(sum(cap.exam_item_count for cap in plan.capabilities), 48)
        self.assertEqual(plan.grades[0].teaching_stages, tuple((name,) for name in names))
        self.assertEqual(tuple(item.capability_id for item in plan.capability_projection_digests), names)
        for index, capability in enumerate(plan.capabilities):
            with self.subTest(capability=capability.capability_id):
                self.assertEqual(capability.stage, index)
                self.assertEqual(capability.prerequisites, (names[index - 1],) if index else ())
                self.assertEqual(capability.source_anchor, "repo:fixture/z")
                self.assertEqual(capability.provider_id, "fixture.z-adapter/v1")
                self.assertEqual(capability.oracle_id, "fixture.z-oracle/v1")
        changed_bindings = replace(bindings, bindings=(
            *bindings.bindings[:-1],
            replace(bindings.bindings[-1], source_anchor="repo:fixture/z/revised")))
        changed = compile_execution_plan(
            curriculum, CurriculumProfile.full(), _synthetic_registry(),
            source_bindings=changed_bindings, answer_registry=_boolean_answers())
        self.assertEqual(changed.capability_projection_digests[:-1],
                         plan.capability_projection_digests[:-1])
        self.assertNotEqual(changed.capability_projection_digests[-1].source,
                            plan.capability_projection_digests[-1].source)
        self.assertEqual(changed.capability_projection_digests[-1].schedule,
                         plan.capability_projection_digests[-1].schedule)
        with self.assertRaisesRegex(ValueError, "^GRADE_CAPABILITY_COUNT_OUTSIDE_SIX_TO_NINE$"):
            validate(_synthetic_course(10))
    def test_profile_roster_mutation_regenerates_all_static_runtime_projections(self):
        course = _synthetic_course(7)
        registry = _synthetic_registry()
        full = compile_execution_plan(course, CurriculumProfile.full(), registry)
        reduced = compile_execution_plan(
            course,
            CurriculumProfile("z-six", grades=(GradeProfile(
                "Z", enabled_capabilities=tuple(
                    cap.id for cap in course.grades[0].capabilities[:6]),
            ),)),
            registry,
        )

        self.assertEqual(len(full.capabilities), 7)
        self.assertEqual(len(reduced.capabilities), 6)
        self.assertEqual(reduced.grades[0].capabilities,
                         tuple(cap.id for cap in course.grades[0].capabilities[:6]))
        self.assertEqual(sum(cap.exam_item_count for cap in reduced.capabilities), 24)

        delta = diff_execution_plans(full, reduced)
        self.assertEqual(delta.removed_capabilities, ("Z.C6",))
        self.assertEqual(delta.added_capabilities, ())
        self.assertEqual(delta.revised_grades, ("Z",))
        self.assertEqual(
            set(delta.projection_changes),
            {"roster", "schedule", "assessment", "source", "answer_schema",
             "coverage", "teaching"})
