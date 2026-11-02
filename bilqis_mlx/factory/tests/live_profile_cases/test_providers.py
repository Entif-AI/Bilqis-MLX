from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[4]


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
            partial(draw, i), partial(check, i),
            semantic_footprint=lambda row: ("root." + row["capability"].split("-")[-1],))
            for i in range(2)))
        names = tuple(f"opaque.task-{i}" for i in range(12))
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
        self._assert_receipt_schedule(release, program)
        self._assert_projected_schedule(program, names)
        self._assert_thin_profiles(names, curriculum, bindings, registry, graph, calls)

    def _assert_thin_profiles(self, names, curriculum, bindings, registry, graph, calls):
        from bilqis_mlx.factory.executable_release import compile_executable_factory_release
        from bilqis_mlx.factory.execution import CurriculumProfile, GradeProfile
        from bilqis_mlx.factory.generation import draw_executable_release_rows
        from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
        from bilqis_mlx.factory.tests.test_executable_release import _answers

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


    def _assert_receipt_schedule(self, release, program):
        from unittest.mock import patch
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

    def _assert_projected_schedule(self, program, names):
        from dataclasses import replace
        from bilqis_mlx.curriculum.scheduler import adopt_appended_program, start_new
        from bilqis_mlx.learning.champions import Checkpoint
        checkpoint = Checkpoint("a" * 64, "bundles/disposable-append", 7, True)
        previous = replace(program, program_complete=False)
        completed = replace(start_new(previous, checkpoint),
            stage="AWAITING_NEXT_GRADE", queue=(), champions={"Z": checkpoint},
            introduction_stage=len(previous.grades[0].teaching_stages) - 1)
        added = replace(program.grades[0], id="Q")
        added = replace(added, capabilities=tuple(replace(cap, id="Q." + cap.id)
                                                for cap in added.capabilities),
                        teaching_stages=tuple(tuple("Q." + name for name in stage)
                                              for stage in added.teaching_stages))
        successor = replace(previous, program_digest="b" * 64,
                            grades=(*previous.grades, added),
                            assessment_projections=(*previous.assessment_projections,
                                *(("Q." + name, digest) for name, digest
                                  in previous.assessment_projections)))
        admitted = adopt_appended_program(previous, successor, completed)
        from bilqis_mlx.runtime.release_adoption import _profile_transition
        transitioned, revised_grade, appended = _profile_transition(previous, successor, completed)
        self.assertEqual(transitioned, admitted)
        self.assertIsNone(revised_grade)
        self.assertTrue(appended)
        self.assertEqual(admitted.grade, "Q")
        self.assertEqual(admitted.current_student, checkpoint)
        self.assertEqual(admitted.champions, {"Z": checkpoint})
        self.assertEqual(admitted.queue, ("Q." + names[0],))
        self.assertEqual(admitted.course_digest, successor.digest())
        self.assertEqual(completed.current_student, checkpoint)
        self.assertEqual(tuple(cap.id for cap in program.grades[0].capabilities), names)
        self.assertEqual(tuple(program.capability_map), names)
        self.assertEqual(program.grades[0].exam_item_counts, tuple((name, 4) for name in names))
        self.assertEqual(program.grades[0].teaching_stages, tuple((name,) for name in names))
        self.assertEqual(tuple(cap for cap, _ in program.assessment_projections), names)
        self.assertTrue(program.program_complete)
        self.assertEqual(program.assessment_manifest_sha256, program.grades[0].assessment_sha256)
        self.assertEqual(program.exact_scope_rubric(names), program.grades[0].assessment_sha256)
        self.assertNotEqual(program.exact_scope_rubric(names[:-1]), program.grades[0].assessment_sha256)
