"""Pure release metadata/commit contract, no GitHub mutations."""
import json
from pathlib import Path
import tempfile
import tomllib
import unittest

from bilqis_mlx import __version__
from scripts.release_version import changelog_section, conventional, version_contract, VERSION


class ReleaseVersionTests(unittest.TestCase):
    def test_conventional_commits(self):
        for subject in ("feat(training): consolidate custody", "fix: repair Finder metadata",
                        "chore(release)!: update contracts", "docs: update operator instructions"):
            self.assertTrue(conventional(subject), subject)
        for subject in ("add some stuff", "Merge pull request #5", "feat: ", "feat(scope): hi"):
            self.assertFalse(conventional(subject), subject)

    def test_semver_and_versioned_changelog(self):
        self.assertTrue(VERSION.fullmatch("0.2.0"))
        self.assertFalse(VERSION.fullmatch("01.2.0"))
        example = "# Changes\n\n## [0.2.0] - 2026-10-17\n\n### Added\n- Source custody\n\n## [0.1.0] - 2026-10-15\n### Added\n- Old\n"
        self.assertIn("Source custody", changelog_section(example, "0.2.0"))
        self.assertNotIn("Old", changelog_section(example, "0.2.0"))
        with self.assertRaisesRegex(ValueError, "CHANGELOG_VERSION_MISSING"):
            changelog_section(example, "0.3.0")

    def test_python_and_project_manifests_share_one_version(self):
        root = Path(__file__).resolve().parents[2]
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        package_lock = json.loads(
            (root / "package-lock.json").read_text(encoding="utf-8"))
        release_manifest = json.loads(
            (root / ".release-please-manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(__version__, project["project"]["version"])
        self.assertEqual(__version__, package["version"])
        self.assertEqual(__version__, package_lock["version"])
        self.assertEqual(__version__, package_lock["packages"][""]["version"])
        self.assertEqual(__version__, release_manifest["."])

    def test_release_please_controls_every_version_surface(self):
        root = Path(__file__).resolve().parents[2]
        config = json.loads(
            (root / "release-please-config.json").read_text(encoding="utf-8"))
        self.assertFalse(config["include-component-in-tag"])
        self.assertTrue(config["include-v-in-tag"])
        package = config["packages"]["."]
        self.assertEqual(package["release-type"], "node")
        extra = {(item["type"], item["path"]) for item in package["extra-files"]}
        self.assertIn(("toml", "pyproject.toml"), extra)
        self.assertIn(("generic", "bilqis_mlx/__init__.py"), extra)

    def test_release_contract_rejects_stale_python_package_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bilqis_mlx").mkdir()
            (root / "pyproject.toml").write_text(
                '[project]\nname = "x"\nversion = "0.3.0"\n', encoding="utf-8")
            (root / "package.json").write_text(
                json.dumps({"version": "0.3.0"}), encoding="utf-8")
            (root / "package-lock.json").write_text(
                json.dumps({
                    "version": "0.3.0",
                    "packages": {"": {"version": "0.3.0"}},
                }), encoding="utf-8")
            (root / "bilqis_mlx" / "__init__.py").write_text(
                '__version__ = "0.2.0"  # x-release-please-version\n', encoding="utf-8")
            (root / ".release-please-manifest.json").write_text(
                json.dumps({".": "0.3.0"}), encoding="utf-8")
            (root / "CHANGELOG.md").write_text(
                '# Changelog\n\n## [0.3.0] - 2026-10-25\n\n### Added\n- x\n',
                encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "SEMVER_OR_MANIFEST_MISMATCH"):
                version_contract(root)


if __name__ == "__main__":
    unittest.main()
