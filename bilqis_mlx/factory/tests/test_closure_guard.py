from pathlib import Path
import tempfile
import unittest

from scripts.check_factory_closure import inspect_factory_closure


class FactoryClosureGuardTests(unittest.TestCase):
    def fixture(self, source: str, *, filename="trainer.py"):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "bilqis_mlx/factory").mkdir(parents=True)
        (root / "bilqis_mlx/factory/__init__.py").write_text("")
        path = root / "bilqis_mlx" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
        return temp, root

    def test_release_identity_dispatch_is_rejected_even_without_grade_letter(self):
        temp, root = self.fixture(
            "from x import MINIMAL_BOOLEAN_RELEASE\n"
            "def choose(mode):\n"
            "    if mode == MINIMAL_BOOLEAN_RELEASE:\n"
            "        return 1\n")
        with temp:
            problems = inspect_factory_closure(root)
        self.assertTrue(any("GENERIC_RELEASE_IDENTITY_DISPATCH" in item
                            for item in problems))

    def test_capability_roster_special_case_is_rejected(self):
        temp, root = self.fixture(
            "def valid(caps):\n"
            "    compact = tuple(caps) == ('B.AND', 'B.IFF')\n"
            "    return compact\n",
            filename="curriculum/model.py")
        with temp:
            problems = inspect_factory_closure(root)
        self.assertTrue(any("GENERIC_CAPABILITY_LITERAL:B.AND" in item
                            for item in problems))
        self.assertTrue(any("GENERIC_CAPABILITY_LITERAL:B.IFF" in item
                            for item in problems))

    def test_concrete_provider_import_from_generic_runtime_is_rejected(self):
        temp, root = self.fixture(
            "from bilqis_mlx.minimal_grade_b import build_course\n"
            "def run():\n    return build_course()\n")
        with temp:
            problems = inspect_factory_closure(root)
        self.assertTrue(any("GENERIC_IMPORTS_CONCRETE_PROVIDER" in item
                            for item in problems))

    def test_data_driven_generic_runtime_passes(self):
        temp, root = self.fixture(
            "def run(plan):\n"
            "    return tuple(item.capability_id for item in plan.capabilities)\n")
        with temp:
            self.assertEqual(inspect_factory_closure(root), ())


if __name__ == "__main__":
    unittest.main()
