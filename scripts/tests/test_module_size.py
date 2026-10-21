"""Size gates preserve inherited debt while refusing new growth."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("check_module_size", Path(__file__).parents[1] / "check_module_size.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class ModuleSizeTests(unittest.TestCase):
    def test_new_and_worsened_hard_violations_fail(self):
        self.assertEqual(check.violations({"a.py": 1200, "b.py::f": 300}, {}),
                         ["a.py", "b.py::f"])
        self.assertEqual(check.violations({"a.py": 1201}, {"a.py": 1200}), ["a.py"])

    def test_unchanged_reduced_and_review_only_debt_passes(self):
        self.assertEqual(check.violations({"a.py": 1200, "b.py": 810, "c.py::f": 299},
                                         {"a.py": 1201}), [])

    def test_inventory_excludes_fixtures_and_counts_nested_functions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            production = root / "bilqis_mlx"
            production.mkdir()
            (production / "module.py").write_text("def outer():\n    def inner():\n        return 1\n    return inner()\n")
            (production / "tests").mkdir()
            (production / "tests/test_hidden.py").write_text("invalid Python")
            found = check.inventory(root)
            self.assertEqual(found, {"bilqis_mlx/module.py": 4,
                "bilqis_mlx/module.py::outer": 4, "bilqis_mlx/module.py::outer.inner": 2})
