"""Rendering projection behavior from the original School50 suite."""
import io
from pathlib import Path
import tempfile
import unittest
from bilqis_mlx.presentation.dashboard import build, ingest
from bilqis_mlx.presentation.tests.school50.fixtures import exam


class RenderingTests(unittest.TestCase):
    def test_old_wide_three_pane_format_keeps_decisive_new_metrics_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "GRADE_A_TEACHER_VISIT_COMMITTED",
                           "generation": 2, "capability": "A.IDENTITY", "optimizer_step": 116776,
                           "teacher_policy": "policyabc0123",
                           "strategy": {"lr": .00013, "depth": 2, "contrast": 1},
                           "source_training_accuracy_before": .50,
                           "source_training_accuracy_after": 1.0,
                           "teacher_reward": .5, "loss": .123,
                           "gradient_norm": 1.2e-10, "next_phase": "MAIN"})
            for gen, score in ((3, 6), (6, 8)):
                ingest(board, exam("A", gen, "rubric-a",
                                   {"A.IDENTITY": (score, 12)}, step=116776 + gen))
            display = board.render(width=276, height=40)
            self.assertIn("LOSS", display)
            self.assertIn("GRAD", display)
            self.assertIn("WAS/CHP/NOW/ALL", display)
            self.assertIn("GOOD [GREW]", display)
            self.assertIn("67% [+17%]", display)
            self.assertNotIn("BRIDGE FAMILIES", display)
            self.assertIn("0.00", display)
