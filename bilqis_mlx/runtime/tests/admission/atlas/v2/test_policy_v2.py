"""Atlas admission policy v2 verifier tests."""

from bilqis_mlx.runtime.tests.admission.atlas.v2.policy_support import *
from bilqis_mlx.learning.tests.test_atlas_salience import _signed
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import (
    _REGISTRY,
    _lease,
    _run,
)
class AtlasPolicyV2Tests(PolicyV2Support):
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
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._require_current_v2_lease"), \
                patch(
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._require_exact_atlas_release"):
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

    def test_semantic_id_handoff_requires_native_a02_before_policy_success(self):
        _capability, _semantic_id, handoff, plan, ledger, checkpoint = self._event_handoff()
        approval, lease = self._authority(handoff)
        context = self._context(handoff, plan, ledger, checkpoint, approval)

        with self.assertRaises(BilqisError) as caught:
            advance_atlas_frontier_v2(
                context, AtlasDeltaEnvelopeV2(handoff, None), lease)

        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_ATLAS_V2_DELTA_INVALID",
        )

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


    def test_semantic_release_outside_current_lease_stages_without_mutation(self):
        _capability, semantic_id, handoff, plan, ledger, checkpoint = self._event_handoff()
        approval, _lease_v2 = self._authority(handoff)
        outside = _signed(replace(
            approval, atlas_release_sha256="f" * 64, signature_hex="0" * 128))
        lease = issue_atlas_lease_v2(
            "fixture-v2-other-release", _run(), outside,
            ResourceCeilingV2(4, 4, 32768, 1 << 40, 1 << 40),
            requested_at="2026-11-10T16:15:00Z",
            human_command_sha256="8" * 64, human_started=True, registry=_REGISTRY)
        context = self._context(handoff, plan, ledger, checkpoint, outside)
        native = self._a02_staged(semantic_id)
        before_release = context.legacy.current_release
        before_ledger = context.legacy.ledger

        with patch(
                "bilqis_mlx.runtime.atlas_admission_policy_v2._accepted_run_bindings"), \
                patch(
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._require_current_v2_lease"), \
                patch(
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._require_exact_atlas_release",
                    side_effect=AssertionError("out-of-scope release reached in-scope verifier")):
            result = advance_atlas_frontier_v2(
                context, AtlasDeltaEnvelopeV2(handoff, native), lease)

        self.assertEqual(result.status.value, "STAGED")
        self.assertEqual(result.reason, "OUT_OF_LEASE_SCOPE")
        self.assertFalse(result.state_adopted)
        self.assertIs(context.legacy.current_release, before_release)
        self.assertIs(context.legacy.ledger, before_ledger)

    def test_one_v2_lease_covers_three_source_attested_successor_handoffs(self):
        capabilities = (
            "D.EVENT_OCCURRENCE", "D.COMMENCEMENT", "D.TERMINATION")
        handoffs = []
        current = self.current
        graph = self.parent_graph
        accepted_credit = None
        for capability in capabilities:
            _cap, semantic_id, handoff, plan, ledger, checkpoint = self._event_handoff(
                capability=capability, current_release=current, parent_graph=graph,
                accepted_credit=accepted_credit)
            handoffs.append((semantic_id, handoff, plan, ledger, checkpoint))
            current = handoff.staged_candidate.successor
            graph = event_frames.projected_graph(graph, (capability,))
            accepted_credit = self._accepted_credit(current, handoffs)

        semantic_release = handoffs[0][1].receipt.selection_snapshot.semantic_release
        self.assertTrue(all(
            handoff.receipt.selection_snapshot.semantic_release == semantic_release
            for _semantic_id, handoff, _plan, _ledger, _checkpoint in handoffs))
        families = tuple(sorted({
            family for _semantic_id, handoff, _plan, _ledger, _checkpoint in handoffs
            for family in handoff.family_ids
        }))
        operators = tuple(sorted({
            operator for _semantic_id, handoff, _plan, _ledger, _checkpoint in handoffs
            for operator in handoff.operator_ids
        }))
        approval = _signed(replace(
            AtlasSourceApproval(
                "fixture-v2-three-successors", semantic_release, families, operators,
                "b" * 64, 1, "c" * 64, "d" * 64, "e" * 64,
                True, True, "fixture:salience-owner", "0" * 128),
            signature_hex="0" * 128))
        lease = issue_atlas_lease_v2(
            "fixture-v2-three-successors", _run(), approval,
            ResourceCeilingV2(4, 4, 32768, 1 << 40, 1 << 40),
            requested_at="2026-11-12T15:00:00Z",
            human_command_sha256="7" * 64, human_started=True, registry=_REGISTRY)

        results = []
        with patch(
                "bilqis_mlx.runtime.atlas_admission_policy_v2._accepted_run_bindings"), \
                patch(
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._require_current_v2_lease"), \
                patch(
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._require_exact_atlas_release"):
            for semantic_id, handoff, plan, ledger, checkpoint in handoffs:
                context = self._context(handoff, plan, ledger, checkpoint, approval)
                result = advance_atlas_frontier_v2(
                    context, AtlasDeltaEnvelopeV2(
                        handoff, self._a02_staged(semantic_id)), lease)
                results.append(result)

        self.assertEqual(
            tuple(result.reason for result in results),
            ("V2_DELTA_AUTHORITY_VERIFIED",) * 3)
        self.assertEqual({result.lease_sha256 for result in results}, {lease.digest()})
        self.assertEqual(
            len({handoff.staged_candidate.successor.release_sha256
                 for _semantic_id, handoff, _plan, _ledger, _checkpoint in handoffs}),
            3)

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
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._require_current_v2_lease"), \
                patch(
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._require_exact_atlas_release"):
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
