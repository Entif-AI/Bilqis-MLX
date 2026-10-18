"""User-specified champion roles and cross-grade soup teaching contracts."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx import grade_a_trainer as trainer
from bilqis_mlx.champion_confidence import champion_roster


def _pointer(seed):
    return {"filename": "bundles/" + seed, "sha256": seed * 64,
            "optimizer_step": 10, "model_and_native_adamw": True}


def _grade_b_frontier():
    frontier, roles = {}, []
    owners = {"B.AND": "a", "B.IFF": "a", "B.IMPLIES": "b",
              "B.NOT": "a", "B.OR": "c", "B.XOR": "a"}
    rubric = "1" * 64
    for cap, seed in owners.items():
        role = {"capability": cap, "rubric": rubric,
                "checkpoint_sha256": _pointer(seed)["sha256"]}
        roles.append(role)
        frontier[rubric + ":" + cap] = {
            **role, "breadth": {"a": 16, "b": 15, "c": 14}[seed],
            "perfect_capabilities": [cap] + ["A." + str(n) for n in range(
                {"a": 16, "b": 15, "c": 14}[seed] - 1)],
            "checkpoint": _pointer(seed)}
        # A past rubric with a lower mastery count is *not* another active
        # championship, regardless of its historical perfect score.
        frontier["2" * 64 + ":" + cap] = {
            "capability": cap, "rubric": "2" * 64, "breadth": 2,
            "perfect_capabilities": [cap, "A.OLD"],
            "checkpoint": _pointer("d")}
    snapshot = {"grade": "B", "vote_count": 6,
                "perfect_capabilities": sorted(owners),
                "roles": roles}
    return frontier, snapshot


class GradeMentorFidelityTests(TestCase):
    def test_newly_earned_champions_and_soups_replace_bootstrap_guidance(self):
        from bilqis_mlx.mentor_epoch import begin_epoch
        graph = {"tokens": ["PAD", "TRUE", "FALSE"]}
        graduate, baseline, earned = (_pointer(key) for key in "abc")
        epoch = begin_epoch(
            previous_graduate=graduate, admitted_baseline=baseline,
            introduced_grade="C", source_graph_sha256=trainer._fingerprint(graph),
            previous_capabilities=("A.IDENTITY",),
            previous_graduation_exam={
                "checkpoint_sha256": graduate["sha256"],
                "rubric_sha256": "d" * 64, "cohort_sha256": "e" * 64,
                "scores": {"A.IDENTITY": {"correct": 12, "total": 12}},
            })
        epoch["active_roles"] = {
            "C.COUNT": {"capability": "C.COUNT", "rubric": "f" * 64,
                        "checkpoint": earned, "breadth": 5,
                        "perfect_capabilities": ["C.COUNT"] + [
                            "A." + str(n) for n in range(4)]}}
        epoch["active_grade_soups"] = {"C": {"grade": "C", "vote_count": 1}}
        receipt = {"mentor_epoch": epoch,
                   "graduation_perfect": {"historic": {"checkpoint": graduate}},
                   "grade_soups": {"A": {"grade": "A", "vote_count": 6}}}
        with (patch.object(trainer, "_frozen_confidence_champions",
                           return_value=({"checkpoint_sha256": earned["sha256"],
                                          "breadth": 5},)) as champions,
              patch.object(trainer, "_frozen_grade_soup_votes",
                           return_value=(("new-epoch-soup",), ("receipt",))) as soups,
              patch.object(trainer, "_cached_frozen_champion",
                           side_effect=AssertionError("bootstrap must yield"))):
            live, frozen, events = trainer._mentor_sources_for_visit(
                Path("/unused"), receipt, "C", graph, 3)
        self.assertEqual(live[0]["checkpoint_sha256"], earned["sha256"])
        self.assertEqual(frozen, ("new-epoch-soup",))
        self.assertEqual(events, ("receipt",))
        selected = champions.call_args.args[1]
        self.assertEqual(set(selected["graduation_perfect"]), {
            "f" * 64 + ":C.COUNT"})
        self.assertEqual(set(soups.call_args.args[1]["grade_soups"]), {"C"})

    def test_graduation_resets_every_old_role_to_no_active_champions(self):
        from bilqis_mlx.mentor_epoch import begin_epoch
        graph = {"tokens": ["PAD", "TRUE", "FALSE"]}
        older, baseline = _pointer("a"), _pointer("b")
        prior = ("A.IDENTITY", *tuple("B." + name for name in (
            "AND", "IFF", "IMPLIES", "NOT", "OR", "XOR")))
        exam = {"checkpoint_sha256": older["sha256"],
                "cohort_sha256": "c" * 64, "rubric_sha256": "d" * 64,
                "scores": {cap: {"correct": 12, "total": 12} for cap in prior}}
        epoch = begin_epoch(previous_graduate=older, admitted_baseline=baseline,
                            introduced_grade="C",
                            source_graph_sha256=trainer._fingerprint(graph),
                            previous_capabilities=prior,
                            previous_graduation_exam=exam)
        self.assertEqual(epoch["baseline_roles"], {})
        self.assertEqual(epoch["active_roles"], {})
        self.assertEqual(epoch["active_grade_soups"], {})
        self.assertEqual(epoch["earned_role_votes_at_reset"], 0)
        self.assertEqual(epoch["championship_eligibility_after_step"],
                         baseline["optimizer_step"])

    def test_grade_b_has_six_roles_and_not_extra_historical_votes(self):
        frontier, snapshot = _grade_b_frontier()
        active = champion_roster(frontier, "B", snapshot=snapshot)
        self.assertEqual(sum(1 for r in snapshot["roles"] if r["capability"].startswith("B.")), 6)
        self.assertEqual(len(active), 3)
        self.assertEqual({m["checkpoint"]["sha256"] for m in active},
                         {_pointer(seed)["sha256"] for seed in "abc"})
        self.assertNotIn(_pointer("d")["sha256"],
                         {m["checkpoint"]["sha256"] for m in active})

    def test_new_grade_epoch_suppresses_all_unearned_and_old_mentors(self):
        from bilqis_mlx.mentor_epoch import active_adviser_checkpoints, begin_epoch
        graph = {"tokens": ["PAD", "TRUE", "FALSE"]}
        graduated, baseline = _pointer("a"), _pointer("b")
        exam = {"checkpoint_sha256": graduated["sha256"],
                "cohort_sha256": "c" * 64, "rubric_sha256": "d" * 64,
                "scores": {"A.IDENTITY": {"correct": 12, "total": 12}}}
        epoch = begin_epoch(previous_graduate=graduated, admitted_baseline=baseline,
                            introduced_grade="B",
                            source_graph_sha256=trainer._fingerprint(graph),
                            previous_capabilities=("A.IDENTITY",),
                            previous_graduation_exam=exam)
        self.assertEqual(epoch["baseline_roles"], {})
        self.assertEqual(epoch["earned_role_votes_at_reset"], 0)
        self.assertEqual(active_adviser_checkpoints(epoch), ())
        current = {"mentor_epoch": epoch, "graduation_perfect": {},
                   "grade_soups": {}}
        with (patch.object(trainer, "_frozen_confidence_champions", return_value=()) as champions,
              patch.object(trainer, "_frozen_grade_soup_votes", return_value=((), ())) as soups,
              patch.object(trainer, "_cached_frozen_champion",
                           return_value=({"frozen": True}, graph)),
              patch("pathlib.Path.stat") as stat):
            stat.return_value.st_size = 1
            stat.return_value.st_mtime_ns = 1
            roster, soups_roster, receipts = trainer._mentor_sources_for_visit(
                Path("/nonexistent"), current, "B", graph, 2)
        self.assertEqual(roster, ())
        self.assertEqual(soups_roster, ())
        self.assertEqual(receipts, ())
        champions.assert_not_called()
        soups.assert_not_called()
