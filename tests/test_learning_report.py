"""Small, no-MLX behavioral fixtures for the standalone read-only report."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.diagnostics.learning_report import (analyze, main, read_history,
                                                    render_html)


def exam(step, correct, cohort, student, *, observed=False):
    # A synthetic but fixed 72-item B inventory, six 12-item capabilities.
    values = [12, 12, 12, 12, 12, max(0, correct-60)]
    if correct < 60:
        values = [min(12, max(0, correct-i*12)) for i in range(6)]
    scores = {f"B.{cap}": {"correct": value, "total": 12}
              for cap, value in zip(("AND", "IFF", "IMPLIES", "NOT", "OR", "XOR"), values)}
    assert sum(v["correct"] for v in scores.values()) == correct
    findings = ([{"capability": "B.XOR", "target": "CAPABILITY",
                 "signal": "REPETITIVE_ANSWERS", "status": "OBSERVED_IN_COHORT",
                 "note": "Constant output across varied source-gold labels"}]
                if observed else [])
    return {"event": "SCHOOL_LIVE_EXAM_COMMITTED", "grade": "B",
            "generation": step, "optimizer_step": step, "scores": scores,
            "rubric": "sealed-rubric", "generator_version": "fixture/v1",
            "assessment_scope_sha256": "same-inventory", "student_sha256": student,
            "cohort_sha256": cohort,
            "learning_diagnostics": {"findings": findings}}


def visit(step):
    return {"event": "SCHOOL_GRADE_B_TEACHER_VISIT_COMMITTED",
            "capability": "B.XOR", "optimizer_step": step,
            "strategy": {"old": 16}, "teacher_policy": "fixture-policy",
            "retained_optimizer_updates": 16,
            "candidate_retention": {"decision": "PROVISIONAL",
                                    "reason": "PAIRED_SCREEN_WITHIN_BUDGET"},
            "lesson_methodology": {"findings": [{
                "capability": "B.XOR", "signal": "DISCONNECTED_PREREQUISITES",
                "status": "NOT_MEASURED", "note": "No delivered source evidence"}]}}


class LearningReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "school"
        self.run.mkdir()
        records = [exam(230280, 69, "cohort-old", "student-A"),
                   visit(230312),
                   exam(230344, 65, "cohort-old", "student-B"),
                   exam(230344, 65, "cohort-old", "student-B"),
                   exam(230344, 44, "cohort-new", "student-B", observed=True),
                   exam(230360, 45, "cohort-new", "student-C")]
        (self.run / "events.jsonl").write_text(
            "".join(json.dumps(record, sort_keys=True)+"\n" for record in records))

    def test_paired_decline_is_distinct_from_same_student_cohort_change(self):
        ledger = read_history(self.run / "events.jsonl")
        self.assertEqual(ledger["duplicate_exams"], 1)
        report = analyze(ledger)
        self.assertEqual(report["latest_scores"]["B"],
                         {"correct": 45, "total": 72})
        paired = [f for f in report["alerts"] if f["target"] == "B" and f["paired"]]
        unpaired = [f for f in report["alerts"] if f["target"] == "B" and
                    f["kind"] == "CROSS_COHORT_SCORE_GAP"]
        self.assertTrue(any(f["before"] == 69 and f["after"] == 65 for f in paired))
        self.assertTrue(any(f["before"] == 65 and f["after"] == 44 and
                            f["same_student"] and f["start_step"] == f["end_step"] == 230344
                            for f in unpaired))
        self.assertTrue(any(f["intervening_visits"] == 1 for f in paired))

    def test_native_signals_and_missing_teacher_evidence_are_not_invented(self):
        report = analyze(read_history(self.run / "events.jsonl"))
        signals = report["signals"]["latest"]
        self.assertTrue(any(f["signal"] == "REPETITIVE_ANSWERS" and
                            f["status"] == "OBSERVED_IN_COHORT" for f in signals))
        self.assertTrue(any(f["signal"] == "DISCONNECTED_PREREQUISITES" and
                            f["status"] == "NOT_MEASURED" for f in signals))
        self.assertTrue(any(f["signal"] == "EXCESSIVE_INTRODUCTORY_COMPLEXITY" and
                            f["status"] == "NOT_MEASURED" for f in signals))
        teacher = next(t for t in report["teacher"] if t["target"] == "B.XOR")
        self.assertEqual(teacher["no_old_delivery_receipt"], 1)
        self.assertEqual(teacher["accepted"], 1)

    def test_new_numeric_scope_is_not_assessed_as_paired_forgetting(self):
        record = exam(230376, 23, "new-staircase-cohort", "student-D")
        record["assessment_scope_sha256"] = "a-new-numeric-domain"
        with (self.run / "events.jsonl").open("a") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        report = analyze(read_history(self.run / "events.jsonl"))
        self.assertEqual(report["scopes"], 2)
        self.assertEqual(report["latest_scores"]["B"]["correct"], 23)
        self.assertEqual(report["alerts"], [])
        self.assertEqual(report["distinct_exams_in_scope"], 1)

    def test_html_document_marks_cohort_changes_and_student_steps(self):
        rendered = render_html(analyze(read_history(self.run / "events.jsonl")))
        self.assertIn("Where learning held", rendered)
        self.assertIn("Cohort discontinuity", rendered)
        self.assertIn("230,344", rendered)
        self.assertIn("65/72", rendered)
        self.assertIn("44/72", rendered)
        self.assertIn("NOT_MEASURED", rendered)
        self.assertNotIn("https://cdn.", rendered)

    def test_npm_entrypoint_outputs_stable_html_and_json_outside_training_run(self):
        output = self.root / "reports" / "report.html"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--run-dir", str(self.run),
                                   "--output", str(output)]), 0)
        before = (output.read_bytes(), output.with_suffix(".json").read_bytes())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--run-dir", str(self.run),
                                   "--output", str(output)]), 0)
        self.assertEqual(before, (output.read_bytes(),
                                  output.with_suffix(".json").read_bytes()))
        with self.assertRaises(SystemExit):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                main(["--run-dir", str(self.run),
                      "--output", str(self.run / "unsafe.html")])


if __name__ == "__main__":
    unittest.main()
