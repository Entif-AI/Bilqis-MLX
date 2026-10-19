"""Read-only championship quarantine replay must distinguish absence from withholding."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
from unittest import TestCase

from scripts.audit_championship_quarantine import audit


def _write_run(root: Path, *, withheld: bool) -> None:
    (root / "states").mkdir(parents=True)
    student = "a" * 64
    events = [
        {
            "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
            "generation": 1,
            "grade": "A",
            "retained_optimizer_updates": 1,
            "recovered_at_student_sha256": student,
        },
        {
            "event": "SCHOOL_CAPABILITY_BEST_COMMITTED",
            "generation": 2,
            "grade": "A",
            "student_sha256": student,
            "optimizer_step": 2,
            "scores": {"A.IDENTITY": {"correct": 12, "total": 12}},
        },
        {
            "event": "SCHOOL_GRADE_A_LIVE_EXAM_COMMITTED",
            "generation": 2,
            "grade": "A",
            "student_sha256": student,
            "scores": ({"A.EDGE": {"correct": 10, "total": 12}}
                       if not withheld else {}),
            "withheld_capabilities": (["A.EDGE"] if withheld else []),
            "championship_epoch": {"cross_origin_decisions": []},
        },
    ]
    (root / "events.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
    state = {
        "school": {"current_student": {"sha256": student, "optimizer_step": 2}},
        "stagnation_session": {"quarantined": {"A.EDGE": {}}},
        "mentor_epoch": {"active_roles": {}, "championship_eligibility_after_step": -1},
    }
    (root / "states" / "0000002.json").write_text(json.dumps(state), encoding="utf-8")


class ChampionshipQuarantineAuditTests(TestCase):
    def test_measured_quarantined_capability_is_not_called_not_measured(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_run(root, withheld=False)
            result = audit(root)
        self.assertEqual(result["withheld_not_measured"], [])
        self.assertEqual(result["classification_counts"]["NOT_MEASURED"], 0)
        self.assertEqual(
            result["classification_counts"]["ROLE_MINT_AFTER_HOLISTIC_RESET"], 1)

    def test_only_explicit_withholding_is_called_not_measured(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_run(root, withheld=True)
            result = audit(root)
        self.assertEqual(result["classification_counts"]["NOT_MEASURED"], 1)
        self.assertEqual(result["withheld_not_measured"][0]["capability"], "A.EDGE")

    def test_blocked_after_perfect_score_remains_a_measured_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "states").mkdir(parents=True)
            student = "a" * 64
            events = [
                {"event": "SCHOOL_TEACHER_VISIT_COMMITTED", "generation": 1,
                 "grade": "A", "retained_optimizer_updates": 1,
                 "recovered_at_student_sha256": student},
                {"event": "SCHOOL_CAPABILITY_BEST_COMMITTED", "generation": 2,
                 "grade": "A", "student_sha256": student, "optimizer_step": 2,
                 "scores": {"A.LINK": {"correct": 12, "total": 12}}},
                {"event": "SCHOOL_GRADE_A_LIVE_EXAM_COMMITTED", "generation": 2,
                 "grade": "A", "student_sha256": student,
                 "scores": {"A.LINK": {"correct": 12, "total": 12}},
                 "withheld_capabilities": [],
                 "championship_epoch": {"cross_origin_decisions": []}},
            ]
            (root / "events.jsonl").write_text(
                "".join(json.dumps(event) + "\n" for event in events),
                encoding="utf-8")
            state = {
                "school": {"current_student": {"sha256": student, "optimizer_step": 2}},
                "stagnation_session": {"quarantined": {"A.LINK": {"trigger_generation": 2}}},
                "mentor_epoch": {"active_roles": {},
                                 "championship_eligibility_after_step": -1},
            }
            (root / "states" / "0000002.json").write_text(
                json.dumps(state), encoding="utf-8")
            result = audit(root)
        self.assertEqual(result["classification_counts"]["NOT_MEASURED"], 0)
        self.assertEqual(
            result["classification_counts"]["ROLE_MINT_AFTER_HOLISTIC_RESET"], 1)
