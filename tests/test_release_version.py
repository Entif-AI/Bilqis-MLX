"""Pure release metadata/commit contract, no GitHub mutations."""
import unittest

from scripts.release_version import changelog_section, conventional, VERSION


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


if __name__ == "__main__":
    unittest.main()
