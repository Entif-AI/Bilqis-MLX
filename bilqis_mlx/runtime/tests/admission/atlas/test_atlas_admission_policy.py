"""Lease scope uses actual native proposals/packages, with no adoption executor."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_admission import advance_atlas_frontier
from bilqis_mlx.runtime.atlas_admission_policy import AtlasAdmissionContext, AtlasDeltaEnvelope, PostAdmissionTotals
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import _lease, _REGISTRY, _signed
from bilqis_mlx.runtime.tests import test_jit_adoption as native_fixture
from bilqis_mlx.runtime.atlas_revalidation import SourceAuthorityRegistry, SourceAuthorityScope
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.factory.jit_curriculum import propose_curriculum_delta

_REGISTRY = SourceAuthorityRegistry((replace(_REGISTRY.keys[0], allowed_scopes=tuple(sorted(
    (*_REGISTRY.keys[0].allowed_scopes, SourceAuthorityScope(DependencyKind.ARTIFACT, 'atlas-delta:')),
    key=lambda scope: (scope.kind.value, scope.key_prefix)))),))


class AtlasAdmissionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.native = native_fixture.JitAdoptionTests()
        self.native.setUp()
        self.addCleanup(self.native.doCleanups)
        self.addCleanup(self.native.fixture.doCleanups)
        self.lease = _lease()
        fixture = self.native.fixture.fixture
        self.context = AtlasAdmissionContext(self.lease.run_identity, self.native.current,
            self.native.frontier, self.native.ledger, self.native.plan, self.native.checkpoint,
            self.lease.source_approval, _REGISTRY, fixture.registry, fixture.answers)
        self.envelope = self.envelope_for(self.native.proposal)

    def envelope_for(self, proposal):
        introduced = len(
            self.native.staged.successor.semantic_catalog[
                len(self.native.current.semantic_catalog):])
        return _signed(AtlasDeltaEnvelope(proposal, self.native.staged, ('family:one',),
            ('operator:one',), PostAdmissionTotals(1, 1, 8, 1024, 2048), introduced,
            contract_digest(self.lease.source_approval), 'fixture:salience-owner', '0' * 128))

    def test_no_lease_and_authorized_fixture_stage_without_adoption_claim(self):
        unleased = advance_atlas_frontier(self.context, self.envelope, None)
        self.assertEqual(unleased.status.value, 'STAGED')
        self.assertEqual(unleased.reason, 'EXPLICIT_ATLAS_LEASE_REQUIRED')
        authorized = advance_atlas_frontier(self.context, self.envelope, self.lease)
        self.assertEqual(authorized.reason, 'ACCEPTED_RUN_AUTHORITY_UNAVAILABLE')
        self.assertEqual(authorized.lease_sha256, self.lease.digest())
        self.assertEqual(authorized.proposal_sha256, self.native.proposal.proposal_sha256)
        self.assertFalse(authorized.state_adopted)
        self.assertEqual(self.native.checkpoint.optimizer_step, 0)

    def test_three_native_proposals_reuse_one_lease_but_do_not_prove_adoption(self):
        seen = []
        for step in range(3):
            checkpoint = replace(self.native.checkpoint, optimizer_step=step)
            proposal = propose_curriculum_delta(self.native.frontier, self.native.current,
                self.native.ledger, self.native.plan, checkpoint.sha256, checkpoint.optimizer_step,
                candidate_bindings=(self.native.staged.binding,))
            result = advance_atlas_frontier(replace(self.context, checkpoint=checkpoint),
                                            self.envelope_for(proposal), self.lease)
            self.assertEqual(result.reason, 'ACCEPTED_RUN_AUTHORITY_UNAVAILABLE')
            self.assertEqual(result.lease_sha256, self.lease.digest())
            seen.append(result.proposal_sha256)
        self.assertEqual(len(set(seen)), 3)

    def test_exact_scope_and_post_admission_total_ceilings_precede_executor(self):
        for changes, reason in (({'source_family_ids': ('foreign-family',)}, 'OUT_OF_LEASE_SCOPE'),
                                ({'operator_ids': ('foreign-operator',)}, 'OUT_OF_LEASE_SCOPE'),
                                ({'post_admission_totals': PostAdmissionTotals(3, 1, 8, 1024, 2048)}, 'RESOURCE_CEILING'),
                                ({'new_semantic_identities': 17}, 'DELTA_BUDGET')):
            result = advance_atlas_frontier(self.context, _signed(replace(self.envelope, **changes)), self.lease)
            self.assertEqual(result.reason, reason)
        current = _signed(replace(self.lease.source_approval, rights_epoch=2))
        self.assertEqual(advance_atlas_frontier(replace(self.context, source_approval=current),
            self.envelope, self.lease).reason, 'OUT_OF_LEASE_SCOPE')
        held = _signed(replace(self.lease.source_approval, rights_compatible=False))
        self.assertEqual(advance_atlas_frontier(replace(self.context, source_approval=held),
            self.envelope, self.lease).reason, 'SOURCE_OR_RIGHTS_HELD')

    def test_native_proposal_and_signed_scope_cannot_be_relabelled(self):
        for envelope in (replace(self.envelope, signature_hex='0' * 128),
                         _signed(replace(self.envelope, source_approval_digest='0' * 64))):
            with self.assertRaises(BilqisError):
                advance_atlas_frontier(self.context, envelope, self.lease)
        with self.assertRaises(BilqisError):
            advance_atlas_frontier(replace(self.context, checkpoint=replace(self.native.checkpoint,
                optimizer_step=1)), self.envelope, self.lease)

    def test_unleased_staging_needs_no_live_implementation_registry(self):
        context = replace(self.context, source_registry=None, answer_registry=None)
        result = advance_atlas_frontier(context, self.envelope, None)
        self.assertEqual(result.reason, 'EXPLICIT_ATLAS_LEASE_REQUIRED')
        self.assertFalse(result.state_adopted)
        with self.assertRaises(BilqisError) as caught:
            advance_atlas_frontier(context, self.envelope, self.lease)
        self.assertEqual(caught.exception.context['reason'],
                         'BAMF_ATLAS_CURRENT_IMPLEMENTATION_REGISTRIES_REQUIRED')

    def test_accepted_run_context_delegates_exact_native_handoff_to_executor(self):
        runtime = SimpleNamespace(run_dir=Path('/fixture/run'))
        added = tuple(
            self.native.staged.successor.semantic_catalog[
                len(self.native.current.semantic_catalog):])
        native_staged = SimpleNamespace(candidate=SimpleNamespace(outbox=({
            'event': 'BAMF_A02_VOCABULARY_STAGED',
            'plan': {'allocations': tuple(
                {'semantic_id': semantic_id} for semantic_id in added)},
        },)))
        source_authority = object()
        accepted = SimpleNamespace(native_pointer={
            'generation': 1, 'manifest_sha256': '9' * 64})
        context = replace(
            self.context, runtime=runtime, native_staged=native_staged,
            source_authority=source_authority,
            source_registry=object(), answer_registry=object())
        cache = SimpleNamespace(
            source_authority_registry_sha256=self.context.registry.digest)
        with patch(
                'bilqis_mlx.runtime.bamf_bundle.admission.bind_accepted_execution_cache',
                return_value=cache), patch(
                'bilqis_mlx.runtime.bamf_bundle.require_issued_a02_staged_vocabulary_extension',
                return_value=native_staged), patch(
                'bilqis_mlx.runtime.atlas_admission_policy.native_post_admission_totals',
                return_value=self.envelope.post_admission_totals), patch(
                'bilqis_mlx.source_adapters.school.live_source_registry',
                return_value=self.context.source_registry), patch(
                'bilqis_mlx.factory.live_answers.live_answer_registry',
                return_value=self.context.answer_registry), patch(
                'bilqis_mlx.runtime.jit_adoption._execute_prepared_successor_adoption',
                return_value=accepted) as execute:
            result = advance_atlas_frontier(context, self.envelope, self.lease)
        self.assertEqual(result.status.value, 'ADOPTED')
        self.assertTrue(result.state_adopted)
        self.assertTrue(result.requires_cold_resume)
        self.assertEqual(result.accepted_generation, 1)
        self.assertEqual(result.accepted_manifest_sha256, '9' * 64)
        self.assertEqual(result.actual_neural_updates, 0)
        self.assertEqual(
            result.retained_release_sha256,
            self.native.staged.successor.release_sha256)
        execute.assert_called_once_with(
            runtime, frontier=self.native.frontier, current=self.native.current,
            ledger=self.native.ledger, plan=self.native.plan,
            checkpoint=self.native.checkpoint, proposal=self.native.proposal,
            staged=(self.native.staged,), source_registry=self.context.source_registry,
            answer_registry=self.context.answer_registry,
            native_staged=native_staged, atlas_lease=self.lease,
            source_authority=source_authority)

    def test_a02_semantic_plan_must_match_factory_delta_before_executor(self):
        native_staged = SimpleNamespace(candidate=SimpleNamespace(outbox=({
            'event': 'BAMF_A02_VOCABULARY_STAGED',
            'plan': {'allocations': ({'semantic_id': 'foreign:semantic'},)},
        },)))
        context = replace(
            self.context, runtime=SimpleNamespace(run_dir=Path('/fixture/run')),
            native_staged=native_staged,
            source_authority=object())
        cache = SimpleNamespace(
            source_authority_registry_sha256=self.context.registry.digest)
        with patch(
                'bilqis_mlx.runtime.bamf_bundle.admission.bind_accepted_execution_cache',
                return_value=cache), patch(
                'bilqis_mlx.runtime.bamf_bundle.require_issued_a02_staged_vocabulary_extension',
                return_value=native_staged), patch(
                'bilqis_mlx.runtime.jit_adoption._execute_prepared_successor_adoption') as execute, \
                self.assertRaises(BilqisError) as caught:
            advance_atlas_frontier(context, self.envelope, self.lease)
        self.assertEqual(
            caught.exception.context['reason'],
            'BAMF_ATLAS_A02_FACTORY_SEMANTIC_MISMATCH')
        execute.assert_not_called()

    def test_native_resource_totals_must_match_envelope_before_executor(self):
        native_staged = SimpleNamespace(candidate=SimpleNamespace(outbox=({
            'event': 'BAMF_A02_VOCABULARY_STAGED', 'plan': {'allocations': ()},
        },)))
        context = replace(
            self.context,
            runtime=SimpleNamespace(run_dir=Path('/fixture/run')),
            native_staged=native_staged, source_authority=object())
        cache = SimpleNamespace(
            source_authority_registry_sha256=self.context.registry.digest)
        owner_totals = replace(self.envelope.post_admission_totals, semantic_banks=2)
        with patch(
                'bilqis_mlx.runtime.bamf_bundle.admission.bind_accepted_execution_cache',
                return_value=cache), patch(
                'bilqis_mlx.runtime.bamf_bundle.require_issued_a02_staged_vocabulary_extension',
                return_value=native_staged), patch(
                'bilqis_mlx.runtime.atlas_admission_policy.native_post_admission_totals',
                return_value=owner_totals), patch(
                'bilqis_mlx.runtime.jit_adoption._execute_prepared_successor_adoption') as execute, \
                self.assertRaises(BilqisError) as caught:
            advance_atlas_frontier(context, self.envelope, self.lease)
        self.assertEqual(
            caught.exception.context['reason'],
            'BAMF_ATLAS_POST_ADMISSION_TOTALS_DRIFT')
        execute.assert_not_called()

    def test_production_delta_registry_must_equal_accepted_b13_registry(self):
        context = replace(
            self.context,
            runtime=SimpleNamespace(run_dir=Path('/fixture/run')),
            native_staged=object(), source_authority=object())
        accepted = SimpleNamespace(source_authority_registry_sha256='f' * 64)
        with patch(
                'bilqis_mlx.runtime.bamf_bundle.admission.bind_accepted_execution_cache',
                return_value=accepted), self.assertRaises(BilqisError) as caught:
            advance_atlas_frontier(context, self.envelope, self.lease)
        self.assertEqual(
            caught.exception.context['reason'],
            'BAMF_ATLAS_ACCEPTED_DELTA_REGISTRY_DRIFT')

    def test_source_and_answer_code_drift_fail_before_any_adoption(self):
        fixture = self.native.fixture.fixture
        successor = self.native.staged.successor
        binding = successor.source_bindings.bindings[0]
        source = fixture.registry.require(binding.generator_id, binding.oracle_id)
        answer = fixture.answers.require(successor.answer_modalities[0].kind)
        changed_source = SimpleNamespace(require=Mock(return_value=replace(
            source, descriptor=replace(source.descriptor, implementation_sha256='f' * 64))))
        changed_answer = SimpleNamespace(require=Mock(return_value=replace(
            answer, descriptor=replace(answer.descriptor, implementation_sha256='f' * 64))))
        for overrides, reason in (
            ({'source_registry': changed_source}, 'BAMF_ATLAS_SOURCE_IMPLEMENTATION_DRIFT'),
            ({'answer_registry': changed_answer}, 'BAMF_ATLAS_ANSWER_IMPLEMENTATION_DRIFT'),
        ):
            with self.subTest(reason=reason), self.assertRaises(BilqisError) as caught:
                advance_atlas_frontier(replace(self.context, **overrides),
                                       self.envelope, self.lease)
            self.assertEqual(caught.exception.context['reason'], reason)
        self.assertEqual(advance_atlas_frontier(
            self.context, self.envelope, self.lease).reason,
            'ACCEPTED_RUN_AUTHORITY_UNAVAILABLE')
