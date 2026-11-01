"""Lease scope uses actual native proposals/packages, with no adoption executor."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_admission import advance_atlas_frontier
from bilqis_mlx.runtime.atlas_admission_policy import AtlasAdmissionContext, AtlasDeltaEnvelope, PostAdmissionTotals
from bilqis_mlx.runtime.tests.admission.test_atlas_admission import _lease, _REGISTRY, _signed
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
        return _signed(AtlasDeltaEnvelope(proposal, self.native.staged, ('family:one',),
            ('operator:one',), PostAdmissionTotals(1, 1, 8, 1024, 2048), 1,
            contract_digest(self.lease.source_approval), 'fixture:salience-owner', '0' * 128))

    def test_no_lease_and_authorized_fixture_stage_without_adoption_claim(self):
        unleased = advance_atlas_frontier(self.context, self.envelope, None)
        self.assertEqual(unleased.status.value, 'STAGED')
        self.assertEqual(unleased.reason, 'EXPLICIT_ATLAS_LEASE_REQUIRED')
        authorized = advance_atlas_frontier(self.context, self.envelope, self.lease)
        self.assertEqual(authorized.reason, 'ADOPTION_EXECUTOR_UNAVAILABLE')
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
            self.assertEqual(result.reason, 'ADOPTION_EXECUTOR_UNAVAILABLE')
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
            'ADOPTION_EXECUTOR_UNAVAILABLE')
