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


def _fixture_rows(*, capability, seed, each, **_):
    return tuple({
        "id": f"{capability}:{seed}:{index}",
        "capability": capability,
        "gold": "TRUE" if index % 2 else "FALSE",
    } for index in range(each))


def _fixture_check(row, **_):
    return row["gold"] in BINARY


def _boolean_fixture_rows(*, capability, seed, each,
                          profile_parameters=None, **_):
    operators = tuple(
        (profile_parameters or {}).get("operators", BOOLEAN_OPERATORS))
    rows = []
    for index in range(each):
        operator = operators[index % len(operators)]
        if capability == "B.IDBOOLOPS":
            rows.append({
                "id": f"{capability}:{seed}:{index}",
                "capability": capability,
                "answer_kind": "boolean_operator",
                "operator": operator,
                "gold": operator,
            })
        else:
            rows.append({
                "id": f"{capability}:{seed}:{index}",
                "capability": capability,
                "answer_kind": "binary",
                "operator": operator,
                "gold": "TRUE" if index % 2 else "FALSE",
            })
    return tuple(rows)


def _boolean_fixture_check(row, **_):
    if row.get("answer_kind") == "boolean_operator":
        return row.get("gold") in BOOLEAN_OPERATORS
    return row.get("gold") in BINARY


def _synthetic_course(count=7):
    capabilities = tuple(Capability(
        id=f"Z.C{index}", difficulty="fixture", source_anchor="repo:fixture/z",
        taught_roots=(f"z.op.{index}",), examined_roots=(f"z.op.{index}",),
        prerequisites=(), composed_of=(),
        answer_families=(AnswerFamily("binary", BINARY),),
        lesson_generator="fixture.z-generator/v1",
        independent_oracle="fixture.z-oracle/v1",
    ) for index in range(count))
    grade = Grade(
        "Z", capabilities, assessment_sha256="a" * 64,
        exam_item_counts=tuple((cap.id, 4) for cap in capabilities))
    return Course((grade,), "fixture.z/v1", "b" * 64, "a" * 64)


def _synthetic_registry():
    descriptor = SourceAdapter(
        "fixture.z-adapter/v1", "fixture.z-generator/v1",
        ("fixture.z-oracle/v1",), "d" * 64)
    return SourceAdapterRegistry((
        RegisteredSourceAdapter(descriptor, _fixture_rows, _fixture_check),
    ))


def _synthetic_boolean_course():
    a_caps = tuple(Capability(
        id=f"A.C{index}", difficulty="fixture-a", source_anchor="repo:fixture/a",
        taught_roots=(f"a.op.{index}",), examined_roots=(f"a.op.{index}",),
        prerequisites=(), composed_of=(),
        answer_families=(AnswerFamily("binary", BINARY),),
        lesson_generator="fixture.a-generator/v1",
        independent_oracle="fixture.a-oracle/v1",
    ) for index in range(6))
    grade_a = Grade(
        "A", a_caps, assessment_sha256="1" * 64,
        exam_item_counts=tuple((cap.id, 12) for cap in a_caps))
    names = (
        "B.NOT", "B.AND", "B.OR", "B.XOR", "B.IMPLIES", "B.IFF",
        "B.COMPOSITE", "B.IDBOOLOPS",
    )
    b_caps = tuple(Capability(
        id=name, difficulty="fixture-b", source_anchor="repo:fixture/b",
        taught_roots=(f"b.op.{index}",), examined_roots=(f"b.op.{index}",),
        prerequisites=("A.C0", "A.C1"), composed_of=(),
        answer_families=(
            (AnswerFamily("boolean_operator", BOOLEAN_OPERATORS),)
            if name == "B.IDBOOLOPS"
            else (AnswerFamily("binary", BINARY),)
        ),
        lesson_generator="fixture.b-generator/v1",
        independent_oracle="fixture.b-oracle/v1",
    ) for index, name in enumerate(names))
    grade_b = Grade(
        "B", b_caps, assessment_sha256="2" * 64,
        exam_item_counts=tuple((cap.id, 12) for cap in b_caps),
        teaching_stages=(
            names[:6],
            ("B.COMPOSITE",),
            ("B.IDBOOLOPS",),
        ))
    course = Course(
        (grade_a, grade_b), "fixture.a-b/v1",
        source_attestation_sha256="3" * 64,
        assessment_manifest_sha256="2" * 64)
    registry = SourceAdapterRegistry((
        RegisteredSourceAdapter(SourceAdapter(
            "fixture.a-adapter/v1", "fixture.a-generator/v1",
            ("fixture.a-oracle/v1",), "4" * 64), _fixture_rows, _fixture_check),
        RegisteredSourceAdapter(SourceAdapter(
            "fixture.b-adapter/v1", "fixture.b-generator/v1",
            ("fixture.b-oracle/v1",), "5" * 64,
            profile_dimensions=(("operators", BOOLEAN_OPERATORS),)),
            _boolean_fixture_rows, _boolean_fixture_check),
    ))
    return course, registry


class ExecutionPlanTests(unittest.TestCase):
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

    def test_profile_cannot_leave_active_grade_after_disabled_prefix(self):
        course, registry = _synthetic_boolean_course()
        with self.assertRaisesRegex(
                ValueError,
                "FACTORY_PROFILE_ACTIVE_GRADE_AFTER_DISABLED_GRADE:B"):
            compile_execution_plan(
                course,
                CurriculumProfile(
                    "invalid-gap",
                    grades=(GradeProfile("A", enabled_capabilities=()),)),
                registry)

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


if __name__ == "__main__":
    unittest.main()
