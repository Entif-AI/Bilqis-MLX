"""Actual archived A/B evidence and falsifying negative diagnostic controls.

These tests never load student model weights or mutate training state.
"""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.diagnostics import (DiagnosticStatus, DiagnosticTarget,
    LearningSignal, diagnose_exam, diagnose_history, load_archived_exam_history,
    load_saved_exam, observe_binary_exam)
from bilqis_mlx.generated_assessment import make_cohort, score


ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "runs/school-mlx-v1"


def constructed_exam(*, predicted: tuple[str, ...], seed: int = 7):
    """Source-independent gold for actual, behavioral confusion assertions."""
    rows = [dict(id=f"witness-{seed}-{n}", source_id=f"witness-{seed}-{n}",
                 capability="X.NOT", answer_kind="binary",
                 gold="TRUE" if n % 2 else "FALSE") for n in range(len(predicted))]
    cohort = make_cohort(rows, generator_version="source-fixture", seed=seed,
                         rubric_version="scoped-binary-fixture")
    payload = dict(schema=cohort.rubric_version,
                   rubric_sha256="c" * 64,
                   generator_version=cohort.generator_version,
                   seed=cohort.seed, cohort_sha256=cohort.digest, rows=rows)
    predictions = dict(zip((r["id"] for r in rows), predicted))
    measured = score(cohort, predictions, dict(sha256="d" * 64,
                 optimizer_step=100 + seed, model_and_native_adamw=True))
    last_exam = dict(cohort_sha256=cohort.digest, cohort_seed=seed,
                     generator_version=cohort.generator_version,
                     exam_rubric_sha256=payload["rubric_sha256"],
                     student_sha256="d" * 64, optimizer_step=100 + seed,
                     scores=measured["scores"],
                     misses_for_teacher=list(measured["misses_for_teacher"]))
    return payload, last_exam


def find_signal(findings, signal, target, capability):
    return next(x for x in findings if x.signal is signal and x.target is target
                and x.capability == capability)


class DiagnosticObservationTests(unittest.TestCase):
    def test_binary_collapse_distinct_from_baseline_quality(self):
        constant_false = ("FALSE",) * 12
        cohort, receipt = constructed_exam(predicted=constant_false)
        observed = observe_binary_exam(cohort, receipt)
        cap = observed.capabilities[0]
        self.assertEqual((cap.correct, cap.total), (6, 12))
        self.assertEqual((cap.gold_false, cap.gold_true), (6, 6))
        self.assertEqual((cap.predicted_false, cap.predicted_true), (12, 0))
        self.assertEqual((cap.confusion_ff, cap.confusion_ft,
                          cap.confusion_tf, cap.confusion_tt), (6, 0, 6, 0))
        findings = diagnose_exam(observed)
        self.assertEqual(find_signal(findings, LearningSignal.REPETITIVE_ANSWERS,
                                    DiagnosticTarget.CAPABILITY, "X.NOT").status,
                         DiagnosticStatus.OBSERVED_IN_COHORT)
        self.assertEqual(find_signal(findings, LearningSignal.CHANCE_LEVEL_OR_LAGGING,
                                    DiagnosticTarget.GRADE, "X").status,
                         DiagnosticStatus.OBSERVED_IN_COHORT)
        for signal in (LearningSignal.LACK_OF_DURABLE_GAIN,
                       LearningSignal.DISCONNECTED_PREREQUISITES,
                       LearningSignal.EXCESSIVE_INTRODUCTORY_COMPLEXITY):
            self.assertEqual(find_signal(findings, signal, DiagnosticTarget.GRADE,
                                         "X").status, DiagnosticStatus.NOT_MEASURED)

    def test_balanced_predictions_can_still_be_at_baseline(self):
        # 6 correct of 12 despite using both output labels, so no collapse.
        values = tuple("FALSE" if n % 4 < 2 else "TRUE" for n in range(12))
        cohort, last = constructed_exam(predicted=values)
        observed = observe_binary_exam(cohort, last)
        findings = diagnose_exam(observed)
        self.assertEqual(find_signal(findings, LearningSignal.REPETITIVE_ANSWERS,
                                    DiagnosticTarget.GRADE, "X").status,
                         DiagnosticStatus.NOT_OBSERVED)
        self.assertEqual(observed.grade_total("X").predicted_false, 6)
        self.assertEqual(observed.grade_total("X").predicted_true, 6)

    def test_longitudinal_signal_requires_distinct_compatible_cohorts(self):
        cohort1, last1 = constructed_exam(predicted=("FALSE",) * 12, seed=7)
        cohort2, last2 = constructed_exam(predicted=("FALSE",) * 12, seed=8)
        a, b = observe_binary_exam(cohort1, last1), observe_binary_exam(cohort2, last2)
        findings = diagnose_history((a, b))
        self.assertEqual(find_signal(findings, LearningSignal.REPETITIVE_ANSWERS,
                                    DiagnosticTarget.GRADE, "X").status,
                         DiagnosticStatus.OBSERVED_LONGITUDINALLY)
        with self.assertRaisesRegex(ValueError, "REPEATED_COHORT"):
            diagnose_history((a, a))
        shifted = deepcopy(cohort2)
        shifted["rubric_sha256"] = "b" * 64
        last2["exam_rubric_sha256"] = shifted["rubric_sha256"]
        with self.assertRaisesRegex(ValueError, "INCOMPARABLE_RUBRIC"):
            diagnose_history((a, observe_binary_exam(shifted, last2)))

    def test_corrupt_cohort_gold_misses_and_scores_are_not_silent_passes(self):
        cohort, last = constructed_exam(predicted=("FALSE",) * 12)
        bad = deepcopy(cohort)
        bad["rows"][0]["gold"] = "TRUE"
        with self.assertRaisesRegex(ValueError, "CONTENT_DRIFT"):
            observe_binary_exam(bad, last)
        bad = deepcopy(last)
        bad["misses_for_teacher"].pop()
        with self.assertRaisesRegex(ValueError, "SCORE_EVIDENCE_DRIFT"):
            observe_binary_exam(cohort, bad)
        bad = deepcopy(last)
        bad["misses_for_teacher"][0]["predicted"] = "NO"
        with self.assertRaisesRegex(ValueError, "MISS_EVIDENCE_DRIFT"):
            observe_binary_exam(cohort, bad)
        bad = deepcopy(cohort)
        bad["rows"][0]["answer_kind"] = "integer"
        bad["cohort_sha256"] = make_cohort(bad["rows"],
            generator_version=bad["generator_version"], seed=bad["seed"],
            rubric_version=bad["schema"]).digest
        last["cohort_sha256"] = bad["cohort_sha256"]
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_PREDICTION_CASTE"):
            observe_binary_exam(bad, last)

    def test_a_missing_or_outside_saved_run_cannot_be_loaded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "state.json").write_text('{}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "EXAM_NOT_MEASURED"):
                load_saved_exam(root)
            with self.assertRaisesRegex(ValueError, "STATE_OUTSIDE_RUN"):
                load_saved_exam(root, state_file=ROOT / "README.md")

    def test_actual_human_saved_grade_b_is_near_baseline_not_constant_collapse(self):
        if not (LIVE / "state.json").exists():
            self.skipTest("Human-run JSON evidence not mounted")
        exam = load_saved_exam(LIVE)
        a = exam.grade_total("A")
        b = exam.grade_total("B")
        self.assertEqual((a.correct, a.total, a.predicted_false, a.predicted_true),
                         (55, 72, 31, 41))
        self.assertEqual((b.correct, b.total, b.predicted_false, b.predicted_true,
                          b.gold_false, b.gold_true), (33, 72, 37, 35, 36, 36))
        findings = diagnose_exam(exam)
        self.assertEqual(find_signal(findings, LearningSignal.REPETITIVE_ANSWERS,
                                    DiagnosticTarget.GRADE, "B").status,
                         DiagnosticStatus.NOT_OBSERVED)
        self.assertEqual(find_signal(findings, LearningSignal.CHANCE_LEVEL_OR_LAGGING,
                                    DiagnosticTarget.GRADE, "B").status,
                         DiagnosticStatus.OBSERVED_IN_COHORT)

    def test_actual_39_exam_history_reconstructs_without_neural_reads(self):
        if not (LIVE / "events.jsonl").exists():
            self.skipTest("Human-run JSON evidence not mounted")
        history = load_archived_exam_history(LIVE, grade="B")
        self.assertEqual(len(history), 39)
        self.assertEqual(history[-1].optimizer_step, 155640)
        self.assertEqual(history[-1].grade_total("B").correct, 33)
        self.assertTrue(any(f.target is DiagnosticTarget.GRADE and
                            f.capability == "B" for f in diagnose_history(history)))


if __name__ == "__main__":
    unittest.main()
