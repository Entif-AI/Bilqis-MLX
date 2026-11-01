"""Candidates projection behavior from the original School50 suite."""
import io
from pathlib import Path
import tempfile
import unittest
from bilqis_mlx.presentation.dashboard import build, ingest


class CandidatesTests(unittest.TestCase):
    def test_real_source_visit_shows_strategy_loss_reward_and_no_fake_sentinel(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "GRADE_A_TEACHER_VISIT_COMMITTED",
                           "generation": 2, "capability": "A.IDENTITY",
                           "optimizer_step": 116776, "teacher_policy": "c0d92a80eada",
                           "strategy": {"lr": .00013, "depth": 1, "contrast": 1.,
                                        "old": 16, "preview": 4, "distill": .15},
                           "unavailable_teacher_dimensions": ["old", "preview", "distill"],
                           "source_training_accuracy_before": 7/12,
                           "source_training_accuracy_after": 11/12,
                           "teacher_reward": 4/12, "gradient_norm": 1.26,
                           "loss": .467, "next_phase": "MAIN",
                           "teacher_decision": {
                               "warning_signals": ["DISCONNECTED_PREREQUISITES"],
                               "selected": {"exam_mistake_replay": 2,
                                            "champion_priority": 1},
                           }})
            candidate = board.rows["CANDIDATES"][-1]
            teacher = board.rows["SOUP & TEACHER"][-1]
            self.assertEqual(candidate["capability"], "A.IDENTITY")
            self.assertIn("58.3", candidate["train"])
            self.assertIn("91.7", candidate["train"])
            self.assertEqual(candidate["reward"], "+0.333")
            self.assertEqual(teacher["old"], "OFF")
            self.assertEqual(teacher["preview"], "OFF")
            self.assertEqual(teacher["distill"], "OFF")
            self.assertIn("0.467", candidate["loss"])
            self.assertIn("1.26", candidate["gradient"])
            self.assertIn("S4", candidate["decision"])
            self.assertIn("miss 2", candidate["decision"])
            self.assertIn("champ 1", candidate["decision"])
            self.assertFalse(board.rows["SENTINEL & RETENTION"])
            self.assertTrue(any("NOT MEASURED" in x["detail"]
                                for x in board.rows["SYSTEM & QUALIFICATION"]))
