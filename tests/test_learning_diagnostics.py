"""Actual archived A/B evidence and falsifying negative diagnostic controls.

These tests never load student model weights or mutate training state.
"""
from copy import deepcopy
import hashlib
import json
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
    student_sha = hashlib.sha256(str(seed).encode()).hexdigest()
    measured = score(cohort, predictions, dict(sha256=student_sha,
                 optimizer_step=100 + seed, model_and_native_adamw=True))
    last_exam = dict(cohort_sha256=cohort.digest, cohort_seed=seed,
                     generator_version=cohort.generator_version,
                     exam_rubric_sha256=payload["rubric_sha256"],
                     student_sha256=student_sha, optimizer_step=100 + seed,
                     scores=measured["scores"],
                     misses_for_teacher=list(measured["misses_for_teacher"]))
    return payload, last_exam


def find_signal(findings, signal, target, capability):
    return next(x for x in findings if x.signal is signal and x.target is target
                and x.capability == capability)


class DiagnosticObservationTests(unittest.TestCase):
    def test_single_gold_class_does_not_make_perfect_answers_a_chance_alarm(self):
        cohort, last = constructed_exam(predicted=("TRUE",) * 12)
        for row in cohort["rows"]:
            row["gold"] = "TRUE"
        cohort["cohort_sha256"] = make_cohort(cohort["rows"],
            generator_version=cohort["generator_version"], seed=cohort["seed"],
            rubric_version=cohort["schema"]).digest
        last.update(cohort_sha256=cohort["cohort_sha256"], misses_for_teacher=[],
                    scores={"X.NOT": {"correct": 12, "total": 12}})
        findings = diagnose_exam(observe_binary_exam(cohort, last))
        for signal in (LearningSignal.REPETITIVE_ANSWERS,
                       LearningSignal.CHANCE_LEVEL_OR_LAGGING):
            self.assertEqual(find_signal(findings, signal,
                DiagnosticTarget.CAPABILITY, "X.NOT").status,
                DiagnosticStatus.NOT_MEASURED)

    def test_pooled_labels_cannot_hide_single_class_capabilities(self):
        cohort, last = constructed_exam(predicted=("FALSE",) * 6 + ("TRUE",) * 6)
        for i, row in enumerate(cohort["rows"]):
            row.update(capability="X.A" if i < 6 else "X.B",
                       gold="FALSE" if i < 6 else "TRUE")
        cohort["cohort_sha256"] = make_cohort(cohort["rows"],
            generator_version=cohort["generator_version"], seed=cohort["seed"],
            rubric_version=cohort["schema"]).digest
        last.update(cohort_sha256=cohort["cohort_sha256"], misses_for_teacher=[],
                    scores={c: {"correct": 6, "total": 6} for c in ("X.A", "X.B")})
        observed = observe_binary_exam(cohort, last)
        findings = diagnose_exam(observed)
        for name, target in (("X", DiagnosticTarget.GRADE),
                             ("*", DiagnosticTarget.WHOLE_STUDENT)):
            finding = find_signal(findings, LearningSignal.CHANCE_LEVEL_OR_LAGGING,
                                  target, name)
            self.assertEqual(finding.status, DiagnosticStatus.NOT_MEASURED)
            self.assertEqual(finding.majority_baseline, 12)

    def test_repeated_checkpoint_is_not_a_learning_trajectory(self):
        cohort1, last1 = constructed_exam(predicted=("FALSE",) * 12, seed=7)
        cohort2, last2 = constructed_exam(predicted=("FALSE",) * 12, seed=8)
        last2.update(student_sha256=last1["student_sha256"],
                     optimizer_step=last1["optimizer_step"])
        with self.assertRaisesRegex(ValueError, "REPEATED_CHECKPOINT"):
            diagnose_history((observe_binary_exam(cohort1, last1),
                              observe_binary_exam(cohort2, last2)))

    def test_checkpoint_order_is_evidence_and_must_not_be_sorted(self):
        a = observe_binary_exam(*constructed_exam(predicted=("FALSE",) * 12, seed=8))
        b = observe_binary_exam(*constructed_exam(predicted=("FALSE",) * 12, seed=7))
        with self.assertRaisesRegex(ValueError, "NON_MONOTONIC"):
            diagnose_history((a, b))

    def test_recent_persistent_failure_survives_an_older_good_score(self):
        good, good_last = constructed_exam(predicted=("FALSE", "TRUE") * 6, seed=6)
        bad1, last1 = constructed_exam(predicted=("FALSE",) * 12, seed=7)
        bad2, last2 = constructed_exam(predicted=("FALSE",) * 12, seed=8)
        findings = diagnose_history(observe_binary_exam(c, e)
            for c, e in ((good, good_last), (bad1, last1), (bad2, last2)))
        finding = find_signal(findings, LearningSignal.CHANCE_LEVEL_OR_LAGGING,
                              DiagnosticTarget.CAPABILITY, "X.NOT")
        self.assertEqual(finding.status, DiagnosticStatus.OBSERVED_LONGITUDINALLY)
        self.assertEqual(finding.evidence_count, 2)

    def test_extra_score_capability_and_negative_step_are_rejected(self):
        cohort, last = constructed_exam(predicted=("FALSE",) * 12)
        bad = deepcopy(last)
        bad["scores"]["UNKNOWN"] = {"correct": 1, "total": 1}
        with self.assertRaisesRegex(ValueError, "SCORE_EVIDENCE_DRIFT"):
            observe_binary_exam(cohort, bad)
        last["optimizer_step"] = -1
        with self.assertRaisesRegex(ValueError, "CUSTODY_MISMATCH"):
            observe_binary_exam(cohort, last)

    def test_nonconsecutive_low_scores_are_not_a_sustained_warning(self):
        findings = diagnose_history(observe_binary_exam(*constructed_exam(
            predicted=values, seed=seed)) for seed, values in (
                (7, ("FALSE",) * 12), (8, ("FALSE", "TRUE") * 6),
                (9, ("FALSE",) * 12)))
        finding = find_signal(findings, LearningSignal.CHANCE_LEVEL_OR_LAGGING,
                              DiagnosticTarget.CAPABILITY, "X.NOT")
        self.assertEqual(finding.status, DiagnosticStatus.OBSERVED_IN_COHORT)
        self.assertEqual(finding.evidence_count, 1)

    def test_malformed_identity_and_bool_scores_do_not_verify(self):
        cohort, last = constructed_exam(predicted=("FALSE",) * 12)
        for sha in (True, "x", "z" * 64):
            with self.subTest(sha=sha):
                bad = deepcopy(last)
                bad["student_sha256"] = sha
                with self.assertRaisesRegex(ValueError, "CUSTODY_MISMATCH"):
                    observe_binary_exam(cohort, bad)
        last["scores"]["X.NOT"]["total"] = True
        with self.assertRaisesRegex(ValueError, "SCORE_EVIDENCE_DRIFT"):
            observe_binary_exam(cohort, last)

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
