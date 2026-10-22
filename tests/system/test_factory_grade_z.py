"""Disposable end-to-end proof that a new grade needs no generic runtime edits.

This test declares Grade Z, its source adapter, and its binary answer modality
entirely inside the test.  Production code must treat it as ordinary factory
data through release compilation, admission, scheduling, assessment,
championship, telemetry, recovery, teacher evidence, stagnation, and stop logic.
No optimizer or MLX runtime is invoked.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.cli import human_stop_summary
from bilqis_mlx.curriculum import AnswerFamily, BINARY, Capability, Course, Grade
from bilqis_mlx.curriculum.scheduler import (
    Assessment, Score, assess, assess_withheld, start_new, visit,
)
from bilqis_mlx.factory.adapters import (
    RegisteredSourceAdapter, SourceAdapterRegistry,
)
from bilqis_mlx.factory.answers import (
    AnswerModality, AnswerModalityRegistry, RegisteredAnswerModality,
    fixed_domain,
)
from bilqis_mlx.factory.assessment import qualification_complete
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.generation import draw_executable_release_rows
from bilqis_mlx.factory.model import AssessmentClass, LearningEvidence, SourceAdapter
from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.generated_assessment import score as score_cohort
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.learning.epoch_championships import advance_epoch
from bilqis_mlx.learning.mentor_epoch import begin_initial_epoch
from bilqis_mlx.learning.stagnation_control import (
    begin_recovery_cycle, complete_recovery_cycle, quarantined_capabilities,
    record_visit, start_session,
)
from bilqis_mlx.learning.teacher_feedback import reconcile_unresolved_misses
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES, SchoolTelemetry
from bilqis_mlx.presentation.spiral_dashboard import Dashboard
from bilqis_mlx.runtime.admission import (
    _executable_factory_admission, _require_executable_factory_admission,
)
from bilqis_mlx.runtime.assessment import (
    _generalization_executable_cohort, _promotion_executable_cohort,
    _routine_executable_cohort, load_championship_cohort,
)
from bilqis_mlx.runtime.state import _fingerprint, _state_from_json
from bilqis_mlx.trainer import session_stop_reason


CAPABILITIES = tuple(f"Z.C{index}" for index in range(6))


def _rows(*, capability, seed, each, **_):
    return tuple({
        "id": f"{capability}:{seed}:{index}",
        "capability": capability,
        "answer_kind": "binary",
        "gold": "TRUE" if index % 2 else "FALSE",
    } for index in range(each))


def _check(row, **_):
    try:
        index = int(row["id"].rsplit(":", 1)[1])
    except (KeyError, ValueError):
        return False
    return row.get("gold") == ("TRUE" if index % 2 else "FALSE")


def _fixture():
    capabilities = tuple(Capability(
        id=identity,
        difficulty="disposable-z",
        source_anchor="repo:fixture/grade-z",
        taught_roots=("z.semantic." + identity.rsplit(".", 1)[1],),
        examined_roots=("z.semantic." + identity.rsplit(".", 1)[1],),
        prerequisites=(), composed_of=(),
        answer_families=(AnswerFamily("binary", BINARY),),
        lesson_generator="fixture.z-generator/v1",
        independent_oracle="fixture.z-oracle/v1",
    ) for identity in CAPABILITIES)
    grade = Grade(
        "Z", capabilities,
        assessment_sha256="a" * 64,
        exam_item_counts=tuple((identity, 4) for identity in CAPABILITIES),
    )
    course = Course(
        (grade,), "fixture.grade-z/v1",
        source_attestation_sha256="b" * 64,
        assessment_manifest_sha256="a" * 64,
        program_complete=True,
    )
    adapter = SourceAdapter(
        "fixture.z-adapter/v1", "fixture.z-generator/v1",
        ("fixture.z-oracle/v1",), "d" * 64,
        variation_axes=("fresh-seed", "balanced-gold"),
    )
    source_registry = SourceAdapterRegistry((
        RegisteredSourceAdapter(adapter, _rows, _check),
    ))
    answer_registry = AnswerModalityRegistry((
        RegisteredAnswerModality(
            AnswerModality("binary", "answer.binary/z-fixture", "e" * 64),
            fixed_domain(BINARY),
            lambda value: {
                "FALSE": "cogal.value.false",
                "TRUE": "cogal.value.true",
            }[value],
        ),
    ))
    graph = {
        "tokens": [
            "fixture.padding",
            "cogal.value.false",
            "cogal.value.true",
        ],
    }
    curriculum, bindings = from_legacy_course(
        course, answer_kinds=answer_registry.kinds)
    release = compile_executable_factory_release(
        curriculum, bindings, CurriculumProfile.full(),
        source_registry, answer_registry,
        source_root=None, graph=graph,
        verification_seed=20261019,
        legacy_course=course,
    )
    return course, source_registry, graph, release


class DisposableGradeZSystemProof(unittest.TestCase):
    def _assert_compiler_and_generation(self, course, registry, graph, release):
        self.assertEqual(
            tuple(item.grade_id for item in release.execution_plan.grades),
            ("Z",))
        binary_head = next(
            item for item in release.answer_heads if item.kind == "binary")
        self.assertEqual(binary_head.values, BINARY)
        rows = draw_executable_release_rows(
            None, graph, release, registry, seed=3, legacy_course=course)
        self.assertEqual(len(rows), 24)
        self.assertEqual({row["capability"] for row in rows}, set(CAPABILITIES))

    def _admit_and_schedule(self, root, course, graph, release, student, manifest):
        graph_sha = _fingerprint(graph)
        _, release_file, admission = _executable_factory_admission(
            root, release, student, graph_sha, graph)
        program = schedule_program_from_executable_release(release)
        school = start_new(program, student)
        receipt = {
            "run_id": "disposable-grade-z",
            "generation": 1,
            "source_manifest_sha256": manifest["manifest_sha256"],
            "semantic_graph_sha256": graph_sha,
            "factory_release_sha256": release.release_sha256,
            "factory_release_file": release_file,
            "factory_admission_v2": asdict(admission),
            "qualification_cohort_v2": None,
            "burned_generalization_cohorts_v2": [],
            "school": asdict(school),
        }
        restored = _require_executable_factory_admission(
            root, json.loads(json.dumps(receipt)), graph)
        self.assertEqual(restored, release)
        recovered_school = _state_from_json(
            json.loads(json.dumps(receipt["school"])), program)
        self.assertEqual(recovered_school, school)
        for capability in CAPABILITIES:
            self.assertEqual(school.queue[0], capability)
            school = visit(program, school, capability, student)
        self.assertEqual(school.stage, "ASSESS_MAIN")
        return receipt, program, school, graph_sha

    def _assert_cohort_lifecycle(
            self, root, receipt, manifest, course, registry, graph, release):
        routine, routine_pointer = _routine_executable_cohort(
            root, receipt, manifest, release, registry, None, graph,
            capabilities=CAPABILITIES, assessment_epoch=0,
            legacy_course=course)
        promotion, promotion_pointer = _promotion_executable_cohort(
            root, receipt, manifest, release, registry, None, graph,
            capabilities=CAPABILITIES, assessment_epoch=0,
            legacy_course=course)
        fixed_promotion, fixed_pointer = _promotion_executable_cohort(
            root, {**receipt, "qualification_cohort_v2": promotion_pointer},
            manifest, release, registry, None, graph,
            capabilities=CAPABILITIES, assessment_epoch=0,
            legacy_course=course)
        self.assertEqual(fixed_promotion, promotion)
        self.assertEqual(fixed_pointer, promotion_pointer)
        generalization, generalization_pointer = _generalization_executable_cohort(
            root, receipt, manifest, release, registry, None, graph,
            capabilities=CAPABILITIES, assessment_epoch=0,
            promotion_pointer=promotion_pointer, legacy_course=course)
        self.assertFalse(
            {row["id"] for row in promotion.rows} &
            {row["id"] for row in generalization.rows})
        next_generalization, next_pointer = _generalization_executable_cohort(
            root,
            {**receipt,
             "burned_generalization_cohorts_v2": [generalization_pointer]},
            manifest, release, registry, None, graph,
            capabilities=CAPABILITIES, assessment_epoch=0,
            promotion_pointer=promotion_pointer, legacy_course=course)
        self.assertNotEqual(next_generalization.digest, generalization.digest)
        self.assertNotEqual(next_pointer, generalization_pointer)
        return routine, routine_pointer, promotion, generalization

    def _assert_mastery_debt_and_teacher(
            self, program, school, student, routine, routine_pointer,
            promotion, generalization):
        perfect = Assessment(
            checkpoint_sha256=student.sha256,
            optimizer_step=student.optimizer_step,
            course_digest=program.digest(),
            rubric_digest=routine_pointer["rubric_sha256"],
            scores={identity: Score(4, 4) for identity in CAPABILITIES},
            evaluation_id="grade-z-perfect",
        )
        mastered = assess(program, school, perfect)
        while mastered.stage == "PROMOTION_SWEEP":
            mastered = visit(program, mastered, mastered.queue[0], student)
            mastered = assess(program, mastered, perfect)
        self.assertEqual(mastered.stage, "WHOLE_SCHOOL_MASTERED")
        self.assertEqual(
            session_stop_reason(
                stage=mastered.stage, elapsed_seconds=0, minutes=90,
                visits=mastered.visits, max_visits=0, grade="Z"),
            "WHOLE_SCHOOL_MASTERED")

        withheld = CAPABILITIES[-1]
        partial = Assessment(
            checkpoint_sha256=student.sha256,
            optimizer_step=student.optimizer_step,
            course_digest=program.digest(),
            rubric_digest=routine_pointer["rubric_sha256"],
            scores={identity: Score(4, 4)
                    for identity in CAPABILITIES if identity != withheld},
            evaluation_id="grade-z-withheld",
        )
        contained = assess_withheld(
            program, school, partial, (withheld,),
            rubric_capabilities=CAPABILITIES)
        self.assertNotEqual(contained.stage, "WHOLE_SCHOOL_MASTERED")

        control = start_session(
            session_id="z-stagnation", generation=1,
            required_capabilities=CAPABILITIES)
        control = begin_recovery_cycle(control, first_recovery=(withheld,))
        for phase in ("RECOVERY_1", "RECOVERY_2"):
            control = record_visit(
                control, capability=withheld, phase=phase,
                decision="REJECT", retained_optimizer_updates=0,
                generation=2)
        control, events = complete_recovery_cycle(
            control, weakest_tail=(withheld,),
            scores={withheld: {"correct": 0, "total": 4}},
            generation=3)
        self.assertEqual(quarantined_capabilities(control), (withheld,))
        self.assertEqual(events[0]["capability"], withheld)

        predictions = {row["id"]: row["gold"] for row in routine.rows}
        predictions[routine.rows[0]["id"]] = (
            "FALSE" if routine.rows[0]["gold"] == "TRUE" else "TRUE")
        misses = reconcile_unresolved_misses([], routine.rows, predictions)
        self.assertEqual(len(misses), 1)
        self.assertTrue(misses[0]["capability"].startswith("Z."))

        promotion_evidence = LearningEvidence(
            AssessmentClass.PROMOTION, promotion.digest,
            student.sha256, student.optimizer_step, True)
        generalization_evidence = LearningEvidence(
            AssessmentClass.GENERALIZATION, generalization.digest,
            student.sha256, student.optimizer_step, True)
        self.assertTrue(qualification_complete(
            promotion_evidence, generalization_evidence))
        return mastered

    def _assert_championship(
            self, root, routine, routine_pointer, student, graph_sha, manifest):
        scores = score_cohort(
            routine,
            {row["id"]: row["gold"] for row in routine.rows},
            asdict(student))["scores"]
        questions = {
            identity: [
                {"id": row["id"], "gold": row["gold"]}
                for row in routine.rows if row["capability"] == identity]
            for identity in CAPABILITIES
        }
        scope_sha = hashlib.sha256(
            json.dumps(CAPABILITIES).encode()).hexdigest()
        challenger = {
            "cohort_sha256": routine.digest,
            "rubric_sha256": routine_pointer["rubric_sha256"],
            "cohort_rubric_sha256": routine_pointer["rubric_sha256"],
            "assessment_scope_sha256": scope_sha,
            "source_graph_sha256": graph_sha,
            "source_oracle_sha256": manifest["manifest_sha256"],
            "challenge_grade": "Z",
            "checkpoint_origin_grade": "Z",
            "checkpoint": asdict(student),
            "scores": scores,
            "questions": questions,
            "correct_questions": questions,
        }
        epoch = begin_initial_epoch(
            student=asdict(student), introduced_grade="Z",
            source_graph_sha256=graph_sha, frontier={}, soups={})
        epoch, changed, _ = advance_epoch(
            epoch, grades={"Z": CAPABILITIES},
            challenger_exam=challenger, incumbent_exams={})
        self.assertEqual(set(changed), set(CAPABILITIES))
        self.assertEqual(set(epoch["active_roles"]), set(CAPABILITIES))
        replayed = load_championship_cohort(root, challenger)
        self.assertEqual(replayed, routine)
        return scores, scope_sha, changed

    def _assert_telemetry_and_operator(
            self, routine, routine_pointer, student, mastered, scores,
            scope_sha, changed):
        board = Dashboard(
            stream=io.StringIO(), redraw=False, tables=LETTER_TABLES,
            show_all_panels=True)
        telemetry = SchoolTelemetry(board, active_grades=("Z",))
        telemetry.ingest({
            "event": "SCHOOL_LIVE_EXAM_COMMITTED",
            "grade": "Z",
            "generation": 2,
            "rubric": routine_pointer["rubric_sha256"],
            "assessment_scope_sha256": scope_sha,
            "optimizer_step": student.optimizer_step,
            "student_sha256": student.sha256,
            "cohort_sha256": routine.digest,
            "cohort_file": routine_pointer["cohort_file"],
            "generator_version": routine.generator_version,
            "scores": scores,
            "phase": mastered.stage,
            "championship_epoch": {
                "earned_roles": list(changed),
                "cross_origin_decisions": [],
            },
        })
        self.assertIn("Z", telemetry.grades)
        self.assertTrue(any(
            row.get("grade") == "Z"
            for row in board.rows["GRADES & MASTERY"]))

        stop = {
            "stop_reason": "GRADE_Z_AWAITING_NEXT_GRADE",
            "visits_this_command": 6,
            "elapsed_seconds": 1.0,
            "optimizer_step": student.optimizer_step,
        }
        self.assertIn("awaiting the next", human_stop_summary(stop))

    def test_grade_z_runs_through_the_generic_factory_control_plane(self):
        course, registry, graph, release = _fixture()
        student = Checkpoint("1" * 64, "bundles/z-student", 7, True)
        manifest = {"manifest_sha256": "2" * 64}
        self._assert_compiler_and_generation(course, registry, graph, release)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt, program, school, graph_sha = self._admit_and_schedule(
                root, course, graph, release, student, manifest)
            routine, pointer, promotion, generalization = self._assert_cohort_lifecycle(
                root, receipt, manifest, course, registry, graph, release)
            mastered = self._assert_mastery_debt_and_teacher(
                program, school, student, routine, pointer,
                promotion, generalization)
            scores, scope_sha, changed = self._assert_championship(
                root, routine, pointer, student, graph_sha, manifest)
            self._assert_telemetry_and_operator(
                routine, pointer, student, mastered, scores, scope_sha, changed)


if __name__ == "__main__":
    unittest.main()
