"""Actual archived A/B evidence and falsifying negative diagnostic controls.

These tests never load student model weights or mutate training state.
"""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.diagnostics import (DiagnosticStatus, DiagnosticTarget,
    LearningSignal, diagnose_exam, diagnose_history, load_archived_exam_history,
    load_saved_exam, observe_binary_exam)
from bilqis_mlx.diagnostics.observations import observe_exam
from bilqis_mlx.diagnostics.exam_events import apply_paired_checkpoint_s3
from bilqis_mlx.generated_assessment import make_cohort, score


ROOT = Path(__file__).resolve().parents[3]
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


def rescore_fixed_exam(cohort, earlier, predicted, *, step, student_sha):
    """Another real score of the same test, on a different intact checkpoint."""
    recorded = make_cohort(cohort["rows"],
        generator_version=cohort["generator_version"], seed=cohort["seed"],
        rubric_version=cohort["schema"])
    measured = score(recorded, {row["id"]: answer
                             for row, answer in zip(cohort["rows"], predicted)},
                     dict(sha256=student_sha, optimizer_step=step,
                          model_and_native_adamw=True))
    return {**earlier, "student_sha256": student_sha, "optimizer_step": step,
            "scores": measured["scores"],
            "misses_for_teacher": list(measured["misses_for_teacher"])}


class DiagnosticObservationTests(unittest.TestCase):
    def test_v2_envelope_binds_source_release_and_scope_separately_from_rubric(self):
        cohort, exam = constructed_exam(predicted=("TRUE", "FALSE", "FALSE", "TRUE"))
        rubric = "c" * 64
        source = "d" * 64
        cohort.update(schema="bilqis.mlx.generated-cohort/v2", rubric_sha256=rubric,
                      source_sha256=source, generator_version=source,
                      factory_release_sha256="e" * 64, capabilities=["X.NOT"])
        cohort["cohort_sha256"] = make_cohort(
            cohort["rows"], generator_version=source, seed=cohort["seed"],
            rubric_version=rubric).digest
        exam.update(cohort_sha256=cohort["cohort_sha256"], generator_version=source,
                    exam_rubric_sha256=rubric, rubric_sha256=rubric,
                    source_sha256=source, factory_release_sha256="e" * 64,
                    capabilities=["X.NOT"])
        observed = observe_exam(cohort, exam)
        self.assertEqual(observed.capabilities[0].correct, exam["scores"]["X.NOT"]["correct"])
        for field in ("exam_rubric_sha256", "rubric_sha256", "source_sha256", "factory_release_sha256", "capabilities"):
            wrong = deepcopy(exam)
            wrong[field] = ["X.OTHER"] if field == "capabilities" else "f" * 64
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "CUSTODY"):
                observe_exam(cohort, wrong)
        for field in ("source_sha256", "factory_release_sha256", "capabilities"):
            missing = deepcopy(cohort)
            missing.pop(field)
            with self.subTest(missing=field), self.assertRaisesRegex(ValueError, "CUSTODY"):
                observe_exam(missing, exam)

    def test_v2_cohort_digest_uses_stored_rubric_identity(self):
        rows = [
            {"id": f"v2-{index}", "source_id": f"v2-{index}",
             "capability": "X.NOT", "answer_kind": "binary",
             "gold": "TRUE" if index % 2 else "FALSE"}
            for index in range(12)
        ]
        rubric = "c" * 64
        release = "d" * 64
        cohort = make_cohort(
            rows, generator_version="source-fixture-v2", seed=41,
            rubric_version=rubric)
        payload = {
            "schema": "bilqis.mlx.generated-cohort/v2",
            "factory_release_sha256": release,
            "rubric_sha256": rubric,
            "generator_version": cohort.generator_version,
            "seed": cohort.seed,
            "cohort_sha256": cohort.digest,
            "rows": rows,
        }
        predictions = {row["id"]: row["gold"] for row in rows}
        measured = score(cohort, predictions, {
            "sha256": "a" * 64,
            "optimizer_step": 500,
            "model_and_native_adamw": True,
        })
        exam = {
            "cohort_sha256": cohort.digest,
            "cohort_seed": cohort.seed,
            "generator_version": cohort.generator_version,
            "rubric_sha256": rubric,
            "factory_release_sha256": release,
            "exam_rubric_sha256": rubric,
            "student_sha256": "a" * 64,
            "optimizer_step": 500,
            "scores": measured["scores"],
            "misses_for_teacher": list(measured["misses_for_teacher"]),
        }

        observed = observe_exam(payload, exam)
        self.assertEqual(observed.cohort_sha256, cohort.digest)

        drifted = deepcopy(payload)
        drifted["factory_release_sha256"] = "e" * 64
        with self.assertRaisesRegex(ValueError, "CUSTODY|METADATA|RELEASE"):
            observe_exam(drifted, exam)

        drifted = deepcopy(payload)
        drifted["schema"] = "historical-release/v1"
        with self.assertRaisesRegex(ValueError, "CUSTODY|METADATA|RELEASE"):
            observe_exam(drifted, exam)

    def test_six_way_operator_identity_uses_two_of_twelve_majority_baseline(self):
        operators = ("NOT", "AND", "OR", "XOR", "IMPLIES", "IFF")
        rows = [
            {"id": f"id-op-{i}", "source_id": f"id-op-{i}",
             "capability": "B.IDBOOLOPS", "answer_kind": "boolean_operator",
             "gold": operators[i % len(operators)]}
            for i in range(12)
        ]
        cohort = make_cohort(rows, generator_version="idboolops-fixture", seed=71,
                             rubric_version="idboolops-rubric")
        payload = {
            "schema": cohort.rubric_version,
            "rubric_sha256": "c" * 64,
            "generator_version": cohort.generator_version,
            "seed": cohort.seed,
            "cohort_sha256": cohort.digest,
            "rows": rows,
        }
        predictions = {row["id"]: "AND" for row in rows}
        measured = score(cohort, predictions, {
            "sha256": "a" * 64,
            "optimizer_step": 500,
            "model_and_native_adamw": True,
        })
        exam = {
            "cohort_sha256": cohort.digest,
            "cohort_seed": cohort.seed,
            "generator_version": cohort.generator_version,
            "exam_rubric_sha256": payload["rubric_sha256"],
            "student_sha256": "a" * 64,
            "optimizer_step": 500,
            "scores": measured["scores"],
            "misses_for_teacher": list(measured["misses_for_teacher"]),
        }
        observed = observe_exam(payload, exam)
        cap = observed.capabilities[0]
        self.assertEqual(cap.correct, 2)
        self.assertEqual(cap.majority_baseline, 2)
        self.assertTrue(cap.constant_prediction)
        self.assertEqual(dict(cap.gold_counts), {operator: 2 for operator in operators})
        chance = find_signal(
            diagnose_exam(observed), LearningSignal.CHANCE_LEVEL_OR_LAGGING,
            DiagnosticTarget.CAPABILITY, "B.IDBOOLOPS")
        self.assertEqual(chance.majority_baseline, 2)
        self.assertEqual(chance.status, DiagnosticStatus.OBSERVED_IN_COHORT)

    def test_explicit_lineage_rebase_does_not_poison_latest_branch_s3(self):
        cohort, first = constructed_exam(predicted=("FALSE",) * 12)
        old = replace(observe_binary_exam(cohort, rescore_fixed_exam(
            cohort, first, ("FALSE",) * 12,
            step=500, student_sha="f" * 64)),
            run_id="run", lineage_id="run-root/run")
        first_branch = replace(observe_binary_exam(cohort, rescore_fixed_exam(
            cohort, first, ("FALSE",) * 12,
            step=100, student_sha="a" * 64)),
            run_id="run", lineage_id="experiment-rebase/branch")
        gold = tuple(row["gold"] for row in cohort["rows"])
        middle = replace(observe_binary_exam(cohort, rescore_fixed_exam(
            cohort, first, gold[:9] + ("FALSE",) * 3,
            step=116, student_sha="b" * 64)),
            run_id="run", lineage_id="experiment-rebase/branch")
        latest = replace(observe_binary_exam(cohort, rescore_fixed_exam(
            cohort, first, ("FALSE",) * 12,
            step=132, student_sha="c" * 64)),
            run_id="run", lineage_id="experiment-rebase/branch")
        finding = find_signal(
            diagnose_history((old, first_branch, middle, latest)),
            LearningSignal.LACK_OF_DURABLE_GAIN,
            DiagnosticTarget.CAPABILITY, "X.NOT")
        self.assertEqual(finding.status, DiagnosticStatus.OBSERVED_LONGITUDINALLY)
        self.assertEqual(tuple(step for step, _, _ in finding.trajectory),
                         (100, 116, 132))

    def test_fresh_cohort_parent_pair_makes_s3_measurable_without_freezing_exam(self):
        cohort, current_exam = constructed_exam(predicted=("FALSE",) * 12)
        current = observe_binary_exam(cohort, current_exam)
        summary = {
            "findings": [asdict(finding) for finding in diagnose_exam(current)
                         if finding.target in (DiagnosticTarget.CAPABILITY,
                                               DiagnosticTarget.GRADE)],
            "active_warnings": [],
        }
        updated = apply_paired_checkpoint_s3(
            summary,
            parent_scores={"X.NOT": {"correct": 6, "total": 12}},
            current_scores={"X.NOT": {"correct": 6, "total": 12}},
            parent_sha256="a" * 64, current_sha256="b" * 64,
            parent_step=100, current_step=116,
            cohort_sha256=cohort["cohort_sha256"])
        s3 = next(item for item in updated["findings"]
                  if item["signal"] == LearningSignal.LACK_OF_DURABLE_GAIN and
                  item["target"] == DiagnosticTarget.CAPABILITY)
        self.assertEqual(s3["status"], DiagnosticStatus.OBSERVED_LONGITUDINALLY.value)
        self.assertEqual(s3["trajectory"], ((100, 6, 12), (116, 6, 12)))
        self.assertTrue(updated["s3_usable"])
        self.assertTrue(any(item["signal"] == LearningSignal.LACK_OF_DURABLE_GAIN
                            for item in updated["active_warnings"]))

    def test_paired_s3_does_not_call_stable_perfection_stagnation(self):
        cohort, current_exam = constructed_exam(predicted=("FALSE", "TRUE") * 6)
        current = observe_binary_exam(cohort, current_exam)
        summary = {
            "findings": [asdict(finding) for finding in diagnose_exam(current)
                         if finding.target in (DiagnosticTarget.CAPABILITY,
                                               DiagnosticTarget.GRADE)],
            "active_warnings": [],
        }
        updated = apply_paired_checkpoint_s3(
            summary,
            parent_scores={"X.NOT": {"correct": 12, "total": 12}},
            current_scores={"X.NOT": {"correct": 12, "total": 12}},
            parent_sha256="a" * 64, current_sha256="b" * 64,
            parent_step=100, current_step=116,
            cohort_sha256=cohort["cohort_sha256"])
        s3 = next(item for item in updated["findings"]
                  if item["signal"] == LearningSignal.LACK_OF_DURABLE_GAIN and
                  item["target"] == DiagnosticTarget.CAPABILITY)
        self.assertEqual(s3["status"], DiagnosticStatus.NOT_OBSERVED.value)
        self.assertFalse(any(item["signal"] == LearningSignal.LACK_OF_DURABLE_GAIN
                             for item in updated["active_warnings"]))

    def test_already_perfect_fixed_exam_across_distinct_checkpoints_is_not_stalled(self):
        cohort, first = constructed_exam(predicted=("FALSE", "TRUE") * 6)
        gold = tuple(row["gold"] for row in cohort["rows"])
        middle = rescore_fixed_exam(cohort, first, gold,
                                    step=123, student_sha="a" * 64)
        latest = rescore_fixed_exam(cohort, first, gold,
                                    step=139, student_sha="b" * 64)
        evidence = (observe_binary_exam(cohort, item)
                    for item in (first, middle, latest))
        durable = find_signal(diagnose_history(evidence),
                              LearningSignal.LACK_OF_DURABLE_GAIN,
                              DiagnosticTarget.CAPABILITY, "X.NOT")
        self.assertEqual(durable.status, DiagnosticStatus.NOT_OBSERVED)
        self.assertEqual(durable.trajectory,
                         ((107, 12, 12), (123, 12, 12), (139, 12, 12)))

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

    def test_exam_observation_separates_cohort_provenance_from_assessment_rubric(self):
        cohort, last = constructed_exam(predicted=("FALSE",) * 12)
        cohort["rubric_sha256"] = "c" * 64
        last["exam_rubric_sha256"] = "d" * 64
        observed = observe_binary_exam(cohort, last)
        self.assertEqual(observed.rubric_sha256, "d" * 64)

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
        with self.assertRaisesRegex(ValueError, "REPEATED_CHECKPOINT"):
            diagnose_history((a, a))
        shifted = deepcopy(cohort2)
        shifted["rubric_sha256"] = "b" * 64
        last2["exam_rubric_sha256"] = shifted["rubric_sha256"]
        with self.assertRaisesRegex(ValueError, "INCOMPARABLE_RUBRIC"):
            diagnose_history((a, observe_binary_exam(shifted, last2)))

    def test_fixed_qualification_questions_are_valid_again_on_new_student_checkpoints(self):
        cohort, first = constructed_exam(predicted=("FALSE",) * 12)
        better = rescore_fixed_exam(cohort, first,
                    tuple(row["gold"] for row in cohort["rows"]),
                    step=first["optimizer_step"] + 16, student_sha="a" * 64)
        observations = (observe_binary_exam(cohort, first),
                        observe_binary_exam(cohort, better))
        results = diagnose_history(observations)
        finding = find_signal(results, LearningSignal.CHANCE_LEVEL_OR_LAGGING,
                              DiagnosticTarget.GRADE, "X")
        self.assertEqual(finding.status, DiagnosticStatus.NOT_OBSERVED)
        self.assertEqual(finding.source_cohorts, (cohort["cohort_sha256"],))

    def test_s3_detects_transient_gain_lost_on_the_same_grade_exam(self):
        cohort, first = constructed_exam(predicted=("FALSE",) * 12)
        golds = tuple(row["gold"] for row in cohort["rows"])
        middle = rescore_fixed_exam(cohort, first, golds[:10] + ("FALSE", "FALSE"),
                    step=123, student_sha="a" * 64)
        last = rescore_fixed_exam(cohort, first, ("FALSE",) * 12,
                    step=139, student_sha="b" * 64)
        observations = tuple(observe_binary_exam(cohort, receipt)
                             for receipt in (first, middle, last))
        result = find_signal(diagnose_history(observations),
                LearningSignal.LACK_OF_DURABLE_GAIN, DiagnosticTarget.GRADE, "X")
        self.assertEqual(result.status, DiagnosticStatus.OBSERVED_LONGITUDINALLY)
        self.assertEqual(result.trajectory,
                         ((107, 6, 12), (123, 11, 12), (139, 6, 12)))

    def test_s3_durable_improvement_is_not_falsely_flagged(self):
        cohort, first = constructed_exam(predicted=("FALSE",) * 12)
        golds = tuple(row["gold"] for row in cohort["rows"])
        middle = rescore_fixed_exam(cohort, first, golds[:8] + ("FALSE",) * 4,
                    step=123, student_sha="a" * 64)
        last = rescore_fixed_exam(cohort, first, golds,
                    step=139, student_sha="b" * 64)
        observations = tuple(observe_binary_exam(cohort, receipt)
                             for receipt in (first, middle, last))
        result = find_signal(diagnose_history(observations),
                LearningSignal.LACK_OF_DURABLE_GAIN, DiagnosticTarget.GRADE, "X")
        self.assertEqual(result.status, DiagnosticStatus.NOT_OBSERVED)
        self.assertEqual(result.trajectory[-1], (139, 12, 12))

    def test_s3_partial_regression_is_visible_even_with_some_retained_gain(self):
        cohort, first = constructed_exam(predicted=("FALSE",) * 12)
        golds = tuple(row["gold"] for row in cohort["rows"])
        middle = rescore_fixed_exam(cohort, first, golds[:10] + ("FALSE", "FALSE"),
                    step=123, student_sha="a" * 64)
        partial = rescore_fixed_exam(cohort, first, golds[:4] + ("FALSE",) * 8,
                    step=139, student_sha="b" * 64)
        results = diagnose_history(observe_binary_exam(cohort, item)
                                   for item in (first, middle, partial))
        finding = find_signal(results, LearningSignal.LACK_OF_DURABLE_GAIN,
                              DiagnosticTarget.GRADE, "X")
        self.assertEqual(finding.status, DiagnosticStatus.OBSERVED_LONGITUDINALLY)
        self.assertIn("regressed", finding.note)

    def test_s3_does_not_infer_retention_from_rotating_tests_or_two_scores(self):
        cohort, first = constructed_exam(predicted=("FALSE",) * 12)
        second = rescore_fixed_exam(cohort, first, ("FALSE",) * 12,
                    step=123, student_sha="a" * 64)
        observations = [observe_binary_exam(cohort, r) for r in (first, second)]
        s3 = find_signal(diagnose_history(observations),
                    LearningSignal.LACK_OF_DURABLE_GAIN, DiagnosticTarget.GRADE, "X")
        self.assertEqual(s3.status, DiagnosticStatus.NOT_MEASURED)
        another_cohort, third = constructed_exam(predicted=("FALSE",) * 12, seed=139)
        observations.append(observe_binary_exam(another_cohort, third))
        s3 = find_signal(diagnose_history(observations),
                    LearningSignal.LACK_OF_DURABLE_GAIN, DiagnosticTarget.GRADE, "X")
        self.assertEqual(s3.status, DiagnosticStatus.NOT_MEASURED)

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
        self.assertEqual(a.total, 72)
        self.assertEqual(b.total, 72)
        self.assertEqual(a.predicted_false + a.predicted_true, 72)
        self.assertEqual(b.predicted_false + b.predicted_true, 72)
        self.assertEqual(b.gold_false + b.gold_true, 72)
        findings = diagnose_exam(exam)
        self.assertEqual(find_signal(findings, LearningSignal.REPETITIVE_ANSWERS,
                                    DiagnosticTarget.GRADE, "B").status,
                         DiagnosticStatus.NOT_OBSERVED)
        self.assertIn(find_signal(findings, LearningSignal.CHANCE_LEVEL_OR_LAGGING,
                                  DiagnosticTarget.GRADE, "B").status,
                      (DiagnosticStatus.OBSERVED_IN_COHORT, DiagnosticStatus.NOT_OBSERVED))

    def test_actual_39_exam_history_reconstructs_without_neural_reads(self):
        if not (LIVE / "events.jsonl").exists():
            self.skipTest("Human-run JSON evidence not mounted")
        history = load_archived_exam_history(LIVE, grade="B")
        self.assertGreaterEqual(len(history), 39)
        self.assertGreaterEqual(history[-1].optimizer_step, 155640)
        self.assertEqual(history[-1].grade_total("B").total, 72)
        latest_identity = history[-1].contract
        compatible = [exam for exam in history if exam.contract == latest_identity]
        if len(compatible) > 1:
            self.assertTrue(any(f.target is DiagnosticTarget.GRADE and
                                f.capability == "B" for f in diagnose_history(compatible)))


if __name__ == "__main__":
    unittest.main()
