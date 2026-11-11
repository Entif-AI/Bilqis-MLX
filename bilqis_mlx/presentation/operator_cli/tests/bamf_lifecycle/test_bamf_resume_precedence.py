"""R19 command ownership and resume precedence witnesses for C16.1a."""
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from bilqis_mlx.presentation.operator_cli.tests.bamf_lifecycle import test_bamf_atlas_release_create as atlas_create_tests
from bilqis_mlx.presentation.operator_cli.tests.bamf_lifecycle import test_bamf_resume as resume_tests


class BamfResumePrecedenceTests(unittest.TestCase):
    def test_v2_foundation_flag_on_pointerless_resume_never_reaches_learner(self):
        fixture = resume_tests.BamfResumeTests(methodName="runTest")
        fixture.setUp()
        try:
            target = fixture.root / "missing-bamf"
            with patch(
                    "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                    side_effect=AssertionError("BAMF-v2 resume intent owns routing")):
                code, output, errors = fixture.invoke([
                    "--human-run", "--resume", "--run-dir", str(target),
                    "--run-id", "expected-v2-run",
                ])
            self.assertEqual((code, output), (2, ""))
            self.assertIn("BLOCKED", errors)
            self.assertFalse(target.exists())
        finally:
            fixture.tearDown()

    def test_enrollment_shape_and_request_precede_malformed_topology(self):
        fixture = atlas_create_tests.BamfAtlasReleaseCreateTests(methodName="runTest")
        fixture.setUp()
        try:
            target = fixture.root / "accepted-bamf"
            fixture.preflight(target)
            malformed_topology = fixture.root / "bad-topology.json"
            malformed_topology.write_text("not-json", encoding="utf-8")
            malformed_scope = fixture.root / "bad-scope.json"
            malformed_scope.write_text("not-json", encoding="utf-8")
            cases = (
                ([], "BAMF_ATLAS_V2_EXPLICIT_HUMAN_REQUEST_REQUIRED"),
                (["--human-run"], "BAMF_ATLAS_ENROLLMENT_REQUEST_INVALID"),
            )
            for authorization, reason in cases:
                with self.subTest(reason=reason), fixture.c07_read_context():
                    code, output, errors = fixture.invoke([
                        *authorization, "--resume", "--run-dir", str(target),
                        "--admission-policy", "atlas-release",
                        "--atlas-admission-scope", str(malformed_scope),
                        "--model-topology", str(malformed_topology),
                    ])
                self.assertEqual((code, output), (2, ""))
                self.assertIn(reason, errors)
        finally:
            fixture.tearDown()

    def test_saved_custody_and_identity_precede_malformed_topology(self):
        fixture = resume_tests.BamfResumeTests(methodName="runTest")
        fixture.setUp()
        try:
            target = fixture.root / "accepted-bamf"
            receipt = fixture.preflight(target)
            malformed_topology = fixture.root / "bad-topology.json"
            malformed_topology.write_text("not-json", encoding="utf-8")
            cases = (
                (["--run-id", "wrong-run"], "BAMF_OPERATOR_RESUME_RUN_ID_CONFLICT"),
                (["--run-id", receipt.run_identity.run_id, "--run-seed", "544"],
                 "BAMF_OPERATOR_RESUME_RUN_SEED_CONFLICT"),
                (["--run-id", "wrong-run", "--run-seed", "544",
                  "--learning-rate", "0.8", "--adam-beta1", "0.8",
                  "--adam-beta2", "0.8", "--adam-eps", "1e-5",
                  "--weight-decay", "0.8"], "BAMF_OPERATOR_RESUME_RUN_ID_CONFLICT"),
            )
            for overrides, reason in cases:
                with self.subTest(reason=reason), fixture.accepted_read_context():
                    code, output, errors = fixture.invoke([
                        "--dry-run", "--resume", "--run-dir", str(target),
                        *overrides, "--model-topology", str(malformed_topology),
                    ])
                self.assertEqual((code, output), (2, ""))
                self.assertIn(reason, errors)

            corrupt = fixture.root / "corrupt-bamf"
            corrupt.mkdir()
            (corrupt / "bamf-state.json").write_text("not-json", encoding="utf-8")
            code, output, errors = fixture.invoke([
                "--dry-run", "--resume", "--run-dir", str(corrupt),
                "--model-topology", str(malformed_topology),
            ])
            self.assertEqual((code, output), (2, ""))
            self.assertIn("BLOCKED", errors)
        finally:
            fixture.tearDown()


if __name__ == "__main__":
    unittest.main()
