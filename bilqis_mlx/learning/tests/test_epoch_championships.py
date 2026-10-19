"""Capability-local defended championships and one-hop same-grade fan-out."""
from copy import deepcopy
from types import MappingProxyType
from unittest import TestCase

from bilqis_mlx.learning.epoch_championships import (
    active_frontier, advance_epoch, needed_incumbents,
    rebase_active_championships, reset_active_championships,
)
from bilqis_mlx.learning.grade_soup import grade_soup_recipe
from bilqis_mlx.learning.mentor_epoch import EARNED_ONLY_POLICY
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


def _panel(seed, step, capability, correct, *, cohort="1", grade=None):
    exam = _exam(seed, 208)
    exam["checkpoint"]["optimizer_step"] = step
    exam["cohort_sha256"] = cohort * 64
    exam["scores"] = {capability: {"correct": correct, "total": 12}}
    exam["challenge_grade"] = grade or capability.split(".", 1)[0]
    exam["checkpoint_origin_grade"] = exam["challenge_grade"]
    return _with_question_evidence(exam)


def _multi_panel(seed, step, scores, *, cohort="1", grade="B"):
    exam = _exam(seed, 208)
    exam["checkpoint"]["optimizer_step"] = step
    exam["cohort_sha256"] = cohort * 64
    exam["scores"] = {cap: {"correct": correct, "total": 12}
                      for cap, correct in scores.items()}
    exam["challenge_grade"] = grade
    exam["checkpoint_origin_grade"] = grade
    return _with_question_evidence(exam)


def _battery_answers(role, *, drop=0):
    result = {}
    for segment in role["surviving_battery"]:
        ids = [q["id"] for q in segment["questions"]]
        result[segment["sha256"]] = ids[:max(0, len(ids) - drop)]
    return result


def _match(role, incumbent_current, challenger_current, *,
           incumbent_battery, challenger_battery):
    return {
        "incumbent_checkpoint_sha256": role["checkpoint"]["sha256"],
        "challenger_checkpoint_sha256": challenger_current["checkpoint"]["sha256"],
        "incumbent_current_exam": incumbent_current,
        "challenger_current_exam": challenger_current,
        "battery_results": {
            role["checkpoint"]["sha256"]: incumbent_battery,
            challenger_current["checkpoint"]["sha256"]: challenger_battery,
        },
    }


class EpochChampionshipTests(TestCase):
    def test_explicit_reset_floor_blocks_same_step_authority_but_allows_newer_checkpoint(self):
        epoch = _epoch()
        epoch["championship_eligibility_after_step"] = 12
        stale = _panel("a", 12, "A.0", 12, grade="A")
        unchanged, changes, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=stale, incumbent_exams={})
        self.assertEqual(changes, ())
        self.assertEqual(decisions, ())
        self.assertEqual(unchanged.get("active_roles", {}), {})

        fresh = _panel("c", 13, "A.0", 12, grade="A")
        admitted, changes, decisions = advance_epoch(
            unchanged, grades=GRADES, challenger_exam=fresh, incumbent_exams={})
        self.assertEqual(changes, ("A.0",))
        self.assertEqual(decisions, ())
        self.assertEqual(admitted["active_roles"]["A.0"]["checkpoint"]["sha256"],
                         "c" * 64)

    def test_role_persists_same_grade_checkpoint_origin(self):
        result, _, _ = advance_epoch(
            _epoch(), grades=GRADES,
            challenger_exam=_panel("a", 11, "A.0", 10, grade="A"),
            incumbent_exams={})
        self.assertEqual(result["active_roles"]["A.0"]["origin_grade"], "A")

    def test_cross_grade_legacy_owner_is_archived_before_same_grade_mint(self):
        first = _panel("a", 11, "A.0", 10, grade="A")
        epoch, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=first, incumbent_exams={})
        epoch["active_roles"]["A.0"]["origin_grade"] = "B"
        challenger = _panel("c", 12, "A.0", 12, cohort="6", grade="A")
        result, changes, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger, incumbent_exams={})
        self.assertEqual(changes, ("A.0",))
        self.assertEqual(decisions, ())
        self.assertEqual(result["active_roles"]["A.0"]["checkpoint"]["sha256"],
                         "c" * 64)
        self.assertEqual(result["active_roles"]["A.0"]["origin_grade"], "A")
        archived = result["invalidated_active_roles"][-1]
        self.assertEqual((archived["capability"], archived["origin_grade"],
                          archived["reason"]),
                         ("A.0", "B", "CROSS_GRADE_TITLE_OWNER"))

    def test_missing_legacy_origin_is_archived_fail_closed_before_same_grade_mint(self):
        first = _panel("a", 11, "A.0", 10, grade="A")
        epoch, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=first, incumbent_exams={})
        del epoch["active_roles"]["A.0"]["origin_grade"]
        challenger = _panel("c", 12, "A.0", 12, cohort="6", grade="A")
        result, changes, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger, incumbent_exams={})
        self.assertEqual(changes, ("A.0",))
        self.assertEqual(decisions, ())
        self.assertEqual(result["invalidated_active_roles"][-1]["reason"],
                         "TITLE_ORIGIN_PROVENANCE_MISSING")

    def test_empty_role_requires_at_least_sixty_six_percent(self):
        below = _panel("a", 11, "B.XOR", 7, grade="B")
        result, changes, decisions = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=below, incumbent_exams={})
        self.assertEqual(changes, ())
        self.assertNotIn("B.XOR", result.get("active_roles", {}))
        self.assertEqual(decisions[0]["decision"], "INITIAL_TITLE_THRESHOLD_NOT_MET")

        candidate = _panel("c", 12, "B.XOR", 8, grade="B")
        result, changes, decisions = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=candidate, incumbent_exams={})
        self.assertEqual(changes, ("B.XOR",))
        self.assertEqual(decisions, ())
        self.assertEqual(set(result["active_roles"]), {"B.XOR"})
        self.assertEqual(result["active_roles"]["B.XOR"]["correct"], 8)

    def test_initial_title_battery_is_exactly_first_threshold_passes(self):
        candidate = _panel("a", 11, "B.XOR", 8, grade="B")
        result, changes, decisions = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=candidate, incumbent_exams={})
        self.assertEqual(changes, ("B.XOR",))
        self.assertEqual(decisions, ())
        role = result["active_roles"]["B.XOR"]
        battery = [question for segment in role["surviving_battery"]
                   for question in segment["questions"]]
        expected = [
            {**question, "capability": "B.XOR"}
            for question in candidate["correct_questions"]["B.XOR"]
        ]
        self.assertEqual(
            {question["id"] for question in battery},
            {question["id"] for question in expected})
        self.assertEqual(len(battery), 8)
        self.assertEqual({question["capability"] for question in battery}, {"B.XOR"})

    def test_empty_roles_get_per_capability_batteries(self):
        candidate = _multi_panel("a", 11, {"B.AND": 12, "B.XOR": 12})
        result, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=candidate, incumbent_exams={})
        for cap in ("B.AND", "B.XOR"):
            battery = result["active_roles"][cap]["surviving_battery"]
            self.assertEqual(
                {q["capability"] for segment in battery for q in segment["questions"]},
                {cap})

    def test_single_capability_max_opens_title_fight_even_when_incumbent_also_maxed(self):
        first = _panel("a", 11, "B.XOR", 12, cohort="1")
        epoch, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=first, incumbent_exams={})
        challenger = _panel("c", 12, "B.XOR", 12, cohort="6")
        incumbent = _panel("a", 11, "B.XOR", 12, cohort="6")
        _, changes, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams={"a" * 64: incumbent})
        self.assertEqual(changes, ())
        self.assertTrue(any(d["decision"] == "TITLE_MATCH_REQUIRED" and
                            d["qualification"] == "CAPABILITY_MAX"
                            for d in decisions))

    def test_strict_gain_below_max_opens_title_fight_but_below_max_tie_does_not(self):
        first = _panel("a", 11, "B.XOR", 8)
        epoch, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=first, incumbent_exams={})
        challenger = _panel("c", 12, "B.XOR", 9, cohort="6")
        incumbent = _panel("a", 11, "B.XOR", 8, cohort="6")
        _, _, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams={"a" * 64: incumbent})
        self.assertTrue(any(d["qualification"] == "STRICT_GAIN" for d in decisions))

        tied = _panel("d", 13, "B.XOR", 8, cohort="7")
        incumbent_tie = _panel("a", 11, "B.XOR", 8, cohort="7")
        _, _, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=tied,
            incumbent_exams={"a" * 64: incumbent_tie})
        self.assertFalse(any(d.get("decision") == "TITLE_MATCH_REQUIRED"
                             for d in decisions))

    def test_battery_can_crown_contender_even_after_fresh_current_score_drops(self):
        first = _panel("a", 11, "B.XOR", 12)
        epoch, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=first, incumbent_exams={})
        role = epoch["active_roles"]["B.XOR"]
        challenger = _panel("c", 12, "B.XOR", 11, cohort="6")
        incumbent = _panel("a", 11, "B.XOR", 8, cohort="6")
        incumbent_fresh = _panel("a", 11, "B.XOR", 7, cohort="6")
        challenger_fresh = _panel("c", 12, "B.XOR", 6, cohort="6")
        match = _match(
            role, incumbent_fresh, challenger_fresh,
            incumbent_battery=_battery_answers(role, drop=2),
            challenger_battery=_battery_answers(role, drop=0))
        result, changes, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams={"a" * 64: incumbent},
            title_matches={"B.XOR": match})
        self.assertIn("B.XOR", changes)
        champion = result["active_roles"]["B.XOR"]
        self.assertEqual(champion["checkpoint"]["sha256"], "c" * 64)
        self.assertEqual(champion["correct"], 6)
        self.assertFalse(champion["maxed"])
        self.assertTrue(any(d["decision"] == "TITLE_WON" for d in decisions))

    def test_battery_tie_defends_title_and_refreshes_current_score_downward(self):
        first = _panel("a", 11, "B.XOR", 12)
        epoch, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=first, incumbent_exams={})
        role = epoch["active_roles"]["B.XOR"]
        challenger = _panel("c", 12, "B.XOR", 11, cohort="6")
        incumbent = _panel("a", 11, "B.XOR", 8, cohort="6")
        incumbent_fresh = _panel("a", 11, "B.XOR", 7, cohort="6")
        challenger_fresh = _panel("c", 12, "B.XOR", 6, cohort="6")
        tied = _battery_answers(role, drop=2)
        result, changes, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams={"a" * 64: incumbent},
            title_matches={"B.XOR": _match(
                role, incumbent_fresh, challenger_fresh,
                incumbent_battery=tied, challenger_battery=tied)})
        self.assertNotIn("B.XOR", changes)
        champion = result["active_roles"]["B.XOR"]
        self.assertEqual(champion["checkpoint"]["sha256"], "a" * 64)
        self.assertEqual(champion["correct"], 7)
        self.assertTrue(any(d["decision"] == "TITLE_DEFENDED" for d in decisions))

    def test_settled_pair_never_rematches_or_mutates_role_again(self):
        first = _panel("a", 11, "B.XOR", 12)
        epoch, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=first, incumbent_exams={})
        role = epoch["active_roles"]["B.XOR"]
        challenger = _panel("c", 12, "B.XOR", 12, cohort="6")
        incumbent = _panel("a", 11, "B.XOR", 12, cohort="6")
        tied = _battery_answers(role, drop=1)
        defended, _, _ = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams={"a" * 64: incumbent},
            title_matches={"B.XOR": _match(
                role, _panel("a", 11, "B.XOR", 11, cohort="6"),
                _panel("c", 12, "B.XOR", 11, cohort="6"),
                incumbent_battery=tied, challenger_battery=tied)})
        frozen_role = deepcopy(defended["active_roles"]["B.XOR"])
        self.assertEqual(len(defended["settled_matchups"]), 1)

        rematch = _panel("c", 12, "B.XOR", 12, cohort="7")
        rematch_incumbent = _panel("a", 11, "B.XOR", 8, cohort="7")
        result, changes, decisions = advance_epoch(
            defended, grades=GRADES, challenger_exam=rematch,
            incumbent_exams={"a" * 64: rematch_incumbent})
        self.assertEqual(changes, ())
        self.assertEqual(
            needed_incumbents(defended, grades=GRADES, challenger_exam=rematch), {})
        self.assertTrue(any(d.get("decision") == "TITLE_MATCH_ALREADY_SETTLED"
                            for d in decisions))
        self.assertFalse(any(d.get("decision") in (
            "TITLE_MATCH_REQUIRED", "TITLE_WON", "TITLE_DEFENDED")
                             for d in decisions))
        self.assertEqual(result["active_roles"]["B.XOR"], frozen_role)

    def test_settled_pair_key_is_direction_independent_after_title_transfer(self):
        first = _panel("a", 11, "B.XOR", 12)
        epoch, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=first, incumbent_exams={})
        role = epoch["active_roles"]["B.XOR"]
        challenger = _panel("c", 12, "B.XOR", 12, cohort="6")
        won, _, _ = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams={"a" * 64: _panel("a", 11, "B.XOR", 12, cohort="6")},
            title_matches={"B.XOR": _match(
                role, _panel("a", 11, "B.XOR", 10, cohort="6"),
                _panel("c", 12, "B.XOR", 11, cohort="6"),
                incumbent_battery=_battery_answers(role, drop=2),
                challenger_battery=_battery_answers(role, drop=0))})
        reverse = _panel("a", 14, "B.XOR", 12, cohort="7")
        result, changes, decisions = advance_epoch(
            won, grades=GRADES, challenger_exam=reverse, incumbent_exams={})
        self.assertEqual(changes, ())
        self.assertEqual(result["active_roles"]["B.XOR"]["checkpoint"]["sha256"],
                         "c" * 64)
        self.assertTrue(any(d.get("decision") == "TITLE_MATCH_ALREADY_SETTLED"
                            for d in decisions))

    def test_defended_battery_drops_questions_the_winner_now_misses(self):
        first = _panel("a", 11, "B.XOR", 12)
        epoch, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=first, incumbent_exams={})
        role = epoch["active_roles"]["B.XOR"]
        challenger = _panel("c", 12, "B.XOR", 11, cohort="6")
        incumbent = _panel("a", 11, "B.XOR", 8, cohort="6")
        incumbent_fresh = _panel("a", 11, "B.XOR", 7, cohort="6")
        challenger_fresh = _panel("c", 12, "B.XOR", 6, cohort="6")
        result, _, _ = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams={"a" * 64: incumbent},
            title_matches={"B.XOR": _match(
                role, incumbent_fresh, challenger_fresh,
                incumbent_battery=_battery_answers(role, drop=4),
                challenger_battery=_battery_answers(role, drop=4))})
        refreshed = result["active_roles"]["B.XOR"]["surviving_battery"]
        active_ids = {q["id"] for segment in refreshed for q in segment["questions"]}
        old_ids = {q["id"] for segment in role["surviving_battery"]
                   for q in segment["questions"]}
        self.assertTrue(active_ids < old_ids | {
            q["id"] for q in incumbent["correct_questions"]["B.XOR"]})
        self.assertLess(len(active_ids & old_ids), len(old_ids))

    def test_cross_grade_incumbents_are_not_requested_or_competed(self):
        a = _panel("a", 11, "A.0", 10, grade="A")
        epoch, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=a, incumbent_exams={})
        b = _panel("b", 12, "B.XOR", 10, grade="B")
        epoch, _, _ = advance_epoch(
            epoch, grades=GRADES, challenger_exam=b, incumbent_exams={})
        challenger = _multi_panel("c", 13, {"A.0": 12, "B.XOR": 11},
                                  cohort="6", grade="B")
        needed = needed_incumbents(epoch, grades=GRADES, challenger_exam=challenger)
        self.assertEqual(set(needed), {"b" * 64})
        incumbent = _panel("b", 12, "B.XOR", 10, cohort="6", grade="B")
        result, _, _ = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams={"b" * 64: incumbent})
        self.assertEqual(result["active_roles"]["A.0"], epoch["active_roles"]["A.0"])

    def _fanout_fixture(self):
        first = _panel("a", 11, "B.AND", 8)
        epoch, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=first, incumbent_exams={})
        second = _panel("b", 12, "B.XOR", 8, cohort="2")
        epoch, _, _ = advance_epoch(
            epoch, grades=GRADES, challenger_exam=second, incumbent_exams={})
        challenger = _multi_panel(
            "c", 13, {"B.AND": 10, "B.XOR": 8}, cohort="6", grade="B")
        incumbents = {
            "a" * 64: _panel("a", 11, "B.AND", 8, cohort="6"),
            "b" * 64: _panel("b", 12, "B.XOR", 8, cohort="6"),
        }
        return epoch, challenger, incumbents

    def test_primary_takeover_queues_one_same_grade_fanout_for_match_or_beat(self):
        epoch, challenger, incumbents = self._fanout_fixture()
        and_role = epoch["active_roles"]["B.AND"]
        primary = _match(
            and_role,
            _panel("a", 11, "B.AND", 7, cohort="6"),
            _panel("c", 13, "B.AND", 9, cohort="6"),
            incumbent_battery=_battery_answers(and_role, drop=2),
            challenger_battery=_battery_answers(and_role, drop=0))
        _, changes, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams=incumbents, title_matches={"B.AND": primary})
        self.assertIn("B.AND", changes)
        self.assertTrue(any(d["decision"] == "FANOUT_SCREEN_REQUIRED"
                            for d in decisions))
        screen = {"B.XOR": {
            "incumbent_checkpoint_sha256": "b" * 64,
            "challenger_checkpoint_sha256": "c" * 64,
            "incumbent_exam": _panel("b", 12, "B.XOR", 8, cohort="6"),
            "challenger_exam": _panel("c", 13, "B.XOR", 8, cohort="6"),
        }}
        _, _, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams=incumbents, title_matches={"B.AND": primary},
            fanout_screen=screen)
        self.assertTrue(any(d["decision"] == "FANOUT_TITLE_MATCH_REQUIRED" and
                            d["capability"] == "B.XOR" for d in decisions))

    def test_defended_primary_title_does_not_open_fanout(self):
        epoch, challenger, incumbents = self._fanout_fixture()
        and_role = epoch["active_roles"]["B.AND"]
        tied = _battery_answers(and_role, drop=1)
        primary = _match(
            and_role,
            _panel("a", 11, "B.AND", 7, cohort="6"),
            _panel("c", 13, "B.AND", 9, cohort="6"),
            incumbent_battery=tied, challenger_battery=tied)
        _, changes, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams=incumbents, title_matches={"B.AND": primary})
        self.assertNotIn("B.AND", changes)
        self.assertFalse(any(d["decision"] in (
            "FANOUT_SCREEN_REQUIRED", "FANOUT_TITLE_MATCH_REQUIRED")
                             for d in decisions))

    def test_primary_win_does_not_fanout_into_already_settled_sibling_pair(self):
        epoch, challenger, incumbents = self._fanout_fixture()
        xor_role = epoch["active_roles"]["B.XOR"]
        epoch["settled_matchups"] = {
            "B.XOR|" + "b" * 64 + "|" + "c" * 64: {
                "decision": "TITLE_DEFENDED", "winner_sha256": "b" * 64}}
        and_role = epoch["active_roles"]["B.AND"]
        primary = _match(
            and_role,
            _panel("a", 11, "B.AND", 7, cohort="6"),
            _panel("c", 13, "B.AND", 9, cohort="6"),
            incumbent_battery=_battery_answers(and_role, drop=2),
            challenger_battery=_battery_answers(and_role, drop=0))
        _, changes, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams=incumbents, title_matches={"B.AND": primary})
        self.assertIn("B.AND", changes)
        self.assertFalse(any(d["decision"] in (
            "FANOUT_SCREEN_REQUIRED", "FANOUT_TITLE_MATCH_REQUIRED")
                             for d in decisions))

    def test_secondary_fanout_win_does_not_recurse(self):
        epoch, challenger, incumbents = self._fanout_fixture()
        and_role = epoch["active_roles"]["B.AND"]
        xor_role = epoch["active_roles"]["B.XOR"]
        matches = {
            "B.AND": _match(
                and_role,
                _panel("a", 11, "B.AND", 7, cohort="6"),
                _panel("c", 13, "B.AND", 9, cohort="6"),
                incumbent_battery=_battery_answers(and_role, drop=2),
                challenger_battery=_battery_answers(and_role, drop=0)),
            "B.XOR": _match(
                xor_role,
                _panel("b", 12, "B.XOR", 7, cohort="6"),
                _panel("c", 13, "B.XOR", 7, cohort="6"),
                incumbent_battery=_battery_answers(xor_role, drop=2),
                challenger_battery=_battery_answers(xor_role, drop=0)),
        }
        result, changes, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams=incumbents, title_matches=matches,
            fanout_screen={"B.XOR": {
                "incumbent_checkpoint_sha256": "b" * 64,
                "challenger_checkpoint_sha256": "c" * 64,
                "incumbent_exam": _panel("b", 12, "B.XOR", 8, cohort="6"),
                "challenger_exam": _panel("c", 13, "B.XOR", 8, cohort="6"),
            }})
        self.assertTrue({"B.AND", "B.XOR"} <= set(changes))
        self.assertFalse(any(d["decision"] in (
            "TITLE_MATCH_REQUIRED", "FANOUT_SCREEN_REQUIRED",
            "FANOUT_TITLE_MATCH_REQUIRED") for d in decisions))
        xor_battery = result["active_roles"]["B.XOR"]["surviving_battery"]
        current_ids = {q["id"] for segment in xor_battery
                       for q in segment["questions"]
                       if q["id"].startswith("6" * 64 + "B.XOR")}
        self.assertEqual(len(current_ids), 8,
                         "the fresh fan-out gate's eighth correct answer must survive")

    def test_experiment_rebase_clears_titles_without_making_baseline_a_champ(self):
        first = _panel("c", 11, "C.0", 9, grade="C")
        earned, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=first, incumbent_exams={})
        earned["active_grade_soups"] = {
            "C": grade_soup_recipe(active_frontier(earned), "C", GRADES["C"])}
        old_student = _exam("d", 210)["checkpoint"]
        old_student["optimizer_step"] = 12
        baseline = _exam("e", 208)["checkpoint"]
        baseline["optimizer_step"] = 11
        rebased = rebase_active_championships(
            earned, prior_student=old_student, baseline=baseline, generation=500)
        self.assertEqual(rebased["active_roles"], {})
        self.assertEqual(rebased["active_grade_soups"], {})
        self.assertEqual(rebased["baseline"], baseline)
        self.assertFalse(rebased["baseline_challenge_required"])

    def test_reset_archives_earned_roles_and_soups_without_new_teacher(self):
        first = _panel("c", 11, "C.0", 9, grade="C")
        original, _, _ = advance_epoch(
            _epoch(), grades=GRADES, challenger_exam=first, incumbent_exams={})
        original["active_grade_soups"] = {
            "C": grade_soup_recipe(active_frontier(original), "C", GRADES["C"])}
        original["baseline_roles"] = {"A.0": "b" * 64}
        before = deepcopy(original)
        student = _exam("d", 210)["checkpoint"]
        result, changed = reset_active_championships(
            original, student=student, generation=400)
        self.assertTrue(changed)
        self.assertEqual(original, before)
        self.assertEqual(result["active_roles"], {})
        self.assertEqual(result["active_grade_soups"], {})
        self.assertEqual(result["guidance_policy"], EARNED_ONLY_POLICY)
        historic = result["superseded_active_championships"][-1]
        self.assertEqual(historic["active_roles"], original["active_roles"])

    def test_reset_and_rebase_preserve_permanent_settled_match_ledger(self):
        original = _epoch()
        original["settled_matchups"] = {
            "A.0|" + "a" * 64 + "|" + "c" * 64: {"winner_sha256": "a" * 64}}
        student = _exam("d", 210)["checkpoint"]
        reset, _ = reset_active_championships(
            original, student=student, generation=400)
        self.assertEqual(reset["settled_matchups"], original["settled_matchups"])
        baseline = _exam("e", 208)["checkpoint"]
        rebased = rebase_active_championships(
            reset, prior_student=student, baseline=baseline, generation=401)
        self.assertEqual(rebased["settled_matchups"], original["settled_matchups"])

    def test_reset_baseline_cannot_immediately_reclaim_title(self):
        current = _exam("c", 209)["checkpoint"]
        cleared, _ = reset_active_championships(
            _epoch(), student=current, generation=400)
        same_step = _panel("c", 10, "C.0", 12, grade="C")
        result, changes, _ = advance_epoch(
            cleared, grades=GRADES, challenger_exam=same_step, incumbent_exams={})
        self.assertEqual(changes, ())
        self.assertEqual(result["active_roles"], {})
        later = _panel("d", 11, "C.0", 12, grade="C")
        result, changes, _ = advance_epoch(
            cleared, grades=GRADES, challenger_exam=later, incumbent_exams={})
        self.assertEqual(changes, ("C.0",))
        self.assertEqual(result["active_roles"]["C.0"]["checkpoint"]["sha256"],
                         "d" * 64)
