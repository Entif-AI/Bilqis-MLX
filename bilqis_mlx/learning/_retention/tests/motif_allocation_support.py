"""Shared fixtures for retained B07 motif-allocation tests."""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import (
    CandidateCustodyIdentity, CandidateState, begin_candidate, candidate_step,
)
from bilqis_mlx.learning._atlas_candidate.common import (
    RETAINED_STATE_ISSUER, STATE_SCHEMA,
)
from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_execution_provenance import issue_execution_provenance
from bilqis_mlx.learning.atlas_participation import (
    ActiveAdmittedRows, RoleReadParticipation, SemanticDenominator,
    StepParticipationInputs,
)
from bilqis_mlx.learning.atlas_plasticity import (
    GroupEligibility, IdentityRowAge, PlasticityPolicy,
)
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, AdamWStateTree
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, Initializer, ModelTopologySpecV2, ParameterGroup,
    ParameterSpec,
)
from bilqis_mlx.runtime.topology_v2.ledger import ParameterCensus
from bilqis_mlx.learning._engram.tests.motif_fixtures import RELEASE


IDENTITY = "identity.bank.0"
MOTIF = "motif.page.0"
HP = AdamWHyperparameters(.001, (.9, .95), 1e-8, .01)


class CandidateMotifAllocationFixture:
    def setUp(self):
        self.spec = ModelTopologySpecV2()
        allocations = MotifAllocationSnapshot(MotifManifest(RELEASE))
        self.extents = GenerationExtents(
            1, 1, "a" * 64, allocations.manifest.digest, "c" * 64)
        self.declared = (
            ParameterSpec(
                IDENTITY, (2, 2), Initializer.EMBEDDING,
                ParameterGroup.IDENTITY_ROW_AGE, True),
            ParameterSpec(
                MOTIF, (16384, 128), Initializer.MOTIF_PAGE,
                ParameterGroup.FAST, True),
        )
        identity = mx.array([[.5, -.25], [1., 2.]], dtype=mx.float32)
        motif = mx.zeros((16384, 128), dtype=mx.float32)
        optimizer = AdamWStateTree(
            {IDENTITY: identity, MOTIF: motif},
            {IDENTITY: mx.ones_like(identity) * .1, MOTIF: mx.zeros_like(motif)},
            {IDENTITY: mx.ones_like(identity) * .01, MOTIF: mx.zeros_like(motif)},
            {IDENTITY: mx.array([2, 3], dtype=mx.uint64),
             MOTIF: mx.zeros((16384,), dtype=mx.uint64)},
        )
        policy = PlasticityPolicy(
            "ADAPTIVE", 7, (IdentityRowAge(0, 0, 7), IdentityRowAge(0, 1, 2)))
        custody = CandidateCustodyIdentity(
            "fixture-run", 0, "6" * 64, self.spec.digest, self.extents.digest)
        self.parent = CandidateState(optimizer, policy, allocations, 11, custody)

    def _shape_patches(self, growth=False):
        declared = self.declared
        if growth:
            declared = declared + (ParameterSpec(
                "motif.page.1", (16384, 128), Initializer.MOTIF_PAGE,
                ParameterGroup.FAST, True),)

        def shapes(_spec, extents):
            return declared if extents.motif_page_count == 2 else self.declared

        stack = ExitStack()
        for target in (
            "bilqis_mlx.runtime.model_topology_v2.expected_bamf_shapes",
            "bilqis_mlx.runtime.topology_v2.ledger.expected_bamf_shapes",
            "bilqis_mlx.runtime.topology_v2.validation.expected_bamf_shapes",
            "bilqis_mlx.runtime.backbone_identity.expected_bamf_shapes",
            "bilqis_mlx.learning.atlas_participation_census.expected_bamf_shapes",
            "bilqis_mlx.learning._retention.atlas_participation_census.expected_bamf_shapes",
        ):
            stack.enter_context(patch(target, side_effect=shapes))
        stack.enter_context(patch(
            "bilqis_mlx.runtime.topology_v2.construction.bamf_parameter_census",
            side_effect=lambda spec, extents: ParameterCensus(
                spec.digest, extents.digest, shapes(spec, extents))))
        return stack

    def _retained_state(self, optimizer, allocations, extents):
        state = object.__new__(CandidateState)
        for name, value in (
                ("optimizer", optimizer), ("policy", self.parent.policy),
                ("allocations", allocations),
                ("optimizer_step", self.parent.optimizer_step),
                ("custody", CandidateCustodyIdentity(
                    "fixture-run", 0, "6" * 64, self.spec.digest, extents.digest)),
                ("step_proofs", ()), ("schema_version", STATE_SCHEMA),
                ("_issuance", RETAINED_STATE_ISSUER)):
            object.__setattr__(state, name, value)
        state.__post_init__()
        return state

    def _step(self):
        candidate = begin_candidate(self.parent)
        identity_rows = ((0, 0),)
        inputs = StepParticipationInputs(
            visible_identity_rows=identity_rows,
            executed_parameter_names=(IDENTITY,), loss_bearing_target=True)
        active = ActiveAdmittedRows(identity_rows=identity_rows)
        eligibility = GroupEligibility(
            mode="FULL", eligible_parameter_names=(IDENTITY, MOTIF),
            frozen_parameter_names=(), admitted_identity_rows=identity_rows,
            fast_identity_rows=identity_rows, established_identity_rows=())
        with self._shape_patches():
            execution = issue_execution_provenance(
                inputs, SemanticDenominator(), (), RoleReadParticipation(),
                eligibility, active, spec=self.spec, extents=self.extents,
                run_id=self.parent.custody.run_id,
                generation=self.parent.custody.generation + 1,
                parent_manifest_sha256=self.parent.custody.manifest_sha256,
                parent_candidate_identity_sha256=candidate_identity_digest(self.parent),
                parent_optimizer_step=self.parent.optimizer_step,
                topology_digest=self.parent.custody.topology_digest,
                candidate_step_ordinal=1)
            return candidate_step(
                candidate,
                {IDENTITY: mx.array([[3., 4.], [0., 0.]], dtype=mx.float32),
                 MOTIF: mx.zeros((16384, 128), dtype=mx.float32)},
                execution, HP, spec=self.spec, extents=self.extents,
                loss_bearing=True, max_norm=1.)

    def _continuation(self, proposal):
        return SimpleNamespace(
            approved=SimpleNamespace(
                candidate=proposal, approved_context_digest="d" * 64),
            parent_manifest_sha256=self.parent.custody.manifest_sha256,
            parent_extents_sha256=self.extents.digest,
            parent_allocation_sha256=self.parent.allocations.digest,
        )

    @staticmethod
    def _continuation_patch(continuation):
        return patch(
            "bilqis_mlx.runtime.bamf_bundle.source_continuation."
            "_require_source_qualified_continuation",
            return_value=continuation)
