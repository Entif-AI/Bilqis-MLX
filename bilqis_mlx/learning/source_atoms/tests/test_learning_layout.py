"""Physical owner directories must preserve lazy canonical import identities."""
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest import TestCase


class LearningLayoutTests(TestCase):
    def test_every_relocated_owner_resolves_once_under_its_existing_module_name(self):
        import bilqis_mlx.learning as learning

        root = Path(learning.__file__).parent
        observed = set()
        for directory in learning._SOURCE_DIRECTORIES:
            for path in sorted((root / directory).glob("*.py")):
                self.assertNotIn(path.stem, observed)
                observed.add(path.stem)
                name = "bilqis_mlx.learning." + path.stem
                self.assertEqual(Path(importlib.util.find_spec(name).origin), path)
                self.assertFalse((root / path.name).exists())
        self.assertEqual(len(observed), 31)

    def test_importing_learning_does_not_eagerly_load_neural_or_teacher_owners(self):
        command = (
            "import json,sys; import bilqis_mlx.learning; "
            "print(json.dumps(sorted(n for n in sys.modules "
            "if n == 'mlx' or n.startswith('bilqis_mlx.learning.'))))")
        result = subprocess.run([sys.executable, "-B", "-c", command],
                                check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout), [])

    def test_existing_helper_imports_still_resolve_to_their_owner_tests(self):
        module = importlib.import_module("bilqis_mlx.learning.tests.test_teacher_votes")
        self.assertEqual(Path(module.__file__).parent.name, "tests")
        self.assertEqual(Path(module.__file__).parent.parent.name, "_teaching")
