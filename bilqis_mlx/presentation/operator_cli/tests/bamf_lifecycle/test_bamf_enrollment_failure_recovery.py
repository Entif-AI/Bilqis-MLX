"""C16.1a two-transaction enrollment failure and same-run recovery witness."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from bilqis_mlx.presentation.operator_cli.tests.bamf_lifecycle import test_bamf_atlas_release_create as atlas_create_tests


def _tree_bytes(root: Path):
    return tuple(
        (str(path.relative_to(root)), None if path.is_dir() else path.read_bytes())
        for path in sorted(root.rglob("*"))
    )


class BamfEnrollmentFailureRecoveryTests(unittest.TestCase):
    def test_failed_first_enrollment_recovers_same_genesis_without_republication(self):
        fixture = atlas_create_tests.BamfAtlasReleaseCreateTests(methodName="runTest")
        fixture.setUp()
        try:
            target = fixture.root / "failed-then-enrolled"
            manifest = fixture.manifest()
            request = fixture.matching_request()
            invalid_approval = replace(
                request.source_approval, signature_hex="0" * 128)
            invalid_scope = fixture.scope_file(
                replace(request, source_approval=invalid_approval), "invalid-scope.json")

            with fixture.c07_create_context(), patch(
                    "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                    side_effect=AssertionError("C16.1a enrollment is neural-inert")):
                code, output, errors = fixture.invoke([
                    "--human-run", "--model-topology", str(atlas_create_tests.TOPOLOGY),
                    "--admission-policy", "atlas-release",
                    "--atlas-release-manifest", str(manifest),
                    "--atlas-admission-scope", str(invalid_scope),
                    "--run-dir", str(target), *fixture.FOUNDATION_ARGS,
                ])
            self.assertEqual(code, 2)
            self.assertIn("BAMF_C09_SOURCE_SIGNATURE_INVALID", errors)
            self.assertEqual(
                tuple(record.get("event") for record in fixture.output_records(output)),
                ("BAMF_GENERATION_ACCEPTED",),
            )
            self.assertFalse(
                (target / "autonomy/atlas-admission/v2/current.json").exists())
            pointer_before = (target / "bamf-state.json").read_bytes()
            bundles_before = _tree_bytes(target / "bamf-bundles")
            acceptance_before = _tree_bytes(target / "bamf-acceptance")

            with fixture.c07_read_context(), patch(
                    "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                    side_effect=AssertionError("staged resume is neural-inert")):
                code, output, errors = fixture.invoke([
                    "--dry-run", "--resume", "--run-dir", str(target),
                ])
            self.assertEqual((code, errors), (0, ""))
            self.assertEqual(
                fixture.output_records(output)[-1]["admission_policy"], "staged")

            valid_scope = fixture.scope_file(request, "valid-scope.json")
            with fixture.c07_read_context(), patch(
                    "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                    side_effect=AssertionError("first enrollment is neural-inert")):
                code, output, errors = fixture.invoke([
                    "--human-run", "--resume", "--run-dir", str(target),
                    "--admission-policy", "atlas-release",
                    "--atlas-admission-scope", str(valid_scope),
                ])
            self.assertEqual((code, errors), (0, ""))
            report = fixture.output_records(output)[-1]
            self.assertEqual(report["result"], "ENROLLED")
            self.assertFalse(report["ready_for_training"])
            self.assertEqual(report["neural_updates"], 0)
            self.assertTrue(
                (target / "autonomy/atlas-admission/v2/current.json").is_file())
            self.assertEqual((target / "bamf-state.json").read_bytes(), pointer_before)
            self.assertEqual(_tree_bytes(target / "bamf-bundles"), bundles_before)
            self.assertEqual(_tree_bytes(target / "bamf-acceptance"), acceptance_before)
        finally:
            fixture.tearDown()


if __name__ == "__main__":
    unittest.main()
