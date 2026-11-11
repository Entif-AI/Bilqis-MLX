"""One cohesive R19 disposable first-start witness for C16.1a."""
from dataclasses import asdict, replace
import json
import random
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from bilqis_mlx.compatibility import historical_teacher_policy
from bilqis_mlx.curriculum.scheduler import start_new
from bilqis_mlx.curriculum.tests.test_school import cp
from bilqis_mlx.curriculum.tests.test_staged_school import staged_course
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.learning_experiment import Settings, earlier_grade_capabilities
from bilqis_mlx.learning.tests.teaching import test_c03_parent_acceptance as c03_tests
from bilqis_mlx.presentation.operator_cli.tests.bamf_lifecycle import test_bamf_atlas_release_create as atlas_create_tests
from bilqis_mlx.runtime.accepted_teacher_custody import select_accepted_teacher_visit
from bilqis_mlx.runtime.atlas_admission import advance_atlas_frontier
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation_authority, record_bamf_rejection
from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import _reset_execution_cache_owner_for_tests
from bilqis_mlx.runtime.bamf_first_student import load_bamf_foundation_dashboard_projection
from bilqis_mlx.runtime.capability_retention import retain_candidate
from bilqis_mlx.runtime.tests.admission.atlas import test_atlas_admission_policy as atlas_policy_tests
from bilqis_mlx.runtime.tests.capability.capability_retention_helpers import CANDIDATE, PARENT, _evidence
from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import retained_digest
from bilqis_mlx.runtime.tests.custody.bamf_bundle.teacher_custody_fixtures import adaptation, selection_teacher
from bilqis_mlx.runtime.tests.capability import test_capability_authority as capability_authority_tests
from bilqis_mlx.trainer import _state_from_json


class BamfFirstStartWitnessTests(unittest.TestCase):
    def _create_first_start(self, fixture):
        target = fixture.root / "cohesive-first-start"
        with fixture.c07_create_context(), patch(
                "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                side_effect=AssertionError("C16.1a must remain neural-inert")):
            code, output, errors = fixture.invoke([
                "--human-run", "--model-topology", str(atlas_create_tests.TOPOLOGY),
                "--atlas-release-manifest", str(fixture.manifest()),
                "--run-dir", str(target), *fixture.FOUNDATION_ARGS,
            ])
        self.assertEqual((code, errors), (0, ""))
        report = fixture.output_records(output)[-1]
        self.assertEqual(report["result"], "CREATED")
        self.assertFalse(report["ready_for_training"])
        self.assertEqual(report["neural_updates"], 0)
        with fixture.c07_read_context():
            student, _ = load_bamf_generation_authority(target / "bamf-state.json")
            dashboard = load_bamf_foundation_dashboard_projection(target)
        self.assertEqual((student.generation, student.retained_state.optimizer_step), (0, 0))
        self.assertEqual(dashboard.stage, "READY_FOR_HUMAN_START")
        return target, student

    def _select_visit(self, fixture, target, school):
        with fixture.c07_read_context():
            visit, _policy, _metadata = select_accepted_teacher_visit(
                target, historical_teacher_policy, school, random.Random(17),
                Settings(), "factory/7", {}, "A", capability_id="C.ADD",
                total_capabilities=20,
                legacy_receipt={"teacher": selection_teacher()},
                adaptation=adaptation(), prior_region="legacy-region")
        return visit

    def _assert_rejection_preserves_parent(self, fixture, target, student):
        pointer_before = (target / "bamf-state.json").read_bytes()
        bundle = target / json.loads(pointer_before)["bundle"]
        parent_bytes_before = tuple(
            (str(path.relative_to(bundle)), path.read_bytes())
            for path in sorted(bundle.rglob("*")) if path.is_file())
        optimizer_before = retained_digest(student.retained_state)
        record_bamf_rejection(target, student, {"reason": "first_start_disposable_rejection"})
        with fixture.c07_read_context():
            after, _ = load_bamf_generation_authority(target / "bamf-state.json")
        self.assertEqual((target / "bamf-state.json").read_bytes(), pointer_before)
        self.assertEqual(after.retained_state.optimizer_step, 0)
        self.assertEqual(tuple(
            (str(path.relative_to(bundle)), path.read_bytes())
            for path in sorted(bundle.rglob("*")) if path.is_file()), parent_bytes_before)
        return pointer_before, optimizer_before

    def _assert_grade_and_debt_symmetry(self):
        grade = c03_tests.C03ParentAcceptanceTests(methodName="runTest")
        grade.setUp()
        try:
            left, right = grade._grade_result("A"), grade._grade_result("Z")
        finally:
            grade.doCleanups()
        keys = tuple(key for key in left if not key.startswith("diagnostic_"))
        self.assertEqual({key: left[key] for key in keys}, {key: right[key] for key in keys})
        authority = capability_authority_tests.CapabilityAuthorityTests(methodName="runTest")
        results = []
        for labels in (("A", "Z"), ("Z", "A")):
            release, checkpoint, admission = capability_authority_tests._release(edge=True, labels=labels)
            blocked = authority.gate(
                release, checkpoint, admission,
                thresholds=(capability_authority_tests.PrerequisiteThreshold("foundation", 1, 1),),
                proof=False)
            program = c03_tests.schedule_program_from_executable_release(release)
            debt = earlier_grade_capabilities(program, (), "target", carried_mastery_debt=("foundation",))
            results.append((blocked.reason, debt))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], "PREREQUISITE_EVIDENCE_INSUFFICIENT")

    def _assert_rights_hold(self):
        rights = atlas_policy_tests.AtlasAdmissionPolicyTests(methodName="runTest")
        rights.setUp()
        try:
            held = atlas_policy_tests._signed(replace(
                rights.lease.source_approval, rights_compatible=False))
            result = advance_atlas_frontier(
                replace(rights.context, source_approval=held), rights.envelope, rights.lease)
            self.assertEqual(result.reason, "SOURCE_OR_RIGHTS_HELD")
            self.assertFalse(result.state_adopted)
            self.assertEqual(rights.native.checkpoint.optimizer_step, 0)
        finally:
            rights.doCleanups()

    def _assert_positive_developmental_evidence(self):
        evidence = _evidence()
        retained = retain_candidate(PARENT, CANDIDATE, evidence)
        self.assertEqual(retained.status, "ELIGIBLE")
        self.assertEqual(evidence.target.parent.score("target"), (0, 3))
        self.assertEqual(evidence.target.candidate.score("target"), (3, 3))
        cohort = evidence.target.candidate.cohort
        self.assertEqual((cohort.kind.value, cohort.evidence_stage.value),
                         ("FRESH_TARGET", "STRICT_GENERALIZATION"))
        observed = ("ACQUIRED_TAUGHT_BEHAVIOR", cohort.kind.value)
        self.assertEqual(observed, ("ACQUIRED_TAUGHT_BEHAVIOR", "FRESH_TARGET"))

    def _assert_legacy_b_cadence_rejected(self):
        course = staged_course()
        legacy = asdict(start_new(course, cp("bamf-first-start")))
        legacy["nongating_b_visits"] = legacy["bounded_debt_visits"] + 1
        legacy["non_b_training_turns_since_b_run"] = legacy["priority_visits_since_bounded_debt"] + 1
        with self.assertRaisesRegex(ValueError, "SCHOOL_DEBT_COUNTER_MIGRATION_CONFLICT"):
            _state_from_json(legacy, course)

    def test_command_created_genesis_composes_required_developmental_witnesses(self):
        fixture = atlas_create_tests.BamfAtlasReleaseCreateTests(methodName="runTest")
        fixture.setUp()
        try:
            target, student = self._create_first_start(fixture)
            student_id = candidate_identity_digest(student.retained_state)
            school = SimpleNamespace(
                stage="RECOVERY_1", current_student=SimpleNamespace(sha256=student_id))
            uninterrupted = self._select_visit(fixture, target, school)
            pointer_before, optimizer_before = self._assert_rejection_preserves_parent(
                fixture, target, student)
            self._assert_grade_and_debt_symmetry()
            self._assert_rights_hold()
            self._assert_positive_developmental_evidence()
            self._assert_legacy_b_cadence_rejected()

            _reset_execution_cache_owner_for_tests()
            with fixture.c07_read_context():
                cold, _ = load_bamf_generation_authority(target / "bamf-state.json")
            rebound = self._select_visit(fixture, target, school)
            self.assertEqual(retained_digest(cold.retained_state), optimizer_before)
            self.assertEqual(cold.optimizer_hyperparameters, student.optimizer_hyperparameters)
            self.assertEqual(rebound.identity, uninterrupted.identity)
            self.assertEqual((target / "bamf-state.json").read_bytes(), pointer_before)
        finally:
            fixture.tearDown()


if __name__ == "__main__":
    unittest.main()
