"""C16.1a historical-v1 accepted-run resume compatibility witness."""
from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch
import unittest

from bilqis_mlx.presentation.operator_cli.tests.bamf_lifecycle import test_bamf_atlas_release_create as atlas_create_tests
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.atlas_admission import persist_accepted_atlas_lease
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation_authority
from bilqis_mlx.runtime.jit_adoption import _accepted_lease_run_identity
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import _lease


class BamfHistoricalV1ResumeTests(unittest.TestCase):
    def test_historical_v1_no_scope_resume_is_authenticated_and_neural_inert(self):
        fixture = atlas_create_tests.BamfAtlasReleaseCreateTests(methodName="runTest")
        fixture.setUp()
        try:
            target = fixture.root / "historical-v1"
            manifest = fixture.manifest()
            with fixture.c07_create_context():
                code, _output, errors = fixture.invoke([
                    "--human-run", "--model-topology", str(atlas_create_tests.TOPOLOGY),
                    "--atlas-release-manifest", str(manifest),
                    "--run-dir", str(target), *fixture.FOUNDATION_ARGS,
                ])
            self.assertEqual((code, errors), (0, ""))
            with fixture.c07_read_context():
                student, _ = load_bamf_generation_authority(target / "bamf-state.json")
                lease = replace(
                    _lease(), run_identity=_accepted_lease_run_identity(student.run_identity))
                host = AcceptedRuntimeHost(target)
                persist_accepted_atlas_lease(
                    target, lease, source_authority=host.source_authority())

            for policy_args in ((), ("--admission-policy", "atlas-release")):
                with self.subTest(policy_args=policy_args), fixture.c07_read_context(), patch(
                        "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                        side_effect=AssertionError("historical v1 resume is neural-inert")):
                    code, output, errors = fixture.invoke([
                        "--dry-run", "--resume", "--run-dir", str(target), *policy_args,
                    ])
                self.assertEqual((code, errors), (0, ""))
                report = fixture.output_records(output)[-1]
                self.assertEqual(report["admission_policy"], "atlas-release")
                self.assertFalse(report["ready_for_training"])
                self.assertEqual(report["neural_updates"], 0)

            with fixture.c07_read_context(), patch(
                    "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                    side_effect=AssertionError("policy conflict must precede learner")):
                code, output, errors = fixture.invoke([
                    "--dry-run", "--resume", "--run-dir", str(target),
                    "--admission-policy", "staged",
                ])
            self.assertEqual((code, output), (2, ""))
            self.assertIn("BAMF_OPERATOR_RESUME_ADMISSION_POLICY_CONFLICT", errors)
        finally:
            fixture.tearDown()


if __name__ == "__main__":
    unittest.main()
