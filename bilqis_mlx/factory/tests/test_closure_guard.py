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

    def test_aliased_release_dict_dispatch_cannot_hide(self):
        temp, root = self.fixture(
            "from x import MINIMAL_BOOLEAN_RELEASE as MODE\n"
            "def handler(): return 1\n"
            "HANDLERS = {MODE: handler}\n"
            "def choose(mode): return HANDLERS[mode]()\n")
        with temp:
            problems = inspect_factory_closure(root)
        self.assertTrue(any("GENERIC_RELEASE_IDENTITY_REFERENCE:MODE" in item
                            for item in problems))

    def test_capability_lookup_table_is_rejected_anywhere_in_generic_runtime(self):
        temp, root = self.fixture(
            "HANDLERS = {'B.OR': object()}\n",
            filename="presentation/view.py")
        with temp:
            problems = inspect_factory_closure(root)
        self.assertTrue(any("GENERIC_CAPABILITY_LITERAL:B.OR" in item
                            for item in problems))

    def test_concrete_provider_import_from_generic_runtime_is_rejected(self):
        temp, root = self.fixture(
            "from bilqis_mlx.minimal_grade_b import build_course\n"
            "def run():\n    return build_course()\n")
        with temp:
            problems = inspect_factory_closure(root)
        self.assertTrue(any("GENERIC_IMPORTS_CONCRETE_PROVIDER" in item
                            for item in problems))

    def test_generic_runtime_cannot_reconstruct_inventory_from_course(self):
        temp, root = self.fixture(
            "from bilqis_mlx.curriculum import Course\n"
            "def run(course: Course):\n"
            "    return tuple(cap.id for grade in course.grades for cap in grade.capabilities)\n",
            filename="runtime/runner.py")
        with temp:
            problems = inspect_factory_closure(root)
        self.assertTrue(any("GENERIC_RUNTIME_IMPORTS_COURSE" in item
                            for item in problems))
        self.assertTrue(any("GENERIC_RUNTIME_RECONSTRUCTS_COURSE" in item
                            for item in problems))

    def test_profile_specific_provider_is_rejected_at_provider_boundary(self):
        temp, root = self.fixture(
            "from bilqis_mlx.minimal_grade_b import draw_minimal\n",
            filename="source_adapters/school.py")
        with temp:
            problems = inspect_factory_closure(root)
        self.assertTrue(any("PROFILE_SPECIFIC_PROVIDER_IMPORT" in item
                            for item in problems))

    def test_data_driven_generic_runtime_passes(self):
        temp, root = self.fixture(
            "def run(plan):\n"
            "    return tuple(item.capability_id for item in plan.capabilities)\n")
        with temp:
            self.assertEqual(inspect_factory_closure(root), ())


if __name__ == "__main__":
    unittest.main()
