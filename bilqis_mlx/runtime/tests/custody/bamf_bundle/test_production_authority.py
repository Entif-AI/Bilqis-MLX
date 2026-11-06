"""Production authority adversaries for the consolidated EGM-Mitigation candidate.

These witnesses cover the authority seams end to end: owner-derived participation
inputs, provenance that cannot be replayed, retention acceptance that only the
retention decision owner can grant, and step proofs that survive immutable B13
publication and cold readback.
"""
from __future__ import annotations

import inspect
import json
from dataclasses import replace
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import (
    AcceptedCandidateBinding, mint_acceptance_binding,
)
from bilqis_mlx.learning.atlas_plasticity import next_update_mode
from bilqis_mlx.learning.atlas_retention_decision import (
    CandidateRetentionDecision, decide_candidate_retention,
)
from bilqis_mlx.runtime.bamf_bundle import (
    load_bamf_generation, publish_bamf_generation,
)
from bilqis_mlx.learning.atlas_participation import (
    ActiveAdmittedRows, parameter_update_mask, step_participation,
)
from bilqis_mlx.learning.atlas_participation import (
    RoleReadParticipation, SemanticDenominator, StepParticipationInputs,
)
from bilqis_mlx.runtime.bamf_bundle import admission
from bilqis_mlx.runtime.bamf_bundle.admission import (
    admit_candidate_step, bind_accepted_execution_cache,
    derive_participation_inputs,
)
from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
    AcceptedExecutionCache, require_accepted_execution_cache,
)

from bilqis_mlx.learning._retention.tests.execution_fixtures import (
    execution_provenance,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, accepted_state, candidate, parent_state, retention_decision,
    shape_patch,
)


def _participation():
    return step_participation(
        StepParticipationInputs(executed_parameter_names=("identity.bank.0",)),
        SemanticDenominator(), (), RoleReadParticipation())


def _active():
    return ActiveAdmittedRows(identity_rows=((0, 0),))


class ProductionAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def publish(self, source):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_bamf_generation(self.run, source, acceptance=acceptance(source))

    def test_production_step_accepts_no_caller_participation_facts(self):
        """The production API takes no caller-authored participation facts."""
        parameters = set(inspect.signature(
            admit_candidate_step).parameters)
        for forbidden in ("motif_reads", "executed_parameter_names", "visible_identity_rows",
                          "feedback_identity_rows", "local_slot_rows",
                          "group_eligible", "active_admitted", "spec", "extents",
                          "update_mask"):
            self.assertNotIn(forbidden, parameters)

    def test_group_eligibility_comes_from_the_ledger_and_policy_owners(self):
        self.publish(candidate(parent_state()))
        with shape_patch():
            student = admission.load_accepted_generation(self.run)
            eligibility, active = derive_participation_inputs(student)
        derived = set(eligibility.eligible_parameter_names) | set(
            eligibility.frozen_parameter_names)
        self.assertTrue(derived)
        self.assertFalse(set(eligibility.eligible_parameter_names)
                         & set(eligibility.frozen_parameter_names))
        self.assertEqual(eligibility.mode, next_update_mode(
            student.retained_state.policy, teacher_requests_full=False))
        self.assertEqual(active.identity_rows, eligibility.admitted_identity_rows)

    def test_only_accepted_b13_custody_mints_live_execution_cache(self):
        self.publish(candidate(parent_state()))
        with shape_patch():
            cache = bind_accepted_execution_cache(self.run)
        self.assertIs(require_accepted_execution_cache(cache), cache)
        self.assertEqual(cache.run_id, "fixture-run")
        self.assertEqual(
            cache.motif_manifest.digest,
            parent_state().allocations.manifest.digest,
        )
        with self.assertRaises(BilqisError):
            AcceptedExecutionCache()

    def test_production_step_reaches_the_owner_binder(self):
        self.publish(candidate(parent_state()))
        with shape_patch(), patch.object(
                admission, "production_candidate_step",
                side_effect=admission.production_candidate_step) as step:
            with self.assertRaises(BilqisError):
                admit_candidate_step(
                    self.run, {}, loss_bearing_target=True,
                    teacher_hparams=None, decay={}, max_norm=1.)
        self.assertTrue(step.called)

    def test_no_loss_step_cannot_promote_census_to_execution(self):
        self.publish(candidate(parent_state()))
        marker = object()
        with shape_patch(), patch.object(
                admission, "production_candidate_step", return_value=marker) as step:
            result = admit_candidate_step(
                self.run, {}, loss_bearing_target=False,
                teacher_hparams=None, decay={}, max_norm=1.)
        self.assertIs(result, marker)
        for forbidden in ("motif_reads", "executed_parameter_names",
                          "visible_identity_rows", "feedback_identity_rows",
                          "local_slot_rows"):
            self.assertNotIn(forbidden, step.call_args.kwargs)

    def test_admission_forwards_the_b11_gradient_execution_without_rederiving_it(self):
        self.publish(candidate(parent_state()))
        owner_execution = object()
        marker = object()
        with shape_patch(), patch.object(
                admission, "production_candidate_step", return_value=marker) as step:
            result = admit_candidate_step(
                self.run,
                loss_bearing_target=True,
                gradient_execution=owner_execution,
                teacher_hparams=None,
                decay={},
                max_norm=1.,
            )
        self.assertIs(result, marker)
        self.assertIs(step.call_args.kwargs["gradient_execution"], owner_execution)
        self.assertIsNone(step.call_args.args[1])

    def test_provenance_cannot_replay_onto_another_candidate_or_step(self):
        self.publish(candidate(parent_state()))
        with shape_patch():
            student = admission.load_accepted_generation(self.run)
        issued = execution_provenance(student.retained_state, rows=(0,))
        with self.assertRaises(BilqisError):
            replace(issued, run_id="other-run")
        with self.assertRaises(BilqisError):
            replace(issued, generation=99)
        with self.assertRaises(BilqisError):
            replace(issued, parent_manifest_sha256="9" * 64)
        with self.assertRaises(BilqisError):
            replace(issued, topology_digest="9" * 64)
        with self.assertRaises(BilqisError):
            replace(issued, extents_sha256="9" * 64)
        with self.assertRaises(BilqisError):
            replace(issued, parent_candidate_identity_sha256="9" * 64)
        with self.assertRaises(BilqisError):
            replace(issued, parent_optimizer_step=999)
        with self.assertRaises(BilqisError):
            replace(issued, candidate_step=2)

    def test_caller_created_candidate_cannot_publish_without_the_decision_owner(self):
        source = candidate(parent_state())
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            with self.assertRaises(BilqisError):
                publish_bamf_generation(self.run, source)
        self.assertFalse((self.run / "bamf-state.json").exists())

    def test_caller_cannot_mint_a_retention_decision(self):
        decision = retention_decision()
        with self.assertRaises(BilqisError):
            CandidateRetentionDecision(
                decision.decision, decision.reason, decision.parent_generation,
                decision.candidate_generation, decision.evidence_sha256,
                decision.policy_sha256)

    def test_primitive_retention_claims_cannot_issue_authority(self):
        with self.assertRaises(TypeError):
            decide_candidate_retention(
                no_target_gain=False, same_grade_net_gain=1,
                fixed_grade_regression=False, active_grade_regression=False,
                whole_school_regression=False, frontier_measured=True,
                fragile_losses=0, exceeded=False)

    def test_caller_selected_c05_screen_cannot_issue_live_authority(self):
        from bilqis_mlx.runtime.tests.capability.capability_retention_helpers import (
            _screen_inputs,
        )
        screen = _screen_inputs()
        with self.assertRaises(BilqisError) as failure:
            decide_candidate_retention(
                parent_solver=screen[0], candidate_solver=screen[1],
                target_capability=screen[2], policy=screen[3], cohorts=screen[4],
                parent_state=parent_state(),
                candidate_state=accepted_state(parent_state()))
        self.assertEqual(failure.exception.context["reason"],
                         "BAMF_C05_SOURCE_OWNER_REQUIRED")

    def test_acceptance_requires_an_accepted_decision(self):
        source = candidate(parent_state())
        rejected = retention_decision(
            accepted=False, retained=source.retained_state)
        with self.assertRaises(BilqisError):
            mint_acceptance_binding(
                rejected, source.retained_state, run_id=source.run_id,
                generation=source.generation,
                feature_sha256=source.extents.factor_map_digest)

    def test_step_proofs_survive_publication_and_cold_readback(self):
        initial = parent_state()
        first = self.publish(candidate(initial))
        retained = accepted_state(initial)
        second = self.publish(candidate(retained, 1, first["manifest_sha256"]))
        with shape_patch():
            student = load_bamf_generation(self.run / "bamf-state.json")
        proofs = student.retained_state.step_proofs
        self.assertEqual(len(proofs), 1)
        binding = AcceptedCandidateBinding.from_record(json.loads(
            (self.run / "bamf-acceptance" / f"{second['manifest_sha256']}.json")
            .read_text()))
        self.assertEqual(list(binding.step_proof_sha256),
                         [proof.digest for proof in proofs])

    def test_tampered_step_proof_fails_custody_validation(self):
        initial = parent_state()
        first = self.publish(candidate(initial))
        retained = accepted_state(initial)
        second = self.publish(candidate(retained, 1, first["manifest_sha256"]))
        proofs = (self.run / "bamf-bundles" / second["manifest_sha256"]
                  / "step-proofs.json")
        record = json.loads(proofs.read_text())
        record["proofs"][0]["mask_sha256"] = "0" * 64
        proofs.write_text(json.dumps(record))
        with shape_patch():
            with self.assertRaises(BilqisError):
                load_bamf_generation(self.run / "bamf-state.json")


if __name__ == "__main__":
    unittest.main()
