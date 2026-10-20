import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from bilqis_mlx import trainer


class ChampionshipHistoryTests(TestCase):
    def test_first_settlement_wins_and_duplicate_history_is_not_replayed(self):
        incumbent = "a" * 64
        challenger = "b" * 64
        student = "c" * 64
        first = {
            "capability": "A.IDENTITY", "decision": "TITLE_DEFENDED",
            "incumbent_sha256": incumbent, "challenger_sha256": challenger,
            "winner_sha256": incumbent,
        }
        duplicate = {**first, "decision": "TITLE_WON", "winner_sha256": challenger}
        with TemporaryDirectory() as temp:
            root = Path(temp)
            events = [
                {"event": "SCHOOL_TEACHER_VISIT_COMMITTED", "generation": 1,
                 "grade": "B", "optimizer_step": 20, "retained_optimizer_updates": 16,
                 "recovered_at_student_sha256": student},
                {"event": "SCHOOL_LIVE_EXAM_COMMITTED", "generation": 2,
                 "championship_epoch": {"cross_origin_decisions": [first]}},
                {"event": "SCHOOL_LIVE_EXAM_COMMITTED", "generation": 3,
                 "championship_epoch": {"cross_origin_decisions": [duplicate]}},
            ]
            (root / "events.jsonl").write_text(
                "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
            origins, ambiguous, settled, duplicates = (
                trainer._historical_championship_authority(root))
        self.assertEqual(origins, {student: "B"})
        self.assertEqual(ambiguous, {})
        self.assertEqual(duplicates, 1)
        key = trainer._championship_pair_key("A.IDENTITY", challenger, incumbent)
        self.assertEqual(settled[key]["decision"], "TITLE_DEFENDED")
        self.assertEqual(settled[key]["winner_sha256"], incumbent)
        self.assertEqual(settled[key]["source_generation"], 2)

    def test_checkpoint_origin_is_fail_closed_when_retained_history_spans_grades(self):
        student = "c" * 64
        with TemporaryDirectory() as temp:
            root = Path(temp)
            events = [
                {"event": "SCHOOL_TEACHER_VISIT_COMMITTED", "generation": 1,
                 "grade": grade, "optimizer_step": step, "retained_optimizer_updates": 16,
                 "recovered_at_student_sha256": student}
                for grade, step in (("A", 20), ("B", 36))
            ]
            (root / "events.jsonl").write_text(
                "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
            origins, ambiguous, settled, duplicates = (
                trainer._historical_championship_authority(root))
        self.assertNotIn(student, origins)
        self.assertEqual(ambiguous[student], ["A", "B"])
        self.assertEqual(settled, {})
        self.assertEqual(duplicates, 0)
