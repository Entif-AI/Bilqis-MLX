"""#542 BAMF resume validation contract."""
import json

from .resume.resume_test_support import ResumeCase, tree_snapshot


class BamfResumeTests(ResumeCase):
    def test_resume_without_overrides_reads_saved_b13_identity_without_writes(self):
            target = self.root / "accepted-bamf"
            receipt = self.preflight(target)
            before = tree_snapshot(target)
            with self.accepted_read_context(receipt.atlas_artifact):
                code, output, errors = self.invoke([
                    "--dry-run", "--resume", "--run-dir", str(target),
                ])
            self.assertEqual((code, errors), (0, ""))
            report = json.loads(output)
            self.assertEqual(report["result"], "READY_TO_RESUME")
            self.assertEqual(report["admission_policy"], "staged")
            self.assertEqual(report["run_seed"], receipt.run_identity.run_seed)
            self.assertEqual(
                report["model_topology"]["digest"],
                receipt.run_identity.initial_topology_digest,
            )
            self.assertEqual(
                report["atlas_release_manifest"]["sha256"],
                receipt.atlas_artifact.bundle_id,
            )
            self.assertEqual(tree_snapshot(target), before)

    def test_resume_explicit_atlas_release_conflict_rejects_before_writes(self):
            target = self.root / "accepted-bamf"
            self.preflight(target)
            before = tree_snapshot(target)
            for policy_args in (("--admission-policy", "atlas-release"),
                                ("--admission-policy=atlas-release",)):
                with self.subTest(policy_args=policy_args), self.accepted_read_context():
                    code, output, errors = self.invoke([
                        "--dry-run", "--resume", "--run-dir", str(target), *policy_args,
                    ])
                self.assertEqual((code, output), (2, ""))
                self.assertIn("BAMF_ATLAS_EXPLICIT_SCOPE_FILE_REQUIRED", errors)
                self.assertEqual(tree_snapshot(target), before)

    def test_resume_rejects_atlas_scope_override_before_writes(self):
            target = self.root / "accepted-bamf"
            self.preflight(target)
            before = tree_snapshot(target)
            scope = self.root / "scope.json"
            scope.write_text("{}", encoding="utf-8")
            with self.accepted_read_context():
                code, output, errors = self.invoke([
                    "--dry-run", "--resume", "--run-dir", str(target),
                    "--atlas-admission-scope", str(scope),
                ])
            self.assertEqual((code, output), (2, ""))
            self.assertIn("BAMF_ATLAS_SCOPE_REQUIRES_EXPLICIT_POLICY", errors)
            self.assertEqual(tree_snapshot(target), before)

    def test_resume_scope_requires_human_authorization_before_request_parse(self):
            target = self.root / "accepted-bamf"
            self.preflight(target)
            before = tree_snapshot(target)
            scope = self.root / "malformed-scope.json"
            scope.write_text("not-json", encoding="utf-8")
            with self.accepted_read_context():
                code, output, errors = self.invoke([
                    "--dry-run", "--resume", "--run-dir", str(target),
                    "--admission-policy", "atlas-release",
                    "--atlas-admission-scope", str(scope),
                ])
            self.assertEqual((code, output), (2, ""))
            self.assertIn("BAMF_ATLAS_V2_EXPLICIT_HUMAN_REQUEST_REQUIRED", errors)
            self.assertNotIn("BAMF_ATLAS_ENROLLMENT_REQUEST_INVALID", errors)
            self.assertEqual(tree_snapshot(target), before)
