"""Differential ownership tests for scripts.quality.skos_test_selection."""
import tempfile
import unittest

from scripts.quality import skos_test_selection
from scripts.tests.skos.policy_fixture import SkosPolicyFixture


class SkosTestSelectionTests(SkosPolicyFixture, unittest.TestCase):
    def test_direct_source_change_selects_recursive_owner_plus_canaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.root(temporary)
            plan = skos_test_selection.classify_changes(
                root, ("lib/ithkuil/src/skos/notation.py",))
            self.assertEqual(plan.action, "DIFF")
            self.assertIn(
                "lib/ithkuil/tests/skos/core_identity/test_skos_notation.py",
                plan.tests)
            for canary in skos_test_selection.CANARY_TESTS:
                self.assertIn(canary, plan.tests)

    def test_fixture_change_selects_recursive_test_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.root(temporary)
            plan = skos_test_selection.classify_changes(
                root, ("lib/ithkuil/tests/fixtures/notation.json",))
            self.assertEqual(plan.action, "DIFF")
            self.assertIn(
                "lib/ithkuil/tests/skos/core_identity/test_skos_notation.py",
                plan.tests)

    def test_corpus_cross_cutting_and_split_policy_changes_require_full_suite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.root(temporary)
            for path in (
                "lib/ithkuil/_data/source.csv",
                "lib/ithkuil/src/skos/canonical.py",
                "scripts/skos_test_policy.py",
                "scripts/quality/skos_test_bundle.py",
                "scripts/quality/skos_test_selection.py",
                "docs/evidence/development/skos_test_bundle_v1.json",
            ):
                with self.subTest(path=path):
                    self.assertEqual(
                        skos_test_selection.classify_changes(root, (path,)).action,
                        "FULL")

    def test_unknown_bundle_change_fails_safe_to_full(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.root(temporary)
            (root / "lib/ithkuil/src/skos/new_surface.py").write_text("")
            plan = skos_test_selection.classify_changes(
                root, ("lib/ithkuil/src/skos/new_surface.py",))
            self.assertEqual(plan.action, "FULL")


if __name__ == "__main__":
    unittest.main()
