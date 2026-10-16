"""Exercise the saved-run audit through the human CLI without neural imports."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.cli import main
from bilqis_mlx.diagnostics import DiagnosticStatus, LearningSignal
from bilqis_mlx.diagnostics.signals import DiagnosticTarget
from bilqis_mlx.diagnostics.teaching import METHODOLOGY_VERSION
from tests.test_learning_diagnostics import constructed_exam


def save_exam(root, generation, seed, *, outbox=False,
              optimizer_step=None, student_sha256=None):
    cohort, exam = constructed_exam(predicted=("FALSE",) * 12, seed=seed)
    if optimizer_step is not None:
        exam["optimizer_step"] = optimizer_step
    if student_sha256 is not None:
        exam["student_sha256"] = student_sha256
    exam["cohort_file"] = "cohorts/" + cohort["cohort_sha256"] + ".json"
    record = {"generation": generation, "run_id": "disposable-audit",
              "last_exam": exam}
    (root / "cohorts").mkdir(exist_ok=True)
    (root / "states").mkdir(exist_ok=True)
    (root / exam["cohort_file"]).write_text(json.dumps(cohort))
    (root / "states" / f"{generation:07d}.json").write_text(json.dumps(record))
    (root / "state.json").write_text(json.dumps(record))
    event = {"event": "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED", "grade": "X",
             "generation": generation, "scores": exam["scores"],
             "rubric": exam["exam_rubric_sha256"],
             **{key: exam[key] for key in (
                 "cohort_sha256", "student_sha256", "optimizer_step")}}
    event["generator_version"] = exam["generator_version"]
    if outbox:
        from bilqis_mlx.grade_a_trainer import _with_delivery_outbox
        record = _with_delivery_outbox(record, (event,))
        event = record["delivery_outbox"][0]
        (root / "states" / f"{generation:07d}.json").write_text(json.dumps(record))
        (root / "state.json").write_text(json.dumps(record))
    with (root / "events.jsonl").open("a") as stream:
        stream.write(json.dumps(event) + "\n")
    return event


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class DiagnosticAuditTests(unittest.TestCase):
    def test_methodology_commit_survives_boundary_ledger_replay_window(self):
        from bilqis_mlx.diagnostics.event_evidence import load_verified_lesson_methodology
        from bilqis_mlx.grade_a_trainer import _with_delivery_outbox

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "states").mkdir()
            generation = 4
            capability = "B.NOT"
            findings = [{
                "signal": signal,
                "status": DiagnosticStatus.NOT_OBSERVED,
                "capability": capability,
                "target": DiagnosticTarget.CAPABILITY,
            } for signal in (
                LearningSignal.DISCONNECTED_PREREQUISITES,
                LearningSignal.EXCESSIVE_INTRODUCTORY_COMPLEXITY,
            )]
            visit = {
                "event": "SCHOOL_GRADE_B_TEACHER_VISIT_COMMITTED",
                "generation": generation,
                "capability": capability,
                "lesson_methodology": {
                    "schema": METHODOLOGY_VERSION,
                    "course_sha256": "a" * 64,
                    "capability": capability,
                    "optimizer_batches_observed": 1,
                    "delivered_examples": 4,
                    "findings": findings,
                },
            }
            comparison = {
                "event": "SCHOOL_LIVE_CANDIDATE_COMPARED",
                "generation": generation,
                "grade": "B",
            }
            committed = _with_delivery_outbox(
                {"run_id": "diagnostic-stop-fixture", "generation": generation},
                (visit, comparison),
            )
            state = root / "states" / f"{generation:07d}.json"
            state.write_text(json.dumps(committed))
            (root / "state.json").write_text(json.dumps(committed))
            # Model the crash window after the visit is fsynced but before the
            # already committed boundary member is replayed to events.jsonl.
            delivered_visit = committed["delivery_outbox"][0]
            (root / "events.jsonl").write_text(json.dumps(delivered_visit) + "\n")
            verified = load_verified_lesson_methodology(root)
            self.assertEqual(verified, (delivered_visit,))

            no_boundary = _with_delivery_outbox(
                {"run_id": "diagnostic-stop-fixture", "generation": generation},
                (visit,),
            )
            state.write_text(json.dumps(no_boundary))
            (root / "state.json").write_text(json.dumps(no_boundary))
            (root / "events.jsonl").write_text(
                json.dumps(no_boundary["delivery_outbox"][0]) + "\n")
            with self.assertRaisesRegex(ValueError, "BOUNDARY_OUTBOX_MISSING"):
                load_verified_lesson_methodology(root)

    def test_exam_boundary_builds_automatic_s1_s2_without_sealed_question_policy(self):
        from bilqis_mlx.diagnostics.exam_events import summarize_completed_exam
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save_exam(root, 1, 7)
            state = json.loads((root / "state.json").read_text())
            # The live teacher has already completed supervised source scoring;
            # this method only consumes those results for nonbinding warnings.
            report = summarize_completed_exam(root, state, state["last_exam"])
            self.assertEqual(report["optimizer_step"], 107)
            self.assertTrue(any(warning == {
                "signal": LearningSignal.REPETITIVE_ANSWERS,
                "target": "CAPABILITY", "capability": "X.NOT"}
                for warning in report["active_warnings"]))
            self.assertTrue(any(warning == {
                "signal": LearningSignal.CHANCE_LEVEL_OR_LAGGING,
                "target": "GRADE", "capability": "X"}
                for warning in report["active_warnings"]))
            self.assertNotIn("holdout", report)

    def test_fixed_exam_retry_history_reports_s3_not_false_unmeasured(self):
        from bilqis_mlx.diagnostics.audit import audit_saved_run
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for generation, step, student_sha in (
                (1, 107, "1" * 64), (2, 123, "2" * 64),
                (3, 139, "3" * 64)):
                save_exam(root, generation, 7, outbox=True,
                          optimizer_step=step, student_sha256=student_sha)
            report = audit_saved_run(root)
            self.assertEqual(report["archived_exam_count"], 3)
            self.assertEqual(report["comparable_exam_count"], 3)
            current = [f for f in report["current_findings"]
                       if f["capability"] == "X" and
                       f["signal"] == LearningSignal.LACK_OF_DURABLE_GAIN]
            self.assertEqual(len(current), 1)
            self.assertEqual(current[0]["status"],
                             DiagnosticStatus.OBSERVED_LONGITUDINALLY)
            self.assertEqual(current[0]["trajectory"],
                             ((107, 6, 12), (123, 6, 12), (139, 6, 12)))
            self.assertNotIn(LearningSignal.LACK_OF_DURABLE_GAIN,
                             report["unmeasured_signals"])
            self.assertIn(LearningSignal.DISCONNECTED_PREREQUISITES,
                          report["unmeasured_signals"])
    def test_regressing_history_is_rejected_instead_of_sorted(self):
        from bilqis_mlx.diagnostics.audit import audit_saved_run
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save_exam(root, 1, 8, outbox=True)
            save_exam(root, 2, 7, outbox=True)
            with self.assertRaisesRegex(ValueError, "NON_MONOTONIC"):
                audit_saved_run(root)

    def test_current_pointer_cannot_hide_a_later_committed_exam(self):
        from bilqis_mlx.diagnostics.audit import audit_saved_run
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save_exam(root, 1, 7, outbox=True)
            old = (root / "state.json").read_bytes()
            save_exam(root, 2, 8, outbox=True)
            (root / "state.json").write_bytes(old)
            with self.assertRaisesRegex(ValueError, "LATEST_EXAM_NOT_IN_COMMITTED_HISTORY"):
                audit_saved_run(root)

    def test_symlinks_cannot_replace_immutable_evidence(self):
        from bilqis_mlx.diagnostics.audit import audit_saved_run
        for name in ("state.json", "states/0000001.json", "events.jsonl", "cohort"):
            with self.subTest(file=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                save_exam(root, 1, 7, outbox=True)
                path = (next((root / "cohorts").iterdir()) if name == "cohort"
                        else root / name)
                copy = path.with_name(path.name + ".preserved")
                copy.write_bytes(path.read_bytes())
                path.unlink()
                path.symlink_to(copy)
                with self.assertRaisesRegex(ValueError, "EVIDENCE_NOT_REGULAR"):
                    audit_saved_run(root)
    def test_latest_pointer_cannot_borrow_another_runs_exam_history(self):
        from bilqis_mlx.diagnostics.audit import audit_saved_run
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save_exam(root, 1, 7)
            state = json.loads((root / "state.json").read_text())
            state["run_id"] = "unrelated-run"
            (root / "state.json").write_text(json.dumps(state))
            with self.assertRaisesRegex(ValueError, "LATEST_EXAM_NOT_IN_COMMITTED_HISTORY"):
                audit_saved_run(root)
    def test_outbox_era_event_must_match_its_immutable_delivery_intent(self):
        from bilqis_mlx.diagnostics.audit import audit_saved_run
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            event = save_exam(root, 1, 7, outbox=True)
            report = audit_saved_run(root)
            self.assertEqual(report["outbox_verified_exam_count"], 1)
            for key, value in (("event_id", "0" * 64), ("grade", "UNRELATED")):
                broken = dict(event, **{key: value})
                (root / "events.jsonl").write_text(json.dumps(broken) + "\n")
                with self.assertRaisesRegex(ValueError, "EVENT_OUTBOX_CONFLICT"):
                    audit_saved_run(root)

    def test_same_rubric_cannot_silently_change_capability_inventory(self):
        from bilqis_mlx.diagnostics.audit import audit_saved_run
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save_exam(root, 1, 7)
            save_exam(root, 2, 8)
            state = json.loads((root / "state.json").read_text())
            exam = state["last_exam"]
            cohort = json.loads((root / exam["cohort_file"]).read_text())
            for row in cohort["rows"]:
                row["capability"] = "X.RENAMED"
            from bilqis_mlx.generated_assessment import make_cohort
            digest = make_cohort(cohort["rows"],
                generator_version=cohort["generator_version"], seed=cohort["seed"],
                rubric_version=cohort["schema"]).digest
            cohort["cohort_sha256"] = exam["cohort_sha256"] = digest
            exam["cohort_file"] = "cohorts/" + digest + ".json"
            exam["scores"] = {"X.RENAMED": exam["scores"]["X.NOT"]}
            for miss in exam["misses_for_teacher"]:
                miss["capability"] = "X.RENAMED"
            (root / exam["cohort_file"]).write_text(json.dumps(cohort))
            for file in (root / "state.json", root / "states/0000002.json"):
                file.write_text(json.dumps(state))
            events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
            events[-1].update(cohort_sha256=digest, scores=exam["scores"])
            (root / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
            with self.assertRaisesRegex(ValueError, "INVENTORY_DRIFT"):
                audit_saved_run(root)
    def test_cli_audits_five_signals_and_preserves_all_saved_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save_exam(root, 1, 7)
            save_exam(root, 2, 8)
            before = snapshot(root)
            output = io.StringIO()
            with redirect_stdout(output):
                result = main(["diagnostics", "--run-dir", str(root)])
            self.assertEqual(result, 0)
            report = json.loads(output.getvalue())
            self.assertFalse(report["neural_training_started_by_this_command"])
            self.assertFalse(report["source_oracles_replayed"])
            self.assertEqual(report["archived_exam_count"], 2)
            self.assertEqual(report["comparable_exam_count"], 2)
            self.assertEqual(len(report["unmeasured_signals"]), 3)
            whole = [f for f in report["latest_findings"] if f["capability"] == "*"]
            self.assertEqual({f["signal"] for f in whole}, set(LearningSignal))
            self.assertEqual(next(f for f in whole if f["signal"] ==
                LearningSignal.CHANCE_LEVEL_OR_LAGGING)["status"],
                DiagnosticStatus.OBSERVED_IN_COHORT)
            self.assertEqual(snapshot(root), before)

    def test_event_state_mismatch_is_an_error_and_cannot_produce_a_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            event = save_exam(root, 1, 7)
            event["student_sha256"] = "a" * 64
            (root / "events.jsonl").write_text(json.dumps(event) + "\n")
            before = snapshot(root)
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                result = main(["diagnostics", "--run-dir", str(root)])
            self.assertEqual(result, 2)
            self.assertEqual(out.getvalue(), "")
            self.assertIn("EVENT_STATE_CONFLICT", err.getvalue())
            self.assertEqual(snapshot(root), before)

    def test_changed_rubric_keeps_old_evidence_separate(self):
        from bilqis_mlx.diagnostics.audit import audit_saved_run
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save_exam(root, 1, 7)
            first = json.loads((root / "states/0000001.json").read_text())
            first["last_exam"]["exam_rubric_sha256"] = "a" * 64
            path = root / first["last_exam"]["cohort_file"]
            cohort = json.loads(path.read_text())
            cohort["rubric_sha256"] = "a" * 64
            path.write_text(json.dumps(cohort))
            (root / "states/0000001.json").write_text(json.dumps(first))
            event = json.loads((root / "events.jsonl").read_text())
            event["rubric"] = "a" * 64
            (root / "events.jsonl").write_text(json.dumps(event) + "\n")
            save_exam(root, 2, 8)
            report = audit_saved_run(root)
            self.assertEqual(report["archived_exam_count"], 2)
            self.assertEqual(report["comparable_exam_count"], 1)
            self.assertEqual(report["excluded_contract_observations"], 1)
            self.assertEqual(report["history_findings"], [])

    def test_event_generator_and_state_generation_are_bound(self):
        from bilqis_mlx.diagnostics.audit import audit_saved_run
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            event = save_exam(root, 1, 7)
            event["generator_version"] = "unrelated-generator"
            (root / "events.jsonl").write_text(json.dumps(event) + "\n")
            with self.assertRaisesRegex(ValueError, "EVENT_STATE_CONFLICT"):
                audit_saved_run(root)
            event["generator_version"] = "source-fixture"
            (root / "events.jsonl").write_text(json.dumps(event) + "\n")
            record = json.loads((root / "states/0000001.json").read_text())
            record["generation"] = None
            (root / "states/0000001.json").write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, "STATE_GENERATION_DRIFT"):
                audit_saved_run(root)


if __name__ == "__main__":
    unittest.main()
