"""C07 v2 consumes owner-derived A09/A02 authority without a delta signer."""
from dataclasses import fields, replace
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory import candidate_realizations
from bilqis_mlx.factory.atlas_frontier import (
    AtlasCoverageEpoch,
    bind_realized_snapshot,
    next_atlas_delta,
)
from bilqis_mlx.factory.atlas_frontier_closure import resolve_frontier_closure
from bilqis_mlx.factory.tests.events.support import EventCandidateRealizationFixture, LEGACY
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.atlas_admission import (
    AtlasAdmissionLeaseV2,
    AtlasSourceApproval,
    ResourceCeilingV2,
    advance_atlas_frontier_v2,
    issue_atlas_lease_v2,
    persist_atlas_lease_v2,
    renew_atlas_lease_v2,
)
from bilqis_mlx.runtime.atlas_admission_policy import AtlasAdmissionContext
from bilqis_mlx.runtime.atlas_admission_policy_v2 import (
    AtlasAdmissionContextV2,
    AtlasDeltaEnvelopeV2,
)
from bilqis_mlx.runtime.tests.admission.atlas.atlas_adoption_executor_support import (
    AtlasAdoptionExecutorFixture,
)
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import (
    _REGISTRY, _lease, _run,
)
from bilqis_mlx.learning.tests.test_atlas_salience import _signed
from bilqis_mlx.source_adapters import event_frames


class AtlasAdmissionPolicyV2Tests(EventCandidateRealizationFixture, unittest.TestCase):
    def _event_handoff(self):
        candidate, source_frontier, policy = self.atlas_fixture()
        capability = next(iter(event_frames.SOURCE_SPECS))
        semantic_id = event_frames.atlas_semantic_id(capability)
        staged = candidate_realizations.prepare_realized_candidate(
            self.frontier, self.current, self.parent_graph, semantic_id,
            source_root=LEGACY, source_registry=self.source_registry,
            answer_registry=self.answer_registry)
        snapshot = self.build_snapshot(
            candidate, source_frontier, policy, self.current, staged)
        snapshot = bind_realized_snapshot(
            snapshot, candidate, self.frontier, self.current, (staged,))
        plan, checkpoint_sha256, step, ledger, learner = self.learner_evidence(
            self.current, {"A.IDENTITY"}, capability)
        closure = resolve_frontier_closure(
            snapshot, candidate.census, current_release=self.current,
            evidence_ledger=ledger, autonomy_plan=plan,
            checkpoint_sha256=checkpoint_sha256, optimizer_step=step)
        handoff = next_atlas_delta(
            AtlasCoverageEpoch(
                snapshot=snapshot, closure=closure,
                candidate_frontier=self.frontier,
                current_release=self.current,
                staged_candidates=(staged,), prior=None),
            learner, plan)
        handoff.verify()
        checkpoint = Checkpoint(
            checkpoint_sha256, "bundles/v2-event-owner", step, True)
        return capability, semantic_id, handoff, plan, ledger, checkpoint

    @staticmethod
    def _a02_staged(semantic_id):
        helper = object.__new__(AtlasAdoptionExecutorFixture)
        _parent, candidate = AtlasAdoptionExecutorFixture._native_parent_and_candidate(helper)
        return AtlasAdoptionExecutorFixture._a02_staged(
            helper, candidate, semantic_id=semantic_id)

    def _authority(self, handoff):
        approval = _signed(replace(
            AtlasSourceApproval(
                "fixture-v2-source", "a" * 64,
                handoff.family_ids, handoff.operator_ids,
                "b" * 64, 1, "c" * 64, "d" * 64, "e" * 64,
                True, True, "fixture:salience-owner", "0" * 128),
            signature_hex="0" * 128))
        lease = issue_atlas_lease_v2(
            "fixture-v2", _run(), approval,
            ResourceCeilingV2(4, 4, 32768, 1 << 40, 1 << 40),
            requested_at="2026-11-10T16:00:00Z",
            human_command_sha256="9" * 64, human_started=True,
            registry=_REGISTRY)
        return approval, lease

    def _context(self, handoff, plan, ledger, checkpoint, approval):
        legacy = AtlasAdmissionContext(
            _run(), handoff.receipt.predecessor_release,
            handoff.candidate_frontier, ledger, plan, checkpoint,
            approval, _REGISTRY, self.source_registry, self.answer_registry)
        return AtlasAdmissionContextV2(legacy, Path("/accepted/run"))

    def test_event_token_and_a01_identity_cross_bind_independently(self):
        capability, semantic_id, handoff, plan, ledger, checkpoint = self._event_handoff()
        self.assertNotEqual(
            tuple(handoff.receipt.selection.introduced_semantic_ids),
            (semantic_id,))
        self.assertEqual(
            candidate_realizations.realized_atlas_semantic_id(capability), semantic_id)
        native = self._a02_staged(semantic_id)
        approval, lease = self._authority(handoff)
        context = self._context(handoff, plan, ledger, checkpoint, approval)

        with patch(
                "bilqis_mlx.runtime.atlas_admission_policy_v2._accepted_run_bindings"), \
                patch(
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._require_current_v2_lease"):
            result = advance_atlas_frontier_v2(
                context, AtlasDeltaEnvelopeV2(handoff, native), lease)

        self.assertEqual(result.status.value, "STAGED")
        self.assertEqual(result.reason, "V2_DELTA_AUTHORITY_VERIFIED")
        self.assertEqual(result.lease_sha256, lease.digest())
        self.assertFalse(result.state_adopted)

    def test_wrong_a02_identity_and_missing_owner_mapping_fail_closed(self):
        _capability, semantic_id, handoff, plan, ledger, checkpoint = self._event_handoff()
        approval, lease = self._authority(handoff)
        context = self._context(handoff, plan, ledger, checkpoint, approval)
        wrong = self._a02_staged("urn:foreign:atlas-identity")
        with patch(
                "bilqis_mlx.runtime.atlas_admission_policy_v2._accepted_run_bindings"), \
                patch(
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._require_current_v2_lease"), \
                self.assertRaises(BilqisError) as caught:
            advance_atlas_frontier_v2(
                context, AtlasDeltaEnvelopeV2(handoff, wrong), lease)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_ATLAS_V2_A02_IDENTITY_BINDING_DRIFT")

        native = self._a02_staged(semantic_id)
        with patch(
                "bilqis_mlx.runtime.atlas_admission_policy_v2._accepted_run_bindings"), \
                patch(
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._require_current_v2_lease"), \
                patch(
                    "bilqis_mlx.factory.candidate_realizations.realized_atlas_semantic_id",
                    side_effect=ValueError), \
                self.assertRaises(BilqisError) as missing:
            advance_atlas_frontier_v2(
                context, AtlasDeltaEnvelopeV2(handoff, native), lease)
        self.assertEqual(
            missing.exception.context["reason"],
            "BAMF_ATLAS_V2_A01_IDENTITY_AUTHORITY_UNAVAILABLE")

    def test_v1_lease_is_not_reinterpreted_by_v2(self):
        _capability, semantic_id, handoff, plan, ledger, checkpoint = self._event_handoff()
        approval, _lease_v2 = self._authority(handoff)
        context = self._context(handoff, plan, ledger, checkpoint, approval)
        native = self._a02_staged(semantic_id)
        with patch(
                "bilqis_mlx.runtime.atlas_admission_policy_v2._accepted_run_bindings"):
            result = advance_atlas_frontier_v2(
                context, AtlasDeltaEnvelopeV2(handoff, native), _lease())
        self.assertEqual(result.reason, "V2_ATLAS_LEASE_REQUIRED")
        self.assertIsNone(result.lease_sha256)

    def test_resource_policy_uses_only_a02_sealed_v2_facts(self):
        _capability, semantic_id, handoff, plan, ledger, checkpoint = self._event_handoff()
        native = self._a02_staged(semantic_id)
        approval, _lease_v2 = self._authority(handoff)
        context = self._context(handoff, plan, ledger, checkpoint, approval)
        ceiling = ResourceCeilingV2(4, 4, 32768, 1, 1)
        lease = issue_atlas_lease_v2(
            "fixture-v2-low-resource", _run(), approval, ceiling,
            requested_at="2026-11-10T16:30:00Z",
            human_command_sha256="7" * 64, human_started=True,
            registry=_REGISTRY)
        helper = object.__new__(AtlasAdoptionExecutorFixture)
        _parent, candidate = AtlasAdoptionExecutorFixture._native_parent_and_candidate(helper)
        native = AtlasAdoptionExecutorFixture._a02_staged(
            helper, candidate, semantic_id=semantic_id,
            required_available_bytes=4096)

        with patch(
                "bilqis_mlx.runtime.atlas_admission_policy_v2._accepted_run_bindings"), \
                patch(
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._require_current_v2_lease"):
            result = advance_atlas_frontier_v2(
                context, AtlasDeltaEnvelopeV2(handoff, native), lease)

        self.assertEqual(result.reason, "RESOURCE_CEILING")
        caller_fields = {item.name for item in fields(AtlasDeltaEnvelopeV2)}
        self.assertNotIn("new_semantic_identities", caller_fields)
        self.assertNotIn("total_atlas_semantic_identities", caller_fields)
        self.assertNotIn("checkpoint_bytes_lower_bound", caller_fields)
        self.assertNotIn("required_available_bytes_lower_bound", caller_fields)

    def test_cross_run_substitution_rejects_before_policy(self):
        _capability, semantic_id, handoff, plan, ledger, checkpoint = self._event_handoff()
        approval, lease = self._authority(handoff)
        context = self._context(handoff, plan, ledger, checkpoint, approval)
        native = self._a02_staged(semantic_id)
        cache = SimpleNamespace(source_authority_registry_sha256=_REGISTRY.digest)
        with patch(
                "bilqis_mlx.runtime.atlas_admission._accepted_run_lease_identity",
                return_value=replace(_run(), lineage_id="foreign-lineage")), patch(
                "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_factory_release",
                return_value=handoff.receipt.predecessor_release), patch(
                "bilqis_mlx.runtime.bamf_bundle.admission.bind_accepted_execution_cache",
                return_value=cache), patch(
                "bilqis_mlx.runtime.jit_adoption._authenticate_native_staged_candidate"), \
                self.assertRaises(BilqisError) as caught:
            advance_atlas_frontier_v2(
                context, AtlasDeltaEnvelopeV2(handoff, native), lease)
        self.assertEqual(
            caught.exception.context["reason"], "BAMF_ATLAS_V2_ACCEPTED_RUN_DRIFT")

    def test_stale_current_learner_evidence_rejects_before_policy(self):
        _capability, semantic_id, handoff, plan, ledger, checkpoint = self._event_handoff()
        approval, lease = self._authority(handoff)
        context = self._context(handoff, plan, ledger, checkpoint, approval)
        stale = replace(
            context,
            legacy=replace(
                context.legacy,
                checkpoint=replace(
                    context.legacy.checkpoint,
                    optimizer_step=context.legacy.checkpoint.optimizer_step + 1,
                ),
            ),
        )
        native = self._a02_staged(semantic_id)
        with patch(
                "bilqis_mlx.runtime.atlas_admission_policy_v2._accepted_run_bindings"), \
                patch(
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._require_current_v2_lease"), \
                self.assertRaises(BilqisError) as caught:
            advance_atlas_frontier_v2(
                stale, AtlasDeltaEnvelopeV2(handoff, native), lease)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_ATLAS_V2_PROPOSAL_CONTEXT_DRIFT")

    def test_superseded_v2_lease_cannot_reclaim_broader_authority(self):
        _capability, semantic_id, handoff, plan, ledger, checkpoint = self._event_handoff()
        approval, prior = self._authority(handoff)
        native = self._a02_staged(semantic_id)
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            persist_atlas_lease_v2(
                run_dir, prior,
                independently_loaded_run=_run(), registry=_REGISTRY)
            replacement = issue_atlas_lease_v2(
                "fixture-v2-renewed", _run(), approval,
                ResourceCeilingV2(1, 1, 1, 1, 1),
                requested_at="2026-11-10T17:00:00Z",
                human_command_sha256="8" * 64, human_started=True,
                registry=_REGISTRY)
            renew_atlas_lease_v2(
                run_dir, replacement,
                independently_loaded_run=_run(), registry=_REGISTRY,
                expected_prior_lease_sha256=prior.digest(), human_started=True)
            context = AtlasAdmissionContextV2(
                self._context(handoff, plan, ledger, checkpoint, approval).legacy,
                run_dir)

            with patch(
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._accepted_run_bindings"), \
                    self.assertRaises(BilqisError) as caught:
                advance_atlas_frontier_v2(
                    context, AtlasDeltaEnvelopeV2(handoff, native), prior)

        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_ATLAS_V2_LEASE_CURRENT_AUTHORITY_DRIFT")


if __name__ == "__main__":
    unittest.main()
