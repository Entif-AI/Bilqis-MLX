"""Teacher integration contracts; original evidence and boundaries preserved."""
import unittest
from unittest.mock import patch
from tests.integration.teacher.fixtures import TeacherFixture


class CausalTeacherIntegrationTests(TeacherFixture, unittest.TestCase):
    def test_perfect_target_preflight_keeps_pending_provisionals_without_training(self):
        import mlx.core as mx

        previous = {"event": "PREVIOUS_PENDING_VISIT", "optimizer_step": 1}
        self.receipt["_pending_visit_events"] = [previous]
        original_bytes = (self.fixture.root / "state.json").read_bytes()
        original_step = int(self.fixture.optimizer.state["step"].item())
        original_lr = float(self.fixture.optimizer.learning_rate)

        def correctly_predict(_mx, _params, rows, _config, _ids):
            return {row["id"]: row["gold"] for row in rows}

        with patch('bilqis_mlx.learning.student_ops._predictions', side_effect=correctly_predict), \
                patch('bilqis_mlx.learning.student_ops._train_step', side_effect=AssertionError(
                    "PERFECT_TARGET_MUST_NOT_OPTIMIZE")), \
                patch('bilqis_mlx.runtime.checkpoints._persist', side_effect=AssertionError(
                    "PENDING_STUDENT_MUST_NOT_PERSIST")):
            updated = self.visit()

        mx.eval(self.fixture.optimizer.state)
        self.assertEqual(int(self.fixture.optimizer.state["step"].item()), original_step)
        self.assertEqual(float(self.fixture.optimizer.learning_rate), original_lr)
        self.assertEqual((self.fixture.root / "state.json").read_bytes(), original_bytes)
        self.assertEqual(updated["_pending_visit_events"][0], previous)
        skipped = updated["_pending_visit_events"][1]
        self.assertEqual(skipped["event"], "SCHOOL_PERFECT_TARGET_VISIT_SKIPPED")
        self.assertEqual(skipped["retained_optimizer_updates"], 0)
        self.assertEqual(updated["school"]["current_student"],
                         self.receipt["school"]["current_student"])
