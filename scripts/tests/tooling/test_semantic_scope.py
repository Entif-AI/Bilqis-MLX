import unittest

from scripts.testing.semantic_scope import is_semantic_path, semantic_changes


class SemanticScopeTests(unittest.TestCase):
    def test_semantic_owned_paths_are_selected(self):
        paths = (
            "bilqis_mlx/semantics/frame_codec.py",
            "lib/ithkuil/src/skos/notation.py",
            ".github/workflows/semantic-profile-full.yml",
        )

        self.assertEqual(semantic_changes(paths), paths)

    def test_test_infrastructure_and_general_ci_are_not_semantic(self):
        for path in (
            "package.json",
            "pyproject.toml",
            ".github/workflows/quality.yml",
            ".github/workflows/release.yml",
            "scripts/testing/differential_test_gate.py",
            "scripts/testing/dependency_map.py",
            "scripts/maintenance/release_version.py",
        ):
            with self.subTest(path=path):
                self.assertFalse(is_semantic_path(path))


if __name__ == "__main__":
    unittest.main()
