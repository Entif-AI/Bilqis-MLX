from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT.parent / "bilqis-mlx-retention-lab" / "vendor" / "legacy-v16"


LIVE_PROFILE_PROBE = textwrap.dedent(r'''
            from dataclasses import replace
            import hashlib
            import json
            from pathlib import Path

            from bilqis_mlx.boolean_composite import (
                build_course as build_composite, draw_composite)
            from bilqis_mlx.boolean_identification import (
                answer_heads as boolean_answer_heads,
                build_course as build_identification,
                draw_identification)
            from bilqis_mlx.compatibility.executable_projection import (
                legacy_course_for_profile, project_legacy_course,
            )
            from bilqis_mlx.factory.answers import (
                AnswerModality, AnswerModalityRegistry, RegisteredAnswerModality,
                fixed_domain, merge_prefix_domain,
            )
            from bilqis_mlx.factory.curriculum_definition import from_legacy_course
            from bilqis_mlx.factory.execution import (
                CapabilityProfile, CurriculumProfile, GradeProfile,
                compile_execution_plan,
            )
            from bilqis_mlx.factory.executable_release import (
                ExecutableFactoryRelease,
                answer_heads_from_executable_release,
                compile_executable_factory_release,
                compile_successor_profile_release,
            )
            from bilqis_mlx.factory.generation import (
                draw_executable_release_rows, draw_execution_rows,
            )
            from bilqis_mlx.factory.live_releases import (
                boolean_successor, initial_course, minimal_boolean_successor,
            )
            from bilqis_mlx.grade_a_probe import read_sources
            from bilqis_mlx.grade_a_release import accepted_grade_a
            from bilqis_mlx.live_grade_c import registry_graph
            from bilqis_mlx.semantics.abi import HISTORICAL_PREFIX_SIZE
            from bilqis_mlx.source_adapters.school import live_source_registry
            from bilqis_mlx.profiles.catalog import (
                next_numeric_scope_profile, numeric_entry_transition,
            )
            from bilqis_mlx.typed_answer_training import prepare_typed_batches

            root = Path.cwd()
            source = root.parent / "bilqis-mlx-retention-lab" / "vendor" / "legacy-v16"
            manifest = json.loads((
                root / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
            grade_a = initial_course(accepted_grade_a(manifest))
            course = grade_a
            course = boolean_successor(course, source)
            course = build_composite(course, source)
            course = build_identification(course, source)
            grade_b = replace(
                course.grades[-1],
                teaching_stages=(
                    tuple(cap.id for cap in course.grades[-1].capabilities[:6]),
                    ("B.COMPOSITE",),
                    ("B.IDBOOLOPS",),
                ))
            course = replace(course, grades=(course.grades[0], grade_b))
            curriculum, bindings = from_legacy_course(course)
            # Provider source still comes from the pinned legacy source root,
            # while executable semantic identity follows the actual 222-row
            # historical student ABI used by the human trainer.
            read_sources(source)
            registered = registry_graph()
            graph = {
                **registered,
                "tokens": registered["tokens"][:HISTORICAL_PREFIX_SIZE],
                "nodes": registered["nodes"][:HISTORICAL_PREFIX_SIZE],
                "row_contract_sha256": {
                    key: registered["row_contract_sha256"][key]
                    for key in registered["tokens"][:HISTORICAL_PREFIX_SIZE]
                },
            }
            digest = lambda value: hashlib.sha256(json.dumps(
                value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            assert digest(draw_composite(source, graph, seed=2026101902)) == (
                "cb1d95cc8ae92afeedd33e7f1603aa41d75368f70b83ad29a797eef0a6d87a95")
            assert digest(draw_identification(source, graph, seed=2026101902)) == (
                "21c5e1b95a9eaf2bdd1be49f72f4c9bc8a2d35d249349b80439c27ce4318af1e")
            legacy_boolean_heads = boolean_answer_heads(graph)
            assert legacy_boolean_heads["boolean_operator"]["values"] == [
                "NOT", "AND", "OR", "XOR", "IMPLIES", "IFF"]
            assert [
                graph["tokens"][index]
                for index in legacy_boolean_heads["boolean_operator"]["token_ids"]
            ] == [
                "cogal.operator.NOT",
                "cogal.operator.AND",
                "cogal.operator.OR",
                "cogal.operator.XOR",
                "cogal.operator.IMPLIES",
                "cogal.operator.IFF",
            ]
            registry = live_source_registry()
            answers = AnswerModalityRegistry((
                RegisteredAnswerModality(
                    AnswerModality("binary", "answer.binary/v1", "a" * 64),
                    fixed_domain(("FALSE", "TRUE")),
                    lambda value: {
                        "FALSE": "cogal.value.false",
                        "TRUE": "cogal.value.true",
                    }[value]),
                RegisteredAnswerModality(
                    AnswerModality(
                        "boolean_operator", "answer.boolean-operator/v1", "b" * 64),
                    fixed_domain(("NOT", "AND", "OR", "XOR", "IMPLIES", "IFF")),
                    lambda value: "cogal.operator." + value),
                RegisteredAnswerModality(
                    AnswerModality(
                        "numeric_active", "answer.numeric-active/v1", "c" * 64),
                    merge_prefix_domain,
                    lambda value: "school.number." + value),
            ))
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
                                answer_family_values=(
                                    ("boolean_operator", ("AND", "IFF")),)),
                        ),
                    ),),
                )
            plan = compile_execution_plan(
                curriculum,
                profile,
                registry,
                source_bindings=bindings,
                answer_registry=answers,
            )
            assert "source.micro.boolean-minimal/v1" not in {
                cap.provider_id for cap in plan.capabilities}
            assert plan.grade_map["B"].teaching_stages == (
                ("B.AND", "B.IFF"), ("B.COMPOSITE",), ("B.IDBOOLOPS",))

            rows = []
            for capability in plan.grade_map["B"].capabilities:
                rows.extend(draw_execution_rows(
                    source, graph, curriculum, plan, registry,
                    source_bindings=bindings,
                    seed=20261019, capability=capability))
            assert len(rows) == 48
            assert {row["capability"] for row in rows} == {
                "B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"}
            composite = [row for row in rows if row["capability"] == "B.COMPOSITE"]
            identified = [row for row in rows if row["capability"] == "B.IDBOOLOPS"]
            assert {operator for row in composite for operator in row["operators"]} == {
                "AND", "IFF"}
            assert {row["gold"] for row in identified} == {"AND", "IFF"}
            assert all(tuple(row["operator_options"]) == ("AND", "IFF")
                       for row in identified)

            release = compile_executable_factory_release(
                curriculum, bindings, profile, registry, answers,
                source_root=source, graph=graph, verification_seed=2026101903)
            assert release.execution_plan == plan
            assert "source.micro.boolean-minimal/v1" not in {
                cap.provider_id for cap in release.execution_plan.capabilities}
            assert release.verification.assessments[-1].cumulative_scope == (
                *tuple(cap.id for cap in course.grades[0].capabilities),
                "B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS")
            assert release.verification.assessments[-1].seal_sha256 != (
                plan.grade_map["B"].assessment_blueprint_sha256)
            restored = ExecutableFactoryRelease.from_manifest(
                json.loads(json.dumps(release.manifest())),
                release.release_sha256)
            assert restored == release

            release_rows = []
            for capability in release.execution_plan.grade_map["B"].capabilities:
                release_rows.extend(draw_executable_release_rows(
                    source, graph, release, registry,
                    legacy_course=course, seed=20261019,
                    capability=capability))
            assert release_rows == rows
            release_heads = answer_heads_from_executable_release(
                release, graph)
            assert release_heads["boolean_operator"]["values"] == ["AND", "IFF"]
            typed = prepare_typed_batches(
                [row for row in release_rows
                 if row["capability"] == "B.IDBOOLOPS"],
                release_heads)
            assert typed["boolean_operator"]["gold_labels"]
            assert set(typed["boolean_operator"]["gold_labels"]) == {
                "AND", "IFF"}

            historical_minimal = minimal_boolean_successor(grade_a, source)
            a_curriculum, a_bindings, a_profile, a_canonical = (
                project_legacy_course(
                    grade_a, grade_a, source,
                    answer_kinds=answers.kinds))
            assert a_profile.grades[0].enabled_capabilities == ()
            assert tuple(grade.grade_id for grade in a_curriculum.grades) == (
                "A", "B", "C")
            a_plan = compile_execution_plan(
                a_curriculum, a_profile, registry,
                source_bindings=a_bindings,
                answer_registry=answers)
            assert tuple(grade.grade_id for grade in a_plan.grades) == ("A",)

            projected_curriculum, projected_bindings, projected_profile, projected_course = (
                project_legacy_course(
                    historical_minimal, grade_a, source,
                    answer_kinds=answers.kinds))
            assert projected_curriculum.digest() == a_curriculum.digest()
            assert projected_bindings.digest() == a_bindings.digest()
            assert tuple(
                cap.capability_id
                for cap in projected_curriculum.grades[1].capabilities
            ) == (
                "B.NOT", "B.AND", "B.OR", "B.XOR",
                "B.IMPLIES", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS")
            assert projected_profile.grades[0].enabled_capabilities == (
                "B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS")
            projected_plan = compile_execution_plan(
                projected_curriculum, projected_profile, registry,
                source_bindings=projected_bindings,
                answer_registry=answers)
            assert tuple(
                projected_plan.grade_map["B"].capabilities
            ) == ("B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS")
            assert "source.micro.boolean-minimal/v1" not in {
                cap.provider_id for cap in projected_plan.capabilities}
            projected_release = compile_executable_factory_release(
                projected_curriculum, projected_bindings, projected_profile,
                registry, answers, source_root=source, graph=graph,
                verification_seed=2026101904)
            assert projected_release.execution_plan == projected_plan

            numeric_transition = numeric_entry_transition(
                projected_release, graph,
                full_boolean=False, maximum=3)
            numeric_course = legacy_course_for_profile(
                grade_a, source, numeric_transition.profile)
            numeric_release = compile_successor_profile_release(
                projected_release,
                numeric_transition.profile,
                registry,
                answers,
                source_root=source,
                graph=numeric_transition.graph,
                verification_seed=2026101905)
            assert numeric_release.transition.semantic_geometry == (
                "APPEND_ONLY_EXPANSION")
            assert tuple(
                grade.grade_id
                for grade in numeric_release.execution_plan.grades
            ) == ("A", "B", "C")
            assert numeric_release.execution_plan.grade_map["C"].capabilities == (
                "C.COUNT", "C.NUMBER", "C.SUCCESSOR", "C.ADD", "C.SUB")
            numeric_heads = answer_heads_from_executable_release(
                numeric_release, numeric_transition.graph)
            assert numeric_heads["numeric_active"]["values"] == [
                "0", "1", "2", "3"]
            numeric_rows = []
            for capability in numeric_release.execution_plan.grade_map["C"].capabilities:
                numeric_rows.extend(draw_executable_release_rows(
                    source, numeric_transition.graph, numeric_release, registry,
                    legacy_course=numeric_course,
                    seed=20261019,
                    capability=capability))
            assert numeric_rows
            assert all(
                row["gold"] in {"0", "1", "2", "3"}
                for row in numeric_rows
                if row.get("answer_kind") == "numeric_active")
            assert "source.micro.boolean-minimal/v1" not in {
                cap.provider_id
                for cap in numeric_release.execution_plan.capabilities}

            next_numeric = next_numeric_scope_profile(numeric_release)
            assert next_numeric is not None
            next_numeric_course = legacy_course_for_profile(
                grade_a, source, next_numeric)
            numeric_four = compile_successor_profile_release(
                numeric_release,
                next_numeric,
                registry,
                answers,
                source_root=source,
                graph=numeric_transition.graph,
                verification_seed=2026101906)
            assert numeric_four.transition.semantic_geometry == "UNCHANGED"
            assert answer_heads_from_executable_release(
                numeric_four, numeric_transition.graph
            )["numeric_active"]["values"] == ["0", "1", "2", "3", "4"]
            from bilqis_mlx.factory.schedule import (
                schedule_program_from_executable_release,
            )
            assert (
                schedule_program_from_executable_release(numeric_four).digest()
                != schedule_program_from_executable_release(numeric_release).digest()
            )
            print("LIVE_PROFILE_EXECUTION_OK")
''')


def _run_live_profile_probe():
    return subprocess.run(
        [sys.executable, "-B", "-c", LIVE_PROFILE_PROBE], cwd=ROOT,
        capture_output=True, text=True, check=False)


class TwelveCapabilityProviderTests(unittest.TestCase):
    def test_registered_providers_generate_every_direct_v2_capability(self):
        from functools import partial
        from bilqis_mlx.curriculum import AnswerFamily, BINARY
        from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
        from bilqis_mlx.factory.curriculum_definition import (
            CapabilitySpec, CapabilitySourceBinding, CurriculumDefinition, GradeSpec, SourceBindingSet)
        from bilqis_mlx.factory.executable_release import compile_executable_factory_release
        from bilqis_mlx.factory.execution import CurriculumProfile, GradeProfile
        from bilqis_mlx.factory.generation import draw_executable_release_rows, draw_execution_rows
        from bilqis_mlx.factory.model import SourceAdapter
        from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
        from bilqis_mlx.factory.tests.test_executable_release import _answers

        calls, checks = [], []
        def draw(provider, *, capability, seed, each, course, **_):
            calls.append((provider, capability, course))
            return tuple({"id": f"{capability}:{seed}:{i}", "capability": capability,
                          "provider": provider, "value": (seed + i) % 2,
                          "gold": BINARY[(seed + i) % 2]} for i in range(each))
        def check(provider, row, *, course, **_):
            self.assertIs(course, expected_context)
            checks.append((provider, row["capability"]))
            return row["provider"] == provider and row["gold"] == (
                "TRUE" if row["value"] else "FALSE")
        registry = SourceAdapterRegistry(tuple(RegisteredSourceAdapter(
            SourceAdapter(f"fixture.provider.{i}", f"fixture.generator.{i}",
                          (f"fixture.oracle.{i}",), str(i + 1) * 64),
            partial(draw, i), partial(check, i)) for i in range(2)))
        names = tuple(f"Z.C{i}" for i in range(12))
        curriculum = CurriculumDefinition("fixture.twelve/v1", (GradeSpec("Z", tuple(
            CapabilitySpec(name, "fixture", (f"root.{i}",), (f"root.{i}",), (), (),
                           (AnswerFamily("binary", BINARY),)) for i, name in enumerate(names)),
            tuple((name, 4) for name in names), tuple((name,) for name in names)),),
            program_complete=True)
        bindings = SourceBindingSet(tuple(CapabilitySourceBinding(
            name, "repo:fixture/z", f"fixture.generator.{i % 2}", f"fixture.oracle.{i % 2}")
            for i, name in enumerate(names)))
        expected_context = curriculum
        graph = {"tokens": ["fixture.padding", "cogal.value.false", "cogal.value.true"]}
        release = compile_executable_factory_release(
            curriculum, bindings, CurriculumProfile.full(), registry, _answers(),
            source_root=None, graph=graph, verification_seed=11)
        calls.clear()
        checks.clear()
        rows = draw_executable_release_rows(None, graph, release, registry, seed=17)
        self.assertEqual(calls, [(i % 2, name, curriculum) for i, name in enumerate(names)])
        self.assertEqual(checks, [(i % 2, name) for i, name in enumerate(names) for _ in range(4)])
        self.assertEqual(tuple(row["capability"] for row in rows),
                         tuple(name for name in names for _ in range(4)))
        self.assertEqual({row["gold"] for row in rows}, {"FALSE", "TRUE"})
        self.assertTrue(all(context is curriculum for _, _, context in calls))
        with self.assertRaisesRegex(TypeError, "legacy_course"):
            draw_execution_rows(None, graph, curriculum, release.execution_plan,
                                registry, source_bindings=bindings, seed=17,
                                legacy_course=curriculum)
        from unittest.mock import patch
        historical_course = object()
        expected_context = historical_course
        calls.clear()
        with patch("bilqis_mlx.factory.generation.from_legacy_course",
                   return_value=(curriculum, bindings)) as translate:
            historical_rows = draw_execution_rows(
                None, graph, historical_course, release.execution_plan, registry, seed=17)
        translate.assert_called_once_with(historical_course)
        self.assertEqual(historical_rows, rows)
        self.assertTrue(all(context is historical_course for _, _, context in calls))
        expected_context = curriculum
        program = schedule_program_from_executable_release(release)
        from dataclasses import replace
        from bilqis_mlx.runtime.release_adoption import _schedule_for_receipt
        supplied = replace(program, program_complete=False)
        receipt = dict(factory_admission_v2={}, factory_release_sha256=release.release_sha256,
                       factory_release_file="factory-releases/" + release.release_sha256 + ".json")
        with patch("bilqis_mlx.runtime.release_adoption._cached_schedule_program",
                   return_value=program) as read_program:
            self.assertIs(_schedule_for_receipt(ROOT, receipt, supplied), program)
        read_program.assert_called_once_with(str(ROOT.resolve()), release.release_sha256,
                                             receipt["factory_release_file"])
        self.assertEqual(tuple(cap.id for cap in program.grades[0].capabilities), names)
        self.assertEqual(tuple(program.capability_map), names)
        self.assertEqual(program.grades[0].exam_item_counts, tuple((name, 4) for name in names))
        self.assertEqual(program.grades[0].teaching_stages, tuple((name,) for name in names))
        self.assertEqual(tuple(cap for cap, _ in program.assessment_projections), names)
        self.assertTrue(program.program_complete)
        self.assertEqual(program.assessment_manifest_sha256, program.grades[0].assessment_sha256)
        self.assertEqual(program.exact_scope_rubric(names), program.grades[0].assessment_sha256)
        self.assertNotEqual(program.exact_scope_rubric(names[:-1]), program.grades[0].assessment_sha256)
        for requested in ((names[-1],), (names[9], names[0], names[5])):
            with self.subTest(profile=requested):
                selected = tuple(name for name in names if name in requested)
                thin = compile_executable_factory_release(
                    curriculum, bindings, CurriculumProfile("fixture.thin", grades=(
                        GradeProfile("Z", enabled_capabilities=requested),)),
                    registry, _answers(), source_root=None, graph=graph, verification_seed=11)
                self.assertEqual(thin.curriculum, curriculum)
                self.assertEqual(thin.source_bindings, bindings)
                self.assertEqual(thin.execution_plan.grades[0].capabilities, selected)
                self.assertEqual(thin.execution_plan.grades[0].cumulative_scope, selected)
                calls.clear()
                subset_rows = draw_executable_release_rows(None, graph, thin, registry, seed=17)
                self.assertEqual(calls, [(i % 2, name, curriculum) for i, name in enumerate(names)
                                         if name in selected])
                self.assertEqual(tuple(row["capability"] for row in subset_rows),
                                 tuple(name for name in selected for _ in range(4)))
                thin_schedule = schedule_program_from_executable_release(thin)
                self.assertEqual(tuple(thin_schedule.capability_map), selected)
                self.assertFalse(thin_schedule.program_complete)


@unittest.skipUnless(SOURCE.is_dir(), "Pinned historic source not mounted")
class LiveProfileExecutionTests(unittest.TestCase):
    def test_real_full_b_provider_executes_and_iff_profile_without_minimal_provider(self):
        result = _run_live_profile_probe()
        self.assertEqual(
            result.returncode, 0,
            msg="stdout:\n" + result.stdout + "\nstderr:\n" + result.stderr)
        self.assertIn("LIVE_PROFILE_EXECUTION_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
