"""Historical plans apply through the canonical generation/outbox transaction."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.curriculum.scheduler import start_new
from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_course
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime import checkpoints, session
from bilqis_mlx.state_dag import read_current


class HistoricalRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.course = _synthetic_course(6)
        self.student = Checkpoint('a' * 64, 'bundles/unchanged', 23, True)
        self.school = start_new(self.course, self.student)
        self.receipt = checkpoints._persist(self.root, {
            'generation': 1, 'run_id': 'historical-test', 'school': asdict(self.school),
            'model_bundle': self.student.filename, 'capability_best': {},
            'source_manifest_sha256': 'b' * 64, 'teacher_source_sha256': 'c' * 64,
        })
        self.manifest = {'exam_rubric_sha256': 'd' * 64}

    def migrate(self, receipt=None):
        # This fixture has no model binary. Custody verification remains a
        # required runtime call; persistence and delivery execute without mocks.
        with patch.object(checkpoints, '_verify_best_custody') as custody:
            result = session._migrate_historical_grade_a(
                self.root, receipt or self.receipt, self.school, self.course, self.manifest)
        return result, custody

    def test_publication_repeated_resume_and_stale_baseline(self):
        (record, school), custody = self.migrate()
        self.assertEqual(record, read_current(self.root))
        self.assertEqual(school.current_student, self.student)
        self.assertEqual(record['generation'], 2)
        custody.assert_called_once()
        repeated, _ = self.migrate(record)
        self.assertEqual(repeated, (record, school))
        self.assertEqual(len((self.root / 'events.jsonl').read_text().splitlines()), 1)
        with self.assertRaisesRegex(ValueError, 'HISTORICAL_RECOVERY_BASELINE_DRIFT'):
            self.migrate(self.receipt)

    def test_crash_after_state_commit_reconciles_original_event_once(self):
        reconcile = checkpoints._reconcile_delivery_outbox
        def interrupted(root, record):
            if record['generation'] == 2:
                raise RuntimeError('interrupted delivery')
            return reconcile(root, record)
        with patch.object(checkpoints, '_reconcile_delivery_outbox', side_effect=interrupted):
            with self.assertRaisesRegex(RuntimeError, 'interrupted delivery'):
                self.migrate()
        committed = read_current(self.root)
        self.assertEqual(committed['generation'], 2)
        recovered, _ = self.migrate(committed)
        self.assertEqual(recovered[0], committed)
        self.migrate(committed)
        events = [json.loads(line) for line in (self.root / 'events.jsonl').read_text().splitlines()]
        self.assertEqual(events, committed['delivery_outbox'])

    def test_compatibility_plan_is_readonly_and_input_bound(self):
        from bilqis_mlx.compatibility.resume_migration import migrate_historical_grade_a
        before = deepcopy(self.receipt)
        snapshot = {str(p.relative_to(self.root)): p.read_bytes()
                    for p in self.root.rglob('*') if p.is_file()}
        plan = migrate_historical_grade_a(self.receipt, self.school, self.course, self.manifest)
        self.assertEqual(plan, migrate_historical_grade_a(
            self.receipt, self.school, self.course, self.manifest))
        self.assertEqual(self.receipt, before)
        self.assertEqual(snapshot, {str(p.relative_to(self.root)): p.read_bytes()
                                   for p in self.root.rglob('*') if p.is_file()})
        drifted = {**self.receipt, 'school': asdict(replace(self.school, visits=1))}
        with self.assertRaisesRegex(ValueError, 'HISTORICAL_RECOVERY_BASELINE_DRIFT'):
            self.migrate(drifted)

    def test_frontier_recovery_rebases_real_persisted_cohort_without_student_update(self):
        from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_registry
        from bilqis_mlx.runtime.tests.test_admission import _executable_fixture
        from bilqis_mlx.runtime.assessment import _routine_executable_cohort
        from bilqis_mlx.generated_assessment import score
        release, graph = _executable_fixture()
        cohort, pointer = _routine_executable_cohort(
            self.root, self.receipt, {"manifest_sha256": "b" * 64},
            release, _synthetic_registry(), None, graph,
            capabilities=tuple(release.execution_plan.capability_map), assessment_epoch=0)
        guesses = {row["id"]: row["gold"] for row in cohort.rows}
        source = {**pointer, "student_sha256": "e" * 64, "optimizer_step": 22,
                  "scores": score(cohort, guesses, asdict(self.student))["scores"],
                  "exam_rubric_sha256": pointer["rubric_sha256"]}
        self.receipt = checkpoints._advance(
            self.root, {**self.receipt, "config": {}, "answer_ids": [1, 2]},
            self.school, last_exam=source)
        cohort_bytes = (self.root / pointer["cohort_file"]).read_bytes()
        def plan(_mx, _root, receipt):
            return (source if receipt["last_exam"]["student_sha256"] !=
                    self.student.sha256 else None)
        with patch("bilqis_mlx.compatibility.frontier_recovery.recover_legacy_frontier",
                   side_effect=plan), patch("bilqis_mlx.learning.student_ops._predictions",
                                            return_value=guesses):
            migrated = session._recover_legacy_frontier(
                None, self.root, self.receipt, self.course, {})
            repeated = session._recover_legacy_frontier(
                None, self.root, migrated, self.course, {})
        self.assertEqual(migrated, repeated)
        self.assertEqual(migrated["school"]["current_student"], asdict(self.student))
        self.assertEqual(migrated["last_exam"]["scores"], source["scores"])
        self.assertEqual(migrated["last_exam"]["student_sha256"], self.student.sha256)
        self.assertEqual(migrated["last_exam"]["optimizer_step"], self.student.optimizer_step)
        self.assertEqual((self.root / pointer["cohort_file"]).read_bytes(), cohort_bytes)
        events = [json.loads(line) for line in (self.root / "events.jsonl").read_text().splitlines()]
        self.assertEqual([event["event"] for event in events], ["SCHOOL_FIXED_FRONTIER_REBASELINED"])

    def test_historical_frontier_interpreter_rejects_ambiguous_admission_evidence(self):
        from bilqis_mlx.compatibility.frontier_recovery import _grade_c_admission_event
        current, previous = {"sha256": "a" * 64}, {"sha256": "e" * 64}
        event = {"event": "SCHOOL_COURSE_ADMITTED", "grade": "C",
                 "student_sha256": current["sha256"],
                 "previous_student_sha256": previous["sha256"]}
        path = self.root / "events.jsonl"
        path.write_text(json.dumps(event) + "\n" + json.dumps(event) + "\n")
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "ADMISSION_EVENT_DRIFT"):
            _grade_c_admission_event(self.root, current, previous, "C")
        self.assertEqual(path.read_bytes(), before)

    def test_plan_rejects_school_not_bound_to_the_receipt(self):
        from bilqis_mlx.compatibility.resume_migration import migrate_historical_grade_a
        drifted = replace(self.school, current_student=replace(self.student, optimizer_step=24))
        with self.assertRaisesRegex(ValueError, "HISTORICAL_MIGRATION_SCHOOL_DRIFT"):
            migrate_historical_grade_a(self.receipt, drifted, self.course, self.manifest)

    def test_orphan_generation_replays_without_repeating_the_migration(self):
        from bilqis_mlx import state_dag
        durable = state_dag._durable
        def interrupt(path, *args, **kwargs):
            if Path(path).name == "state.json":
                raise RuntimeError("lost head publication")
            return durable(path, *args, **kwargs)
        with patch.object(state_dag, "_durable", side_effect=interrupt):
            with self.assertRaisesRegex(RuntimeError, "lost head publication"):
                self.migrate()
        self.assertEqual(read_current(self.root), self.receipt)
        self.assertTrue((self.root / "states/0000002.json").is_file())
        (recovered, _), _ = self.migrate()
        self.assertEqual(recovered["generation"], 2)
        self.assertEqual(read_current(self.root), recovered)
        self.migrate(recovered)
        events = [json.loads(line) for line in (self.root / "events.jsonl").read_text().splitlines()]
        self.assertEqual(sum(e["event"] == "SCHOOL_LIVE_GRADE_A_MIGRATED" for e in events), 1)
        self.assertEqual(recovered["school"]["current_student"], asdict(self.student))
