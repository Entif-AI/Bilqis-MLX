"""Disposable production-path checks for retention teaching and mentor epochs."""
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx import grade_a_trainer as trainer
from bilqis_mlx.learning_experiment import Settings, earlier_grade_capabilities
from bilqis_mlx.mentor_epoch import (
    begin_epoch, qualify_candidate, active_adviser_checkpoints,
)
from bilqis_mlx.timing_trace import TimingTrace


class _BatchCaptured(Exception):
    pass


def _rows(capability):
    return [{"id": f"{capability}:{index}", "source_id": f"{capability}:{index}",
             "capability": capability, "answer_kind": "binary",
             "gold": "TRUE" if index % 2 else "FALSE",
             "tokens": [3, 4, index + 5]}
            for index in range(12)]


class RetentionTeachingPathTests(unittest.TestCase):
    def _visit_selection(self, old):
        policy = {"old": old, "lr": 0.0001, "depth": 1,
                  "contrast": 1., "distill": 0., "preview": 0}
        teacher = {"strategies": {"p": policy}}
        engine = SimpleNamespace(pick=lambda *_: ("p", policy))
        school = SimpleNamespace(stage="MAIN", grade="B", visits=0,
                                 champions={"A": {"optimizer_step": 1}})
        grades = [SimpleNamespace(id=grade, capabilities=[SimpleNamespace(id=cap)])
                  for grade, cap in (("A", "A.IDENTITY"), ("B", "B.XOR"))]
        course = SimpleNamespace(grades=grades, capability_map={})
        receipt = {"teacher": teacher, "generation": 1, "run_id": "disposable",
                   "school": {}, "teacher_misses": [], "config": {},
                   "answer_ids": [6, 7], "curriculum_mode": "fixture-school"}
        optimizer = SimpleNamespace(learning_rate=0.0001,
                                    state={"step": SimpleNamespace(item=lambda: 1)})
        captured = []

        def source_rows(*_args, **kwargs):
            return _rows(kwargs["capability"])

        def inspect_batch(_mx, _parameters, _optimizer, rows, *_args, **_kwargs):
            captured.extend(row["capability"] for row in rows)
            raise _BatchCaptured("STOP_BEFORE_ANY_OPTIMIZER")

        def wrong_predictions(_mx, _params, rows, *_args):
            return {row["id"]: ("FALSE" if row["gold"] == "TRUE" else "TRUE")
                    for row in rows}

        with (patch.object(trainer, "_state_from_json", return_value=school),
              patch.object(trainer, "next_capability", return_value="B.XOR"),
              patch.object(trainer, "_draw_live_rows", side_effect=source_rows),
              patch.object(trainer, "_frozen_confidence_champions", return_value=()),
              patch.object(trainer, "_frozen_grade_soup_votes", return_value=((), ())),
              patch.object(trainer, "_train_score", return_value=0.5),
              patch.object(trainer, "_learning_probe_rows",
                           return_value=(_rows("B.XOR")[:6], set(), 0)),
              patch.object(trainer, "_predictions", side_effect=wrong_predictions),
              patch.object(trainer, "fork_student",
                           return_value=({}, optimizer)),
              patch("bilqis_mlx.fragile_replay.load_replay_rows", return_value=()),
              patch.object(trainer, "_train_step", side_effect=inspect_batch)):
            with self.assertRaisesRegex(_BatchCaptured, "STOP_BEFORE_ANY_OPTIMIZER"):
                trainer._take_visit(None, Path("/never-opened"), receipt, {},
                                    course, engine, {}, optimizer, {},
                                    steps_per_visit=1, batch_size=8,
                                    reserve_gib=0., source_root=Path("/not-used"),
                                    learning_settings=Settings())
        self.assertEqual(len(captured), 8)
        return captured

    def test_binary_grade_b_visit_rehearses_source_bound_grade_a_when_requested(self):
        delivered = self._visit_selection(old=16)
        self.assertIn("A.IDENTITY", delivered)
        self.assertIn("B.XOR", delivered)

    def test_binary_grade_b_visit_does_not_invent_old_examples_at_zero_policy(self):
        self.assertEqual(set(self._visit_selection(old=0)), {"B.XOR"})

    def test_real_visit_path_emits_coarse_write_ahead_timing_markers(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.jsonl"
            with TimingTrace(path):
                self._visit_selection(old=0)
            rows = [json.loads(line) for line in path.read_text().splitlines()]

        names = [row.get("name") for row in rows]
        self.assertIn("VISIT_START", names)
        self.assertIn("VISIT_SOURCE_DRAW", names)
        self.assertIn("STEP_SOURCE_DRAW", names)
        self.assertIn("STEP_TRAIN", names)

    def test_older_grade_pool_excludes_target_grade_and_future_grades(self):
        grades = [SimpleNamespace(id=grade, capabilities=[SimpleNamespace(id=cap)])
                  for grade, cap in (("A", "A.IDENTITY"), ("B", "B.XOR"),
                                     ("C", "C.COUNT"), ("D", "D.NEW"))]
        course = SimpleNamespace(grades=grades)
        completed = {"A": object(), "B": object(), "C": object(),
                     "D": object()}
        self.assertEqual(earlier_grade_capabilities(course, completed, "B.XOR"),
                         ("A.IDENTITY",))
        self.assertEqual(earlier_grade_capabilities(course, completed, "C.COUNT"),
                         ("A.IDENTITY", "B.XOR"))
        self.assertEqual(earlier_grade_capabilities(course, completed, "A.IDENTITY"),
                         ())
        with self.assertRaisesRegex(ValueError, "UNKNOWN_TARGET_GRADE"):
            earlier_grade_capabilities(course, completed, "E.UNKNOWN")

    def test_fresh_fragile_preservation_covers_truth_tables_without_exam_ids(self):
        fixed = []
        fresh_by_cap = {}
        def operand(kind):
            if kind == "EQ":
                return {"kind": "compare", "operator": "EQ", "args": [
                    {"kind": "entity", "name": "A"},
                    {"kind": "entity", "name": "B"}]}
            return {"kind": "relation", "name": kind, "args": [
                {"kind": "entity", "name": "A"},
                {"kind": "entity", "name": "B"}]}
        for capability in ("B.OR", "B.XOR"):
            candidates = []
            for index, bits in enumerate((
                    (False, False), (False, True), (True, False), (True, True))):
                gold = ("TRUE" if (any(bits) if capability == "B.OR"
                                   else bits[0] != bits[1]) else "FALSE")
                kinds = (("PARENT", "EQ") if index % 2 == 0
                         else ("LINK", "PARENT"))
                shape = {
                    "universe_size": 3 + index % 2,
                    "record": {"query": {
                        "kind": "apply", "operator": capability[2:],
                        "args": [operand(kind) for kind in kinds]}},
                }
                fixed.append({"id": f"exam:{capability}:{index}",
                              "capability": capability, "gold": gold,
                              "operand_truths": list(bits), "tokens": [1, 2, 3],
                              **shape})
                candidates.append({"id": f"fresh:{capability}:{index}",
                                   "capability": capability, "gold": gold,
                                   "operand_truths": list(bits), "tokens": [4, 5, 6],
                                   **shape})
            fresh_by_cap[capability] = candidates

        def draw(*_args, **kwargs):
            return fresh_by_cap[kwargs["capability"]]

        school = SimpleNamespace()
        receipt = {"run_id": "preservation", "generation": 4}
        with (patch("bilqis_mlx.fragile_replay.load_replay_rows",
                    return_value=tuple(fixed)),
              patch.object(trainer, "assessment_capabilities",
                           return_value=("B.AND", "B.OR", "B.XOR")),
              patch.object(trainer, "_draw_live_rows", side_effect=draw)):
            selected = trainer._fresh_fragile_preservation_rows(
                Path("/unused"), Path("/source"), {}, receipt, object(), school,
                "B.AND", step=1, batch_size=32)
        self.assertEqual(len(selected), 8)
        self.assertFalse({row["id"] for row in selected} &
                         {row["id"] for row in fixed})
        self.assertEqual(
            {(row["capability"], tuple(row["operand_truths"])) for row in selected},
            {(capability, bits)
             for capability in ("B.OR", "B.XOR")
             for bits in ((False, False), (False, True), (True, False), (True, True))},
        )

    def test_fragile_preservation_reserves_batch_capacity_before_miss_replay(self):
        policy = {"old": 0, "lr": 0.0001, "depth": 1,
                  "contrast": 1., "distill": 0., "preview": 0}
        teacher = {"strategies": {"p": policy}}
        engine = SimpleNamespace(pick=lambda *_: ("p", policy))
        school = SimpleNamespace(stage="MAIN", grade="B", visits=0,
                                 champions={"A": {"optimizer_step": 1}})
        grades = [SimpleNamespace(id=grade, capabilities=[SimpleNamespace(id=cap)])
                  for grade, cap in (("A", "A.IDENTITY"), ("B", "B.XOR"))]
        course = SimpleNamespace(grades=grades, capability_map={})
        misses = [
            {"id": f"miss:{index}", "source_id": f"miss:{index}",
             "capability": "B.XOR", "answer_kind": "binary",
             "gold": "TRUE" if index % 2 else "FALSE",
             "tokens": [8, 9, index + 10]}
            for index in range(30)
        ]
        preservation = tuple(
            {"id": f"preserve:{index}", "capability": "B.XOR",
             "answer_kind": "binary",
             "gold": "TRUE" if index % 2 else "FALSE",
             "operand_truths": [bool(index & 1), bool(index & 2)],
             "tokens": [20, 21, index + 22]}
            for index in range(8)
        )
        receipt = {"teacher": teacher, "generation": 1, "run_id": "capacity",
                   "school": {}, "teacher_misses": misses, "config": {},
                   "answer_ids": [6, 7], "curriculum_mode": "fixture-school"}
        optimizer = SimpleNamespace(learning_rate=0.0001,
                                    state={"step": SimpleNamespace(item=lambda: 1)})
        captured = []

        def source_rows(*_args, **kwargs):
            return _rows(kwargs["capability"])

        def inspect_batch(_mx, _parameters, _optimizer, rows, *_args, **_kwargs):
            captured.extend(rows)
            raise _BatchCaptured("STOP_BEFORE_ANY_OPTIMIZER")

        def wrong_predictions(_mx, _params, rows, *_args):
            return {row["id"]: ("FALSE" if row["gold"] == "TRUE" else "TRUE")
                    for row in rows}

        with (patch.object(trainer, "_state_from_json", return_value=school),
              patch.object(trainer, "next_capability", return_value="B.XOR"),
              patch.object(trainer, "_draw_live_rows", side_effect=source_rows),
              patch.object(trainer, "_frozen_confidence_champions", return_value=()),
              patch.object(trainer, "_frozen_grade_soup_votes", return_value=((), ())),
              patch.object(trainer, "_train_score", return_value=0.5),
              patch.object(trainer, "_learning_probe_rows",
                           return_value=(_rows("B.XOR")[:6], set(), 0)),
              patch.object(trainer, "_predictions", side_effect=wrong_predictions),
              patch.object(trainer, "fork_student", return_value=({}, optimizer)),
              patch("bilqis_mlx.fragile_replay.load_replay_rows",
                    return_value=({"id": "fixed"},)),
              patch.object(trainer, "_fresh_fragile_preservation_rows",
                           return_value=preservation),
              patch.object(trainer, "_train_step", side_effect=inspect_batch)):
            with self.assertRaisesRegex(_BatchCaptured, "STOP_BEFORE_ANY_OPTIMIZER"):
                trainer._take_visit(None, Path("/never-opened"), receipt, {},
                                    course, engine, {}, optimizer, {},
                                    steps_per_visit=1, batch_size=32,
                                    reserve_gib=0., source_root=Path("/not-used"),
                                    learning_settings=Settings())

        self.assertEqual(len(captured), 32)
        self.assertEqual({row["id"] for row in preservation} &
                         {row["id"] for row in captured},
                         {row["id"] for row in preservation})
        delivered_misses = {row["id"] for row in captured if row["id"].startswith("miss:")}
        self.assertEqual(len(delivered_misses), 24)


def _pointer(seed):
    return {"filename": "bundles/" + seed, "sha256": seed * 64,
            "optimizer_step": 100, "model_and_native_adamw": True}


def _exam(checkpoint, scores, *, cohort="c" * 64):
    return {"checkpoint_sha256": checkpoint["sha256"],
            "cohort_sha256": cohort, "rubric_sha256": "b" * 64,
            "assessment_scope_sha256": "e" * 64,
            "source_graph_sha256": "d" * 64,
            "scores": {cap: {"correct": correct, "total": 12}
                       for cap, correct in scores.items()}}


class MentorEpochTests(unittest.TestCase):
    def setUp(self):
        self.graduated = _pointer("a")
        self.extended_baseline = _pointer("b")
        self.prior_scores = {"A.ONE": {"correct": 12, "total": 12},
                             "B.XOR": {"correct": 12, "total": 12}}
        self.epoch = begin_epoch(
            previous_graduate=self.graduated,
            admitted_baseline=self.extended_baseline,
            introduced_grade="C", source_graph_sha256="d" * 64,
            previous_capabilities=tuple(self.prior_scores),
            previous_graduation_exam={
                "checkpoint_sha256": self.graduated["sha256"],
                "rubric_sha256": "b" * 64, "cohort_sha256": "a" * 64,
                "scores": self.prior_scores})

    def test_epoch_archives_history_without_historical_adviser_votes(self):
        self.assertEqual(self.epoch["previous_graduate"], self.graduated)
        self.assertEqual(self.epoch["baseline"], self.extended_baseline)
        self.assertEqual(active_adviser_checkpoints(self.epoch), ())
        self.assertEqual(self.epoch["qualified"], [])

    def test_epoch_does_not_start_from_separately_mastered_grade_best_scores(self):
        imperfect = {**self.prior_scores, "B.XOR": {"correct": 11, "total": 12}}
        with self.assertRaisesRegex(ValueError, "COMPLETE_PREVIOUS_GRADUATION"):
            begin_epoch(previous_graduate=self.graduated,
                        admitted_baseline=self.extended_baseline,
                        introduced_grade="C", source_graph_sha256="d" * 64,
                        previous_capabilities=tuple(self.prior_scores),
                        previous_graduation_exam={
                            "checkpoint_sha256": self.graduated["sha256"],
                            "rubric_sha256": "b" * 64,
                            "cohort_sha256": "a" * 64, "scores": imperfect})

    def test_new_adviser_must_gain_current_capability_without_large_mature_loss(self):
        candidate = _pointer("f")
        baseline = _exam(self.extended_baseline,
                         {"A.ONE": 12, "B.XOR": 12, "C.COUNT": 3})
        modest = _exam(candidate, {"A.ONE": 11, "B.XOR": 12, "C.COUNT": 6})
        trial = qualify_candidate(self.epoch, candidate, baseline, modest,
                                  mature_loss_budget=1)
        self.assertEqual(trial["decision"], "QUALIFIED")
        # Paired improvement is historical evidence, not a championship.
        self.assertEqual(active_adviser_checkpoints(trial["epoch"]), ())
        self.assertEqual(active_adviser_checkpoints(
            trial["epoch"], cohort_sha256="f" * 64),
            ())
        tied = qualify_candidate(trial["epoch"], _pointer("9"), baseline,
                                 _exam(_pointer("9"),
                                       {"A.ONE": 11, "B.XOR": 12, "C.COUNT": 6}),
                                 mature_loss_budget=1)
        self.assertEqual(tied["decision"], "HOLD_NO_BETTER_SAME_SCOPE_REFERENCE")
        harmful = _exam(candidate, {"A.ONE": 9, "B.XOR": 12, "C.COUNT": 10})
        rejected = qualify_candidate(self.epoch, candidate, baseline, harmful,
                                     mature_loss_budget=1)
        self.assertEqual(rejected["decision"], "HOLD_MATURE_LOSS")
        self.assertEqual(active_adviser_checkpoints(rejected["epoch"]), ())
        changed = _exam(candidate, {"A.ONE": 12, "B.XOR": 12, "C.COUNT": 3})
        no_gain = qualify_candidate(self.epoch, candidate, baseline, changed,
                                    mature_loss_budget=1)
        self.assertEqual(no_gain["decision"], "HOLD_NO_NEW_GRADE_GAIN")

    def test_cross_cohort_cannot_promote_adviser_and_never_changes_student(self):
        candidate = _pointer("f")
        old = _exam(self.extended_baseline,
                    {"A.ONE": 12, "B.XOR": 12, "C.COUNT": 3})
        new = _exam(candidate, {"A.ONE": 12, "B.XOR": 12, "C.COUNT": 8},
                    cohort="f" * 64)
        with self.assertRaisesRegex(ValueError, "MISMATCHED_EXAMINATION"):
            qualify_candidate(self.epoch, candidate, old, new,
                              mature_loss_budget=1)
        self.assertEqual(self.epoch["qualified"], [])

    def test_opted_in_epoch_uses_no_unearned_baseline_or_archived_soup_votes(self):
        graph = {"tokens": ["PAD", "A"], "nodes": [],
                 "row_contract_sha256": {}}
        epoch = {**self.epoch,
                 "source_graph_sha256": trainer._fingerprint(graph)}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            blob = root / "bundles" / "b" / "model-and-own-adamw.safetensors"
            blob.parent.mkdir(parents=True)
            blob.write_bytes(b"inert-mentor-test-blob")
            receipt = {"mentor_epoch": epoch,
                       "grade_soups": {"B": {"vote_count": 6}}}
            with (patch.object(trainer, "_frozen_confidence_champions",
                               return_value=()) as fresh_champs,
                  patch.object(trainer, "_frozen_grade_soup_votes",
                               return_value=((), ())) as fresh_soups,
                  patch.object(trainer, "_cached_frozen_champion",
                               return_value=({"synthetic": "weights"}, graph))):
                champions, soups, receipts = trainer._mentor_sources_for_visit(
                    root, receipt, "C", graph, 3)
            fresh_champs.assert_not_called()
            fresh_soups.assert_not_called()
        self.assertEqual(soups, ())
        self.assertEqual(receipts, ())
        self.assertEqual(champions, ())

    def test_epoch_references_survive_checkpoint_retirement(self):
        record = {"generation": 4, "mentor_epoch": {**self.epoch,
                  "qualified": [{"checkpoint": _pointer("f")}]},
                  "school": {"active_grades": ["A", "B", "C"], "grade_index": 2,
                             "current_student": _pointer("c"), "champions": {}},
                  "capability_best": {}, "grade_soups": {}}
        with (patch.object(trainer, "_boundary_delivery_events", return_value=()),
              patch.object(trainer, "_quarantine_newer_uncommitted_bundles"),
              patch.object(trainer, "retire_bundles", return_value=()) as retire,
              patch.object(trainer, "retire_stale_soups", return_value=())):
            trainer._publish_boundary(Path("/not-created"), record, (), ())
        self.assertTrue({"bundles/a", "bundles/b", "bundles/f"} <=
                        retire.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
