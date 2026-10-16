"""Exercise the saved-run audit through the human CLI without neural imports."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.cli import main
from bilqis_mlx.diagnostics import DiagnosticStatus, LearningSignal
from tests.test_learning_diagnostics import constructed_exam


def save_exam(root, generation, seed, *, outbox=False):
    cohort, exam = constructed_exam(predicted=("FALSE",) * 12, seed=seed)
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
