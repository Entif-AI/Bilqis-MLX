"""One cohesive R19 disposable first-start witness for C16.1a."""
from dataclasses import replace
from unittest.mock import patch
import unittest

from bilqis_mlx.learning.tests.teaching import test_c03_parent_acceptance as c03_tests
from bilqis_mlx.presentation.operator_cli.tests import test_bamf_atlas_release_create as atlas_create_tests
from bilqis_mlx.runtime.atlas_admission import advance_atlas_frontier
from bilqis_mlx.runtime.bamf_bundle import (
    load_bamf_generation_authority, record_bamf_rejection,
)
from bilqis_mlx.runtime.capability_retention import retain_candidate
from bilqis_mlx.runtime.tests.admission.atlas import test_atlas_admission_policy as atlas_policy_tests
from bilqis_mlx.runtime.tests.capability.capability_retention_helpers import (
    CANDIDATE, PARENT, _evidence,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle import test_cold_resume_continuation as cold_resume_tests
from bilqis_mlx.runtime.tests.capability import test_capability_authority as capability_authority_tests


class BamfFirstStartWitnessTests(unittest.TestCase):
    def test_command_created_genesis_composes_required_developmental_witnesses(self):
        fixture = atlas_create_tests.BamfAtlasReleaseCreateTests(methodName="runTest")
        fixture.setUp()
        try:
            target = fixture.root / "cohesive-first-start"
            manifest = fixture.manifest()
            with fixture.c07_create_context(), patch(
                    "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                    side_effect=AssertionError("C16.1a must remain neural-inert")):
                code, output, errors = fixture.invoke([
                    "--human-run", "--model-topology", str(atlas_create_tests.TOPOLOGY),
                    "--atlas-release-manifest", str(manifest),
                    "--run-dir", str(target), *fixture.FOUNDATION_ARGS,
                ])
            self.assertEqual((code, errors), (0, ""))
            report = fixture.output_records(output)[-1]
            self.assertEqual(report["result"], "CREATED")
            self.assertFalse(report["ready_for_training"])
            self.assertEqual(report["neural_updates"], 0)
            with fixture.c07_read_context():
                student, _ = load_bamf_generation_authority(target / "bamf-state.json")
            self.assertEqual(student.generation, 0)
            self.assertEqual(student.retained_state.optimizer_step, 0)

            pointer_before = (target / "bamf-state.json").read_bytes()
            record_bamf_rejection(
                target, student, {"reason": "first_start_disposable_rejection"})
            with fixture.c07_read_context():
                after_rejection, _ = load_bamf_generation_authority(
                    target / "bamf-state.json")
            self.assertEqual((target / "bamf-state.json").read_bytes(), pointer_before)
            self.assertEqual(after_rejection.retained_state.optimizer_step, 0)

            grade = c03_tests.C03ParentAcceptanceTests(methodName="runTest")
            grade.setUp()
            try:
                left, right = grade._grade_result("A"), grade._grade_result("Z")
            finally:
                grade.doCleanups()
            semantic_keys = tuple(key for key in left if not key.startswith("diagnostic_"))
            self.assertEqual(
                {key: left[key] for key in semantic_keys},
                {key: right[key] for key in semantic_keys})

            authority = capability_authority_tests.CapabilityAuthorityTests(methodName="runTest")
            release, checkpoint, admission = capability_authority_tests._release(
                edge=True, labels=("A", "Z"))
            blocked = authority.gate(
                release, checkpoint, admission,
                thresholds=(capability_authority_tests.PrerequisiteThreshold(
                    "foundation", 1, 1),), proof=False)
            self.assertEqual(blocked.reason, "PREREQUISITE_EVIDENCE_INSUFFICIENT")

            rights = atlas_policy_tests.AtlasAdmissionPolicyTests(methodName="runTest")
            rights.setUp()
            try:
                held = atlas_policy_tests._signed(replace(
                    rights.lease.source_approval, rights_compatible=False))
                result = advance_atlas_frontier(
                    replace(rights.context, source_approval=held),
                    rights.envelope, rights.lease)
                self.assertEqual(result.reason, "SOURCE_OR_RIGHTS_HELD")
                self.assertFalse(result.state_adopted)
                self.assertEqual(rights.native.checkpoint.optimizer_step, 0)
            finally:
                rights.doCleanups()

            evidence = _evidence()
            retained = retain_candidate(PARENT, CANDIDATE, evidence)
            self.assertEqual(retained.status, "ELIGIBLE")
            self.assertEqual(evidence.target.candidate.score("target"), (3, 3))

            cold = cold_resume_tests.BamfColdResumeContinuationTests(methodName="runTest")
            cold.setUp()
            try:
                cold.test_factory_teacher_source_next_visit_survives_cold_owner_readback()
            finally:
                cold.tearDown()

            self.assertEqual((target / "bamf-state.json").read_bytes(), pointer_before)
            self.assertEqual(after_rejection.retained_state.optimizer_step, 0)
        finally:
            fixture.tearDown()


if __name__ == "__main__":
    unittest.main()
