"""The complete school, not a soup or isolated grade, awards epoch titles."""
from copy import deepcopy
from types import MappingProxyType
from unittest import TestCase

from bilqis_mlx.epoch_championships import (
    active_frontier, advance_epoch, needed_incumbents)
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
    def test_new_grade_earns_roles_while_prior_soups_stay_archived(self):
        epoch = _epoch()
        candidate = _exam("c", 209)
        before = deepcopy(epoch)
        needed = needed_incumbents(epoch, grades=GRADES,
                                   scores=candidate["scores"])
        self.assertEqual(set(needed), {epoch["baseline"]["sha256"]})
        upgraded, changes, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=candidate,
            incumbent_exams={epoch["baseline"]["sha256"]: _exam("b", 208)})
        self.assertEqual(epoch, before)
        self.assertTrue(set(GRADES["B"]) <= set(changes))
        self.assertTrue(set(GRADES["A"]) <= set(changes))
        self.assertTrue(set(GRADES["C"]) & set(changes))
        self.assertEqual({decision["decision"] for decision in decisions},
                         {"ELIGIBLE"})
        self.assertEqual(set(upgraded["active_roles"]["B.XOR"]["perfect_capabilities"]),
                         {cap for cap in SCHOOL
                          if candidate["scores"][cap]["correct"] ==
                          candidate["scores"][cap]["total"]})
        soup = grade_soup_recipe(active_frontier(upgraded), "B", GRADE_B)
        self.assertEqual(soup["vote_count"], 6)
        self.assertEqual(soup["members"][0]["votes"], 6)
        self.assertEqual(upgraded["historical_advisers_remain_archived"], True)

    def test_cross_origin_tie_or_imperfect_grade_keeps_baseline(self):
        epoch = _epoch()
        challenger = _exam("c", 208)
        changed, _, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams={epoch["baseline"]["sha256"]: _exam("b", 208)})
        self.assertNotIn("B.XOR", changed["active_roles"])
        self.assertEqual({d["decision"] for d in decisions},
                         {"DENY_NO_STRICT_SCHOOL_VICTORY"})
        challenger = _exam("c", 209)
        challenger["scores"]["B.XOR"]["correct"] = 11
        challenger["scores"]["C.0"]["correct"] += 1
        changed, roles, decisions = advance_epoch(
            epoch, grades=GRADES, challenger_exam=challenger,
            incumbent_exams={epoch["baseline"]["sha256"]: _exam("b", 208)})
        self.assertNotIn("B.XOR", roles)
        self.assertNotIn("B.XOR", changed["active_roles"])
        self.assertTrue(all(d["grade"] != "B" for d in decisions))

    def test_multi_incumbent_target_grade_must_beat_strongest(self):
        initial = _epoch()
        early, _, _ = advance_epoch(
            initial, grades=GRADES, challenger_exam=_exam("a", 207),
            incumbent_exams={initial["baseline"]["sha256"]: _exam("b", 206)})
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
