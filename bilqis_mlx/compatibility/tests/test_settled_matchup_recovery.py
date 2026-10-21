"""Read-only proof of settlement-ledger recovery after the bad rubric repair."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bilqis_mlx.compatibility.settled_matchup_recovery import (
    recover_scope_rubric_settled_matchups,
)
from bilqis_mlx.runtime.state import _fingerprint


def _sha(symbol: str) -> str:
    return symbol * 64


class SettledMatchupRecoveryTests(unittest.TestCase):
    def _fixture(self, root: Path):
        identity = {
            "schema": "bilqis.mlx.championship-school-identity/v1",
            "course_sha256": _sha("1"),
            "semantic_graph_sha256": _sha("2"),
            "factory_release_sha256": _sha("3"),
            "parameter_shapes": {"embedding.weight": [8, 4]},
            "sha256": _sha("4"),
        }
        left, right = _sha("a"), _sha("b")
        ledger = {
            f"B.AND|{left}|{right}": {
                "capability": "B.AND",
                "decision": "TITLE_WON",
                "incumbent_sha256": left,
                "challenger_sha256": right,
                "winner_sha256": right,
                "source_generation": 9,
            },
        }
        older_epoch = {
            "schema": "bilqis.mlx.mentor-epoch-trial/v1",
            "introduced_grade": "C",
            "source_graph_sha256": _sha("2"),
            "championship_school_identity": deepcopy(identity),
            "settled_matchups": {},
        }
        source_epoch = {
            "schema": "bilqis.mlx.mentor-epoch-trial/v1",
            "introduced_grade": "B",
            "source_graph_sha256": _sha("2"),
            "championship_school_identity": deepcopy(identity),
            "active_roles": {"B.AND": {"checkpoint": {"sha256": right}}},
            "settled_matchups": deepcopy(ledger),
        }
        student = {
            "sha256": _sha("c"),
            "filename": "bundles/current",
            "optimizer_step": 77,
            "model_and_native_adamw": True,
        }
        source = {
            "generation": 10,
            "championship_school_identity": deepcopy(identity),
            "school": {"current_student": deepcopy(student)},
            "mentor_epoch": deepcopy(source_epoch),
            "championship_epoch_history": [deepcopy(older_epoch)],
        }
        reset_epoch = {
            "schema": "bilqis.mlx.mentor-epoch-trial/v1",
            "introduced_grade": "B",
            "source_graph_sha256": _sha("2"),
            "championship_school_identity": deepcopy(identity),
            "active_roles": {},
            "settled_matchups": {},
        }
        repair = {
            "generation": 11,
            "championship_school_identity": deepcopy(identity),
            "school": {"current_student": deepcopy(student)},
            "mentor_epoch": deepcopy(reset_epoch),
            "championship_epoch_history": [
                deepcopy(older_epoch), deepcopy(source_epoch)],
        }
        current = {
            **deepcopy(repair),
            "generation": 20,
            "mentor_epoch": {
                **deepcopy(reset_epoch),
                "active_roles": {"B.IFF": {"checkpoint": {"sha256": _sha("d")}}},
            },
        }
        event = {
            "event": "SCHOOL_SCOPE_RUBRIC_EVIDENCE_REPAIRED",
            "generation": 11,
            "source_generation": 10,
            "student_sha256": student["sha256"],
            "optimizer_step": student["optimizer_step"],
            "archived_bad_epoch": True,
            "actual_neural_updates": 0,
            "model_and_own_adamw_unchanged": True,
        }
        run_id = "immutable-settlement-repair-fixture"
        for state in (source, repair, current):
            state["run_id"] = run_id
        event["event_id"] = _fingerprint([
            "school-generation-event/v1", run_id, event["generation"],
            0, event])
        repair["delivery_outbox"] = [deepcopy(event)]
        states = root / "states"
        states.mkdir(parents=True)
        for state in (source, repair, current):
            (states / f"{state['generation']:07d}.json").write_text(
                json.dumps(state, sort_keys=True), encoding="utf-8")
        (root / "events.jsonl").write_text(
            json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")
        return current, ledger, event

    def test_recovers_exact_archived_ledger_and_proof(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            current, expected, event = self._fixture(root)
            before = {
                path.relative_to(root): path.read_bytes()
                for path in root.rglob("*") if path.is_file()
            }

            ledger, proof = recover_scope_rubric_settled_matchups(root, current)

            after = {
                path.relative_to(root): path.read_bytes()
                for path in root.rglob("*") if path.is_file()
            }
        self.assertEqual(ledger, expected)
        self.assertEqual(before, after)
        self.assertEqual(proof["source_generation"], 10)
        self.assertEqual(proof["repair_generation"], 11)
        self.assertEqual(proof["current_generation"], 20)
        self.assertEqual(proof["repair_event_id"], event["event_id"])
        self.assertEqual(proof["settled_matchup_count"], 1)
        self.assertEqual(proof["championship_school_identity_sha256"], _sha("4"))

    def test_rejects_newer_settlement_event(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            current, _, _ = self._fixture(root)
            with (root / "events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({
                    "event": "SCHOOL_LIVE_EXAM_COMMITTED",
                    "generation": 15,
                    "championship_epoch": {
                        "cross_origin_decisions": [{
                            "capability": "B.AND",
                            "decision": "TITLE_DEFENDED",
                            "incumbent_sha256": _sha("a"),
                            "challenger_sha256": _sha("b"),
                        }],
                    },
                }) + "\n")

            with self.assertRaisesRegex(
                    ValueError, "SETTLED_MATCHUP_RECOVERY_NEWER_SETTLEMENT"):
                recover_scope_rubric_settled_matchups(root, current)

    def test_rejects_extra_epoch_reset(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            current, _, _ = self._fixture(root)
            current["mentor_epoch"]["active_championship_reset"] = {
                "source_generation": 18,
                "student_sha256": _sha("c"),
                "optimizer_step": 77,
            }
            (root / "states" / "0000020.json").write_text(
                json.dumps(current, sort_keys=True), encoding="utf-8")

            with self.assertRaisesRegex(
                    ValueError, "SETTLED_MATCHUP_RECOVERY_EXTRA_EPOCH_RESET"):
                recover_scope_rubric_settled_matchups(root, current)

    def test_rejects_journal_source_generation_mismatch(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            current, _, event = self._fixture(root)
            event["source_generation"] = 9
            (root / "events.jsonl").write_text(
                json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(
                    ValueError, "SETTLED_MATCHUP_RECOVERY_TRANSITION_NOT_PROVEN"):
                recover_scope_rubric_settled_matchups(root, current)

    def test_rejects_forged_or_unpublished_event_id(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            current, _, event = self._fixture(root)
            event["event_id"] = _sha("0")
            (root / "events.jsonl").write_text(
                json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "REPAIR_EVENT_CUSTODY_DRIFT"):
                recover_scope_rubric_settled_matchups(root, current)


if __name__ == "__main__":
    unittest.main()
