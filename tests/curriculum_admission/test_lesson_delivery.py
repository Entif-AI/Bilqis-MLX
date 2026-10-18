"""Exercise the production lesson router, not the typed-selection helper alone.

Only source-drawing/model-optimization boundaries are substituted. The actual
_take_visit selection, prior-grade routing, and missed-question replay execute.
The stop-before-optimizer exception makes this safe even beside a human run.
These generated source-boundary witnesses are NOT a source attestation for D.
"""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx import grade_a_trainer as trainer


class _BatchReached(Exception):
    def __init__(self, rows):
        super().__init__("DISPOSABLE_BATCH_REACHED_BEFORE_OPTIMIZER")
        self.rows = tuple(rows)


class _Scalar:
    def item(self):
        return 1


def _oracle_rows(capability, count):
    """Deterministic, independently computable fixture results at source boundary."""
    rows = []
    for i in range(count):
        x, y = i % 3, (i // 3) % 3
        if capability.startswith(("A.", "B.")):
            left, right = bool(i & 1), bool(i & 2)
            result = (left != right if capability.startswith("B.") else left == right)
            gold, kind = ("TRUE" if result else "FALSE"), "binary"
        else:
            # D.MIX is a *hypothetical* future capability, not admitted gold.
            gold, kind = str(x + y), "integer"
        rows.append({
            "id": f"fixture:{capability}:{i}",
            "source_id": f"fixture-source:{capability}:{i}",
            "capability": capability,
            "answer_kind": kind,
            "gold": gold,
            "tokens": (2 + i % 4, 3 + i % 5),
        })
    return rows


def _course():
    return SimpleNamespace(grades=tuple(
        SimpleNamespace(id=grade, capabilities=tuple(SimpleNamespace(id=cap)
            for cap in capabilities))
        for grade, capabilities in (
            ("A", ("A.IDENTITY",)),
            ("B", ("B.XOR",)),
            ("C", ("C.ADD", "C.COUNT")),
            ("D", ("D.MIX",)),
        )
    ))


def capture_production_batch(target, *, old, champions, visits=0,
                             misses=(), contrast=1.0):
    """Execute the real _take_visit dispatcher until its optimizer boundary."""
    policy = {"lr": 0.0001, "old": old, "depth": 1,
              "contrast": contrast, "distill": 0.0}
    school = SimpleNamespace(
        grade=target.partition(".")[0], stage="MAIN", visits=visits,
        champions={grade: object() for grade in champions})
    receipt = {
        "run_id": "neural-inert-curriculum-admission",
        "generation": 1,
        "school": {},
        "teacher": {},
        "config": {},
        "answer_ids": (6, 7),
        "teacher_misses": tuple(misses),
        "teacher_miss_exposures": {},
    }
    params = {}
    optimizer = SimpleNamespace(learning_rate=0.0001, state={"step": _Scalar()})
    # These are the external source/model boundaries, not lesson-routing logic.
    def source_rows(_source, _graph, *, capability, each, **_kw):
        return _oracle_rows(capability, each)

    def not_perfect(_mx, _params, rows, _config, _answer_ids):
        return {row["id"]: "__INCORRECT__" for row in rows}

    def stop_before_optimizer(_mx, _params, _optim, rows, *_args, **_kwargs):
        raise _BatchReached(rows)

    with patch.object(trainer, "_state_from_json", return_value=school), \
            patch.object(trainer, "next_capability", return_value=target), \
            patch.object(trainer, "contextual_pick", return_value=("fixture", policy)), \
            patch.object(trainer, "_draw_live_rows", side_effect=source_rows), \
            patch.object(trainer, "_train_score", return_value=0.0), \
            patch.object(trainer, "_learning_probe_rows", return_value=(
                _oracle_rows(target, 2), frozenset(), 0)), \
            patch.object(trainer, "_predictions", side_effect=not_perfect), \
            patch.object(trainer, "fork_student", return_value=(params, optimizer)), \
            patch.object(trainer, "_frozen_confidence_champions", return_value=()), \
            patch.object(trainer, "_frozen_grade_soup_votes", return_value=((), ())), \
            patch("bilqis_mlx.fragile_replay.load_replay_rows", return_value=()), \
            patch.object(trainer, "_confidence_guidance", return_value=None), \
            patch.object(trainer, "_typed_confidence_guidance", return_value=None), \
            patch.object(trainer, "_train_step", side_effect=stop_before_optimizer):
        try:
            trainer._take_visit(
                None, Path("/nonexistent-neural-inert-run"), receipt,
                {"manifest_sha256": "fixture"}, _course(), object(), params,
                optimizer, {}, steps_per_visit=1, batch_size=8,
                reserve_gib=0.0, source_root=Path("/fixture-oracle"),
                learning_settings=object(),
            )
        except _BatchReached as stopped:
            return stopped.rows
    raise AssertionError("PRODUCTION_ROUTER_DID_NOT_REACH_OPTIMIZER_BOUNDARY")


class LessonAdmissionChecks(unittest.TestCase):
    def test_binary_B_with_positive_old_rehearses_actual_earlier_A(self):
        # Previously broken: B.XOR bypasses the old policy in _take_visit.
        rows = capture_production_batch("B.XOR", old=16, champions=("A",))
        self.assertEqual(len(rows), 8)
        self.assertTrue(any(row["capability"] == "A.IDENTITY" for row in rows),
                        "B.XOR production batches must supervise earlier A directly")
        self.assertTrue(any(row["capability"] == "B.XOR" for row in rows))

    def test_typed_C_with_positive_old_also_rehearses_earlier_A(self):
        rows = capture_production_batch("C.ADD", old=16, champions=("A", "B"))
        self.assertTrue(any(row["capability"] == "A.IDENTITY" for row in rows))
        self.assertTrue(any(row["capability"] == "C.ADD" for row in rows))
        self.assertTrue(all(row["gold"].isdigit() and row["answer_kind"] == "integer"
                            for row in rows if row["capability"] == "C.ADD"))
        self.assertTrue(all(row["gold"] in ("TRUE", "FALSE") and
                            row["answer_kind"] == "binary"
                            for row in rows if row["capability"] == "A.IDENTITY"))

    def test_zero_old_never_allocates_a_prior_grade_example(self):
        for target in ("B.XOR", "C.ADD"):
            with self.subTest(target=target):
                rows = capture_production_batch(
                    target, old=0, champions=("A", "B"))
                self.assertEqual({row["capability"] for row in rows}, {target})

    def test_revalidating_C_does_not_treat_same_grade_as_old(self):
        # A revalidation can have a saved champion for the taught grade itself.
        # `old` must mean *earlier than the capability being taught*.
        rows = capture_production_batch(
            "C.ADD", old=16, champions=("A", "B", "C"), visits=3)
        self.assertTrue(any(row["capability"] != "C.ADD" for row in rows))
        self.assertTrue(all(row["capability"] in ("A.IDENTITY", "B.XOR")
                            for row in rows if row["capability"] != "C.ADD"),
                        "C.COUNT is not earlier-grade rehearsal during C.ADD")

    def test_future_D_routing_uses_prior_grades_without_redefining_outputs(self):
        # Hypothetical D exercise only; never admit or train a real D semantic.
        rows = capture_production_batch(
            "D.MIX", old=16, champions=("A", "B", "C"), visits=2)
        self.assertTrue(any(row["capability"].startswith(("A.", "B.", "C."))
                            for row in rows))
        self.assertTrue(all(row["answer_kind"] == "integer" and row["gold"].isdigit()
                            for row in rows if row["capability"] == "D.MIX"))
        self.assertTrue(any(row["capability"] == "D.MIX" for row in rows))

    def test_missed_oracle_question_survives_production_batch_replay(self):
        missed = _oracle_rows("B.XOR", 1)[0]
        missed = {**missed, "id": "prior-exam-missed-but-teachable"}
        rows = capture_production_batch(
            "B.XOR", old=0, champions=("A",), misses=(missed,))
        self.assertIn(missed["id"], {row["id"] for row in rows})


if __name__ == "__main__":
    unittest.main()
