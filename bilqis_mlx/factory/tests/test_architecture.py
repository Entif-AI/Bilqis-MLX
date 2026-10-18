from pathlib import Path
import tempfile
import unittest

from scripts.check_factory_architecture import inspect_factory_architecture


ROOT = Path(__file__).resolve().parents[3]


class FactoryArchitectureTests(unittest.TestCase):
    def test_current_repository_has_no_factory_bypass(self):
        self.assertEqual(inspect_factory_architecture(ROOT), ())

    def test_future_grade_runtime_fork_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bilqis_mlx/factory").mkdir(parents=True)
            (root / "bilqis_mlx/factory/__init__.py").write_text("")
            (root / "bilqis_mlx/live_grade_d.py").write_text("GRADE = 'D'\n")
            (root / "bilqis_mlx/trainer.py").write_text(
                "def operate():\n _require_factory_admission()\n"
                "def _activate_next_admitted_grade():\n _factory_admission()\n")
            (root / "bilqis_mlx/grade_transition.py").write_text(
                "def activate_numeric_grade():\n _factory_admission()\n")
            (root / "bilqis_mlx/numeric_staircase.py").write_text(
                "def _rebind():\n _factory_admission()\n")
            problems = inspect_factory_architecture(root)
            self.assertTrue(any("FUTURE_GRADE_RUNTIME_FORK:D" in item for item in problems))

    def test_generic_grade_letter_dispatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bilqis_mlx/factory").mkdir(parents=True)
            (root / "bilqis_mlx/factory/__init__.py").write_text(
                "def route(grade):\n    if grade == 'B':\n        return 1\n")
            (root / "bilqis_mlx/live_curriculum.py").write_text("")
            (root / "bilqis_mlx/trainer.py").write_text(
                "def operate():\n _require_factory_admission()\n"
                "def _activate_next_admitted_grade():\n _factory_admission()\n")
            (root / "bilqis_mlx/grade_transition.py").write_text(
                "def activate_numeric_grade():\n _factory_admission()\n")
            (root / "bilqis_mlx/numeric_staircase.py").write_text(
                "def _rebind():\n _factory_admission()\n")
            problems = inspect_factory_architecture(root)
            self.assertTrue(any("GENERIC_GRADE_IDENTITY_DISPATCH B" in item for item in problems))

    def test_training_entrypoint_without_release_gate_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bilqis_mlx/factory").mkdir(parents=True)
            (root / "bilqis_mlx/factory/__init__.py").write_text("")
            (root / "bilqis_mlx/live_curriculum.py").write_text("")
            (root / "bilqis_mlx/trainer.py").write_text(
                "def operate():\n pass\n"
                "def _activate_next_admitted_grade():\n _factory_admission()\n")
            (root / "bilqis_mlx/grade_transition.py").write_text(
                "def activate_numeric_grade():\n _factory_admission()\n")
            (root / "bilqis_mlx/numeric_staircase.py").write_text(
                "def _rebind():\n _factory_admission()\n")
            problems = inspect_factory_architecture(root)
            self.assertIn(
                "bilqis_mlx/trainer.py OPERATE_BYPASSES_FACTORY_RELEASE",
                problems)


if __name__ == "__main__":
    unittest.main()
