"""The complete school, not a soup or isolated grade, awards epoch titles."""
from copy import deepcopy
from types import MappingProxyType
from unittest import TestCase

from bilqis_mlx.epoch_championships import (
    active_frontier, advance_epoch, needed_incumbents,
    rebase_active_championships, reset_active_championships)
from bilqis_mlx.mentor_epoch import EARNED_ONLY_POLICY
from bilqis_mlx.grade_soup import grade_soup_recipe
from tests.test_championship_policy import GRADE_B, SCHOOL, _exam

GRADES = MappingProxyType({
    "A": tuple(cap for cap in SCHOOL if cap.startswith("A.")),
    "B": GRADE_B,
    "C": tuple(cap for cap in SCHOOL if cap.startswith("C.")),
})


def _epoch():
    return {
        "introduced_grade": "C",
        "baseline": _exam("b", 208)["checkpoint"],
        "previous_capabilities": list(GRADES["A"] + GRADES["B"]),
        "qualified": [],
        "historical_advisers_remain_archived": True,
    }


class EpochChampionshipTests(TestCase):
    def test_experiment_rebase_clears_active_titles_and_requires_baseline_victory(self):
        epoch = _epoch()
        first, _, _ = advance_epoch(
            epoch, grades=GRADES, challenger_exam=_exam("c", 209),
            incumbent_exams={})
        first["active_grade_soups"] = {
            "C": grade_soup_recipe(active_frontier(first), "C", GRADES["C"])}
        old_student = _exam("d", 210)["checkpoint"]
        baseline = _exam("e", 208)["checkpoint"]
        rebased = rebase_active_championships(
            first, prior_student=old_student, baseline=baseline,
            generation=500)
        self.assertEqual(rebased["active_roles"], {})
        self.assertEqual(rebased["active_grade_soups"], {})
        self.assertEqual(rebased["qualified"], [])
        self.assertEqual(rebased["baseline"], baseline)
        self.assertTrue(rebased["baseline_challenge_required"])
        self.assertIsNone(rebased["baseline_surpassed"])
        self.assertEqual(rebased["championship_eligibility_after_step"],
                         baseline["optimizer_step"])

    def test_baseline_challenge_blocks_titles_until_strict_same_cohort_victory(self):
        epoch = _epoch()
        epoch["baseline_challenge_required"] = True
        epoch["baseline_surpassed"] = None
        baseline_exam = _exam("b", 208)
        contender = _exam("c", 208)
        contender["checkpoint"]["optimizer_step"] = 11
        unchanged, roles, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=contender,
            incumbent_exams={"b" * 64: baseline_exam})
        self.assertEqual(roles, ())
        self.assertEqual(unchanged["active_roles"], {})
        self.assertIsNone(unchanged["baseline_surpassed"])
        self.assertEqual(decisions[0]["decision"], "DENY_BASELINE_NOT_BEATEN")

        winner = _exam("c", 209)
        winner["checkpoint"]["optimizer_step"] = 11
        upgraded, roles, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=winner,
            incumbent_exams={"b" * 64: baseline_exam})
        self.assertTrue(roles)
        self.assertEqual(upgraded["baseline_surpassed"]["checkpoint"]["sha256"],
                         "c" * 64)
        self.assertEqual(upgraded["baseline_surpassed"]["challenger_correct"], 209)
        self.assertEqual(upgraded["baseline_surpassed"]["baseline_correct"], 208)
        self.assertEqual(decisions[0]["decision"], "BASELINE_STRICTLY_SURPASSED")

    def test_needed_incumbents_requests_non_teaching_baseline_until_surpassed(self):
        epoch = _epoch()
        epoch["baseline_challenge_required"] = True
        epoch["baseline_surpassed"] = None
        candidate = _exam("c", 209)
        candidate["checkpoint"]["optimizer_step"] = 11
        needed = needed_incumbents(
            epoch, grades=GRADES, scores=candidate["scores"],
            challenger_checkpoint=candidate["checkpoint"])
        self.assertEqual(needed, {"b" * 64: epoch["baseline"]})

    def test_own_grade_cannot_mint_titles_from_only_a_subset_of_its_capabilities(self):
        candidate = _exam("c", 209)
        candidate["scores"].pop("C.0")
        result, changes, decisions = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=candidate,
            incumbent_exams={})
        self.assertFalse(any(cap.startswith("C.") for cap in changes))
        self.assertFalse(any(cap.startswith("C.") for cap in result["active_roles"]))
        self.assertEqual(next(d["missing_capabilities"] for d in decisions
                              if d["decision"] == "DEFER_ORIGIN_GRADE_INCOMPLETE"),
                         ["C.0"])

    def test_cross_origin_mints_all_or_none_even_when_one_missing(self):
        candidate = _exam("c", 209)
        candidate["scores"].pop("B.XOR")
        untouched, titles, decisions = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=candidate,
            incumbent_exams={})
        self.assertFalse(any(cap.startswith("B.") for cap in titles))
        self.assertFalse(any(cap.startswith("B.") for cap in untouched["active_roles"]))
        self.assertEqual(next(d["missing_capabilities"] for d in decisions
                              if d["grade"] == "B"), ["B.XOR"])
        candidate["scores"]["B.XOR"] = {"correct": 11, "total": 12}
        unchanged, titles, decisions = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=candidate,
            incumbent_exams={})
        self.assertFalse(any(cap.startswith("B.") for cap in titles))
        self.assertFalse(any(cap.startswith("B.") for cap in unchanged["active_roles"]))
        self.assertEqual(next(d["decision"] for d in decisions if d["grade"] == "B"),
                         "DENY_TARGET_GRADE_NOT_PERFECT")

    def test_new_grade_earns_roles_while_prior_soups_stay_archived(self):
        epoch = _epoch()
        candidate = _exam("c", 209)
        before = deepcopy(epoch)
        needed = needed_incumbents(epoch, grades=GRADES,
                                   scores=candidate["scores"])
        self.assertEqual(needed, {})
        upgraded, changes, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=candidate,
            incumbent_exams={})
        self.assertEqual(epoch, before)
        self.assertTrue(set(GRADES["B"]) <= set(changes))
        self.assertTrue(set(GRADES["A"]) <= set(changes))
        self.assertTrue(set(GRADES["C"]) & set(changes))
        self.assertEqual({decision["decision"] for decision in decisions},
                         {"ELIGIBLE_UNCONTESTED_GRADE"})
        self.assertEqual(set(upgraded["active_roles"]["B.XOR"]["perfect_capabilities"]),
                         {cap for cap in SCHOOL
                          if candidate["scores"][cap]["correct"] ==
                          candidate["scores"][cap]["total"]})
        soup = grade_soup_recipe(active_frontier(upgraded), "B", GRADE_B)
        self.assertEqual(soup["vote_count"], 6)
        self.assertEqual(soup["members"][0]["votes"], 6)
        self.assertEqual(upgraded["historical_advisers_remain_archived"], True)

    def test_cross_origin_tie_or_imperfect_grade_preserves_incumbent(self):
        epoch, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=_exam("b", 208),
            incumbent_exams={})
        challenger = _exam("c", 208)
        changed, _, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams={epoch["baseline"]["sha256"]: _exam("b", 208)})
        self.assertEqual(changed["active_roles"]["B.XOR"]["checkpoint"]["sha256"],
                         "b" * 64)
        self.assertEqual({d["decision"] for d in decisions},
                         {"DENY_NO_STRICT_SCHOOL_VICTORY"})
        challenger = _exam("c", 209)
        challenger["scores"]["B.XOR"]["correct"] = 11
        challenger["scores"]["C.0"]["correct"] += 1
        changed, roles, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams={epoch["baseline"]["sha256"]: _exam("b", 208)})
        self.assertNotIn("B.XOR", roles)
        self.assertEqual(changed["active_roles"]["B.XOR"]["checkpoint"]["sha256"],
                         "b" * 64)
        self.assertEqual(next(d["decision"] for d in decisions if d["grade"] == "B"),
                         "DENY_TARGET_GRADE_NOT_PERFECT")

    def test_multi_incumbent_target_grade_must_beat_strongest(self):
        initial = _epoch()
        early, _, _ = advance_epoch(
            initial, grades=GRADES, challenger_exam=_exam("a", 207),
            incumbent_exams={})
        # Distinct winner takes one role in a later exam, simulating a roster
        # with multiple independently qualified checkpoints.
        early["active_roles"]["B.XOR"] = {
            **early["active_roles"]["B.XOR"],
            "checkpoint": _exam("d", 210)["checkpoint"],
        }
        next_exam = _exam("c", 209)
        needed = needed_incumbents(early, grades=GRADES,
                                   scores=next_exam["scores"])
        self.assertEqual(set(needed), {"a" * 64, "d" * 64})
        changed, _, decisions = advance_epoch(
            early, grades=GRADES, challenger_exam=next_exam,
            incumbent_exams={"a" * 64: _exam("a", 207),
                             "d" * 64: _exam("d", 210)})
        self.assertEqual(next(d["decision"] for d in decisions
                              if d["grade"] == "B"),
                         "DENY_NO_STRICT_SCHOOL_VICTORY")
        self.assertEqual(changed["active_roles"]["B.XOR"]["checkpoint"]["sha256"],
                         "d" * 64)

    def test_same_grade_breadth_tie_does_not_replace_role(self):
        first = _exam("c", 209)
        before, _, _ = advance_epoch(
            _epoch(), grades={"C": GRADES["C"]},
            challenger_exam=first, incumbent_exams={})
        other = _exam("d", 209)
        needed = needed_incumbents(before, grades={"C": GRADES["C"]},
                                   scores=other["scores"])
        self.assertEqual(needed, {})
        after, changes, _ = advance_epoch(
            before, grades={"C": GRADES["C"]},
            challenger_exam=other, incumbent_exams={})
        self.assertEqual(changes, ())
        self.assertEqual(after["active_roles"], before["active_roles"])

    def test_reset_archives_earned_roles_and_soups_without_new_teacher(self):
        first = _exam("c", 209)
        original, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=first,
            incumbent_exams={})
        original["active_grade_soups"] = {
            "C": grade_soup_recipe(active_frontier(original), "C", GRADES["C"])}
        original["baseline_roles"] = {"A.0": "b" * 64}
        old = deepcopy(original)
        student = _exam("d", 210)["checkpoint"]
        result, changed = reset_active_championships(
            original, student=student, generation=400)
        self.assertTrue(changed)
        self.assertEqual(original, old)
        self.assertEqual(result["active_roles"], {})
        self.assertEqual(result["active_grade_soups"], {})
        self.assertEqual(result["baseline_roles"], {})
        self.assertEqual(result["qualified"], [])
        self.assertEqual(result["guidance_policy"], EARNED_ONLY_POLICY)
        self.assertEqual(result["championship_eligibility_after_step"], 10)
        historic = result["superseded_active_championships"][-1]
        self.assertEqual(historic["active_roles"], original["active_roles"])
        self.assertEqual(historic["active_grade_soups"], original["active_grade_soups"])
        self.assertEqual(historic["starting_student"], student)
        replay, changed = reset_active_championships(
            result, student=student, generation=401)
        self.assertFalse(changed)
        self.assertEqual(replay, result)

    def test_reset_baseline_cannot_immediately_reclaim_championships(self):
        original = _epoch()
        current = _exam("c", 209)["checkpoint"]
        cleared, _ = reset_active_championships(
            original, student=current, generation=400)
        same_step, roles, decisions = advance_epoch(
            cleared, grades=GRADES, challenger_exam=_exam("c", 209),
            incumbent_exams={})
        self.assertEqual(roles, ())
        self.assertEqual(decisions, ())
        self.assertEqual(same_step["active_roles"], {})
        later = _exam("d", 209)
        later["checkpoint"]["optimizer_step"] = 11
        grown, roles, decisions = advance_epoch(
            cleared, grades=GRADES, challenger_exam=later,
            incumbent_exams={})
        self.assertTrue(roles)
        self.assertEqual({d["decision"] for d in decisions},
                         {"ELIGIBLE_UNCONTESTED_GRADE"})
        self.assertEqual(len(grown["active_roles"]["B.XOR"]["perfect_capabilities"]),
                         17)
