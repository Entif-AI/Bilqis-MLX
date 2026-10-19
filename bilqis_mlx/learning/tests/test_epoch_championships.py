"""Epoch champions preserve best-score roles and tighten only after mastery."""
from copy import deepcopy
from types import MappingProxyType
from unittest import TestCase

from bilqis_mlx.learning.epoch_championships import (
    active_frontier, advance_epoch as _advance_epoch, needed_incumbents,
    rebase_active_championships, reset_active_championships)
from bilqis_mlx.learning.mentor_epoch import EARNED_ONLY_POLICY
from bilqis_mlx.learning.grade_soup import grade_soup_recipe
from bilqis_mlx.learning.tests.test_championship_policy import GRADE_B, SCHOOL, _exam

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


def _with_question_evidence(exam):
    result = deepcopy(exam)
    result["correct_questions"] = {
        cap: [{"id": result["cohort_sha256"] + cap + str(i), "gold": "TRUE"}
              for i in range(score["correct"])]
        for cap, score in result["scores"].items()}
    result["questions"] = {
        cap: [{"id": result["cohort_sha256"] + cap + str(i), "gold": "TRUE"}
              for i in range(score["total"])]
        for cap, score in result["scores"].items()}
    return result


def advance_epoch(epoch, *, grades, challenger_exam, incumbent_exams):
    """Policy fixtures assume the candidate preserves earlier correct questions."""
    candidate = _with_question_evidence(challenger_exam)
    candidate["witness_scores"] = {
        witness["sha256"]: [q["id"] for q in witness["questions"]]
        for role in epoch.get("active_roles", {}).values()
        for witness in role.get("qualification_witnesses", ())}
    return _advance_epoch(epoch, grades=grades, challenger_exam=candidate,
                          incumbent_exams=incumbent_exams)


class EpochChampionshipTests(TestCase):
    def test_grade_complete_replay_can_improve_a_role_without_inventing_school_evidence(self):
        original = _exam("a", 208)
        original["scores"]["B.XOR"]["correct"] = 10
        epoch, _, _ = advance_epoch(_epoch(), grades=GRADES,
                                    challenger_exam=original, incumbent_exams={})
        candidate = _exam("b", 209)
        candidate["scores"]["B.XOR"]["correct"] = 11
        candidate["cohort_sha256"] = "6" * 64
        partial = {**original, "cohort_sha256": "6" * 64,
                   "scores": {cap: original["scores"][cap] for cap in GRADE_B}}
        _, changed, _ = advance_epoch(epoch, grades=GRADES,
                                      challenger_exam=candidate, incumbent_exams={"a" * 64: partial})
        self.assertIn("B.XOR", changed)

    def test_grade_only_replay_cannot_certify_a_whole_school_takeover(self):
        original = _exam("a", 208)
        epoch, _, _ = advance_epoch(_epoch(), grades=GRADES,
                                    challenger_exam=original, incumbent_exams={})
        candidate = _exam("b", 209)
        candidate["cohort_sha256"] = "6" * 64
        partial = {**original, "cohort_sha256": "6" * 64,
                   "scores": {cap: original["scores"][cap] for cap in GRADE_B}}
        _, changed, decisions = advance_epoch(epoch, grades=GRADES,
                                              challenger_exam=candidate,
                                              incumbent_exams={"a" * 64: partial})
        self.assertFalse(set(GRADE_B) & set(changed))
        self.assertTrue(any(d["decision"] == "DEFER_INCUMBENT_SCHOOL_INCOMPARABLE" for d in decisions))

    def test_grade_wide_tie_takeover_requires_every_displaced_branch_atomically(self):
        left_exam, right_exam = _exam("a", 207), _exam("b", 208)
        right_exam["cohort_sha256"] = "6" * 64
        left, _, _ = advance_epoch(_epoch(), grades=GRADES,
                                   challenger_exam=left_exam, incumbent_exams={})
        right, _, _ = advance_epoch(_epoch(), grades=GRADES,
                                    challenger_exam=right_exam, incumbent_exams={})
        left["active_roles"]["B.XOR"] = right["active_roles"]["B.XOR"]
        candidate = _with_question_evidence(_exam("c", 209))
        candidate["cohort_sha256"] = "7" * 64
        candidate = _with_question_evidence(candidate)
        candidate["witness_scores"] = {
            w["sha256"]: [q["id"] for q in w["questions"]]
            for role in left["active_roles"].values() for w in role["qualification_witnesses"]}
        proof = right["active_roles"]["B.XOR"]["qualification_witnesses"][0]
        candidate["witness_scores"][proof["sha256"]].pop()
        _, changed, _ = _advance_epoch(
            left, grades=GRADES, challenger_exam=candidate,
            incumbent_exams={"a" * 64: {**left_exam, "cohort_sha256": "7" * 64},
                             "b" * 64: {**right_exam, "cohort_sha256": "7" * 64}})
        self.assertFalse(set(GRADE_B) & set(changed))

    def test_grade_takeover_absorbs_every_branch_and_preserves_it_for_successors(self):
        first = _exam("a", 208)
        left, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=first, incumbent_exams={})
        second = _exam("b", 209)
        second["cohort_sha256"] = "6" * 64
        right, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=second, incumbent_exams={})
        left["active_roles"]["B.XOR"] = right["active_roles"]["B.XOR"]
        inherited = {w["sha256"] for role in left["active_roles"].values()
                     for w in role["qualification_witnesses"]}
        contender = _exam("c", 210)
        contender["cohort_sha256"] = "7" * 64
        paired = {seed * 64: {**source, "cohort_sha256": "7" * 64}
                  for seed, source in (("a", first), ("b", second))}
        taken, changed, _ = advance_epoch(
            left, grades=GRADES, challenger_exam=contender, incumbent_exams=paired)
        self.assertTrue(set(GRADE_B) <= set(changed))
        for cap in GRADE_B:
            role = taken["active_roles"][cap]
            self.assertTrue(inherited <= {w["sha256"] for w in role["qualification_witnesses"]})
            self.assertEqual(set(role["ancestor_checkpoint_sha256s"]), {"a" * 64, "b" * 64})

        successor = _with_question_evidence(_exam("d", 211))
        successor["witness_scores"] = {
            w["sha256"]: [q["id"] for q in w["questions"]]
            for role in taken["active_roles"].values() for w in role["qualification_witnesses"]}
        ancestor_proof = next(w for w in right["active_roles"]["B.XOR"]["qualification_witnesses"]
                              if w["questions"])
        successor["witness_scores"][ancestor_proof["sha256"]].pop()
        current = {**contender, "cohort_sha256": successor["cohort_sha256"]}
        kept, changed, _ = _advance_epoch(
            taken, grades=GRADES, challenger_exam=successor,
            incumbent_exams={"c" * 64: current})
        self.assertFalse(set(GRADE_B) & set(changed))
        self.assertEqual(kept["active_roles"]["B.XOR"], taken["active_roles"]["B.XOR"])

    def test_current_paired_score_can_be_beaten_after_a_historical_max(self):
        first = _exam("a", 208)
        epoch, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=first, incumbent_exams={})
        replay = deepcopy(first)
        replay["cohort_sha256"] = "6" * 64
        replay["scores"]["B.XOR"]["correct"] = 8
        contender = deepcopy(replay)
        contender["checkpoint"] = _exam("c", 209)["checkpoint"]
        contender["scores"]["B.XOR"]["correct"] = 11
        after, changed, _ = advance_epoch(
            epoch, grades=GRADES, challenger_exam=contender,
            incumbent_exams={"a" * 64: replay})
        self.assertIn("B.XOR", changed)
        self.assertEqual(after["active_roles"]["B.XOR"]["correct"], 11)
        from bilqis_mlx.learning.championship_witnesses import maxed_role
        self.assertTrue(maxed_role(after["active_roles"]["B.XOR"]))

    def test_fresh_winner_must_preserve_every_original_earning_question(self):
        epoch, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=_exam("a", 208), incumbent_exams={})
        replay = _exam("a", 208)
        replay["cohort_sha256"] = "6" * 64
        replay["scores"]["B.XOR"]["correct"] = 8
        contender = _with_question_evidence(replay)
        contender["checkpoint"] = _exam("c", 209)["checkpoint"]
        contender["scores"]["B.XOR"]["correct"] = 11
        contender = _with_question_evidence(contender)
        original = deepcopy(epoch["active_roles"]["B.XOR"])
        after, changed, decisions = _advance_epoch(
            epoch, grades=GRADES, challenger_exam=contender,
            incumbent_exams={"a" * 64: replay})
        self.assertNotIn("B.XOR", changed)
        self.assertEqual(after["active_roles"]["B.XOR"], original)
        self.assertTrue(any(d["decision"] == "DENY_EARNING_QUESTION_REGRESSION"
                            for d in decisions))

    def test_perfect_breadth_counts_only_the_champions_grade(self):
        first = _exam("a", 208)
        first["scores"]["C.0"]["correct"] = first["scores"]["C.1"]["correct"] = 12
        epoch, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=first, incumbent_exams={})
        contender = _exam("c", 215)
        contender["scores"]["C.1"]["correct"] = 11
        after, changed, _ = advance_epoch(
            epoch, grades=GRADES, challenger_exam=contender,
            incumbent_exams={"a" * 64: first})
        self.assertNotIn("C.0", changed)

    def test_fully_perfect_origin_grade_uses_strict_school_takeover(self):
        first = _exam("a", 208)
        epoch, _, _ = advance_epoch(
            {**_epoch(), "introduced_grade": "B"}, grades=GRADES,
            challenger_exam=first, incumbent_exams={})
        contender = _exam("c", 209)
        self.assertIn("a" * 64, needed_incumbents(
            epoch, grades=GRADES, challenger_exam=contender))
        after, changed, _ = advance_epoch(
            epoch, grades=GRADES, challenger_exam=contender,
            incumbent_exams={"a" * 64: first})
        self.assertTrue(set(GRADE_B) <= set(changed))

    def test_experiment_rebase_clears_active_titles_without_making_baseline_a_champ(self):
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
        self.assertFalse(rebased["baseline_challenge_required"])
        self.assertIsNone(rebased["baseline_surpassed"])
        self.assertEqual(rebased["championship_eligibility_after_step"],
                         baseline["optimizer_step"])

    def test_rebased_baseline_does_not_block_later_best_score_roles(self):
        epoch = _epoch()
        rebased = rebase_active_championships(
            epoch, prior_student=_exam("d", 210)["checkpoint"],
            baseline=_exam("b", 208)["checkpoint"], generation=500)
        contender = _exam("c", 207)
        contender["checkpoint"]["optimizer_step"] = 11
        contender["scores"]["B.XOR"] = {"correct": 10, "total": 12}
        upgraded, roles, _ = advance_epoch(
            rebased, grades=GRADES, challenger_exam=contender,
            incumbent_exams={})
        self.assertIn("B.XOR", roles)
        self.assertEqual(upgraded["active_roles"]["B.XOR"]["correct"], 10)
        self.assertEqual(upgraded["active_roles"]["B.XOR"]["checkpoint"]["sha256"],
                         "c" * 64)
        self.assertIsNone(upgraded["baseline_surpassed"])

    def test_non_teaching_baseline_is_not_a_fictitious_incumbent(self):
        epoch = _epoch()
        candidate = _exam("c", 209)
        candidate["checkpoint"]["optimizer_step"] = 11
        needed = needed_incumbents(
            epoch, grades=GRADES, challenger_exam=candidate)
        self.assertEqual(needed, {})

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

    def test_cross_origin_requires_complete_grade_but_not_perfection_for_empty_roles(self):
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
        self.assertTrue(set(GRADES["B"]) <= set(titles))
        self.assertEqual(unchanged["active_roles"]["B.XOR"]["correct"], 11)

    def test_nonmax_capability_champ_is_replaced_by_strictly_better_score(self):
        first = _exam("c", 207)
        first["scores"]["B.XOR"] = {"correct": 10, "total": 12}
        epoch, roles, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=first,
            incumbent_exams={})
        self.assertIn("B.XOR", roles)
        self.assertEqual(epoch["active_roles"]["B.XOR"]["correct"], 10)

        challenger = deepcopy(first)
        challenger["checkpoint"] = _exam("d", 208)["checkpoint"]
        challenger["scores"]["B.XOR"] = {"correct": 11, "total": 12}
        needed = needed_incumbents(
            epoch, grades=GRADES, challenger_exam=challenger)
        self.assertIn("c" * 64, needed)
        changed, roles, _ = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams={"c" * 64: first})
        self.assertIn("B.XOR", roles)
        self.assertEqual(changed["active_roles"]["B.XOR"]["correct"], 11)
        self.assertEqual(changed["active_roles"]["B.XOR"]["checkpoint"]["sha256"],
                         "d" * 64)

    def test_new_grade_earns_roles_while_prior_soups_stay_archived(self):
        epoch = _epoch()
        candidate = _exam("c", 209)
        before = deepcopy(epoch)
        needed = needed_incumbents(
            epoch, grades=GRADES, challenger_exam=candidate)
        self.assertEqual(needed, {})
        upgraded, changes, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=candidate,
            incumbent_exams={})
        self.assertEqual(epoch, before)
        self.assertTrue(set(GRADES["B"]) <= set(changes))
        self.assertTrue(set(GRADES["A"]) <= set(changes))
        self.assertTrue(set(GRADES["C"]) & set(changes))
        self.assertEqual(decisions, ())
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
        self.assertFalse(any(d.get("grade") == "B" for d in decisions))

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
        needed = needed_incumbents(
            early, grades=GRADES, challenger_exam=next_exam)
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
        needed = needed_incumbents(
            before, grades={"C": GRADES["C"]}, challenger_exam=other)
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
        self.assertEqual(decisions, ())
        self.assertEqual(len(grown["active_roles"]["B.XOR"]["perfect_capabilities"]),
                         17)
