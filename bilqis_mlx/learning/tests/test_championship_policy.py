"""Mechanical proof of the user-directed cross-origin championship rule."""
from copy import deepcopy
from unittest import TestCase

from bilqis_mlx.learning.championship_policy import cross_origin_takeover


GRADE_B = tuple("B." + cap for cap in
                ("AND", "IFF", "IMPLIES", "NOT", "OR", "XOR"))
SCHOOL = tuple("A." + str(i) for i in range(6)) + GRADE_B + tuple(
    "C." + str(i) for i in range(6))


def _exam(seed, school_correct):
    scores = {cap: {"correct": 12, "total": 12} for cap in SCHOOL}
    # Keep the target grade perfect; put all missing school answers in C.
    remaining = 216 - school_correct
    for cap in SCHOOL[-6:]:
        reduction = min(remaining, 12)
        scores[cap]["correct"] -= reduction
        remaining -= reduction
    assert remaining == 0
    return {
        "checkpoint": {"filename": "bundles/" + seed,
                       "sha256": seed * 64,
                       "optimizer_step": 10,
                       "model_and_native_adamw": True},
        "cohort_sha256": "1" * 64, "rubric_sha256": "2" * 64,
        "assessment_scope_sha256": "3" * 64,
        "source_graph_sha256": "4" * 64,
        "source_oracle_sha256": "5" * 64,
        "scores": scores,
    }


def _decision(challenger, *incumbents):
    role_owners = {cap: ("a" if n < 4 else "b") * 64
                   for n, cap in enumerate(GRADE_B)}
    return cross_origin_takeover(
        grade_capabilities=GRADE_B, admitted_capabilities=SCHOOL,
        active_role_owners=role_owners,
        challenger_exam=challenger,
        incumbent_exams={seed * 64: exam
                         for seed, exam in zip(("a", "b"), incumbents)},
    )


class CrossOriginChampionshipContractTests(TestCase):
    def test_uncontested_first_grade_uses_only_grade_evidence(self):
        candidate = _exam("c", 209)
        candidate["scores"] = {cap: candidate["scores"][cap] for cap in GRADE_B}
        result = cross_origin_takeover(
            grade_capabilities=GRADE_B, admitted_capabilities=SCHOOL,
            active_role_owners={}, challenger_exam=candidate, incumbent_exams={})
        self.assertEqual(result["decision"], "ELIGIBLE_UNCONTESTED_GRADE")
        self.assertEqual(result["target_capabilities"], list(GRADE_B))
        self.assertIsNone(result["school_correct"])
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_CUMULATIVE"):
            cross_origin_takeover(
                grade_capabilities=GRADE_B, admitted_capabilities=SCHOOL,
                active_role_owners={"B.XOR": "a"*64},
                challenger_exam=candidate,
                incumbent_exams={"a"*64: _exam("a", 208)})

    def test_uncontested_grade_can_earn_first_roles_with_full_grade_perfection(self):
        candidate = _exam("c", 208)
        result = cross_origin_takeover(
            grade_capabilities=GRADE_B, admitted_capabilities=SCHOOL,
            active_role_owners={}, challenger_exam=candidate,
            incumbent_exams={})
        self.assertEqual(result["decision"], "ELIGIBLE_UNCONTESTED_GRADE")
        candidate["scores"]["B.XOR"]["correct"] = 11
        result = cross_origin_takeover(
            grade_capabilities=GRADE_B, admitted_capabilities=SCHOOL,
            active_role_owners={}, challenger_exam=candidate,
            incumbent_exams={})
        self.assertEqual(result["decision"], "DENY_TARGET_GRADE_NOT_PERFECT")
    def test_complete_grade_and_superior_school_beats_every_role_owner(self):
        challenger = _exam("c", 209)
        incumbents = _exam("a", 207), _exam("b", 208)
        original = deepcopy(challenger)
        result = _decision(challenger, *incumbents)
        self.assertEqual(result["decision"], "ELIGIBLE")
        self.assertEqual(result["target_capabilities"], list(GRADE_B))
        self.assertEqual(result["school_correct"], 209)
        self.assertEqual(len(result["incumbents"]), 2)
        self.assertEqual(challenger, original)

    def test_tie_with_strongest_owner_rejects_full_grade_takeover(self):
        self.assertEqual(_decision(_exam("c", 208), _exam("a", 207),
                                   _exam("b", 208))["decision"],
                         "DENY_NO_STRICT_SCHOOL_VICTORY")

    def test_more_school_answers_cannot_hide_one_wrong_grade_b_answer(self):
        challenger = _exam("c", 210)
        challenger["scores"]["B.XOR"]["correct"] = 11
        challenger["scores"]["C.0"]["correct"] += 1
        result = _decision(challenger, _exam("a", 207), _exam("b", 208))
        self.assertEqual(result["school_correct"], 210)
        self.assertEqual(result["decision"], "DENY_TARGET_GRADE_NOT_PERFECT")

    def test_current_grade_perfect_with_lower_school_score_is_not_enough(self):
        self.assertEqual(_decision(_exam("c", 206), _exam("a", 207),
                                   _exam("b", 208))["decision"],
                         "DENY_NO_STRICT_SCHOOL_VICTORY")

    def test_one_unproven_or_different_cohort_incumbent_fails_closed(self):
        candidate = _exam("c", 209)
        a, b = _exam("a", 207), _exam("b", 208)
        b["cohort_sha256"] = "6" * 64
        with self.assertRaisesRegex(ValueError, "INCOMPARABLE"):
            _decision(candidate, a, b)
        b = _exam("b", 208)
        b["scores"].pop("A.0")
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_CUMULATIVE"):
            _decision(candidate, a, b)
        b = _exam("b", 208)
        b["scores"]["C.0"]["total"] = 11
        with self.assertRaisesRegex(ValueError, "INVALID_SOURCE_SCORES|INCOMPARABLE"):
            _decision(candidate, a, b)

    def test_extra_role_and_missing_incumbent_cannot_succeed(self):
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_TARGET"):
            cross_origin_takeover(
                grade_capabilities=GRADE_B,
                admitted_capabilities=SCHOOL,
                active_role_owners={"A.0": "a" * 64},
                challenger_exam=_exam("c", 209),
                incumbent_exams={"a" * 64: _exam("a", 208)},
            )
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_TARGET"):
            cross_origin_takeover(
                grade_capabilities=GRADE_B,
                admitted_capabilities=SCHOOL,
                active_role_owners={cap: "a" * 64 for cap in GRADE_B},
                challenger_exam=_exam("c", 209),
                incumbent_exams={},
            )

    def test_own_checkpoint_or_different_graph_cannot_take_over(self):
        self.assertEqual(_decision(_exam("a", 210), _exam("a", 207),
                                   _exam("b", 208))["decision"],
                         "DENY_EXISTING_OWNER")
        altered = _exam("c", 209)
        altered["source_graph_sha256"] = "9" * 64
        with self.assertRaisesRegex(ValueError, "INCOMPARABLE"):
            _decision(altered, _exam("a", 207), _exam("b", 208))
