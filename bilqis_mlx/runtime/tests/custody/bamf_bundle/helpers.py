"""Small real-B12 fixtures for B13.1 custody tests."""
from __future__ import annotations

from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.learning.atlas_candidate import (
    CandidateState, begin_candidate, candidate_step, resolve_candidate,
)
from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge, PlasticityPolicy
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, AdamWStateTree
from bilqis_mlx.runtime.bamf_bundle import BamfBundleCandidate
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, GenerationProvenance, Initializer, ModelTopologySpecV2,
    ParameterGroup, ParameterSpec,
)

NAME = "identity.bank.0"
RELEASE = "b" * 64
IMPLEMENTATION = "e" * 64
DECLARED = (ParameterSpec(NAME, (2, 2), Initializer.MATRIX,
                          ParameterGroup.IDENTITY_ROW_AGE, True),)
HP = AdamWHyperparameters(.001, (.9, .95), 1e-8, .01)


def parent_state() -> CandidateState:
    values = mx.array([[.5, -.25], [1., 2.]], dtype=mx.float32)
    optimizer = AdamWStateTree(
        {NAME: values}, {NAME: mx.ones_like(values) * .1},
        {NAME: mx.ones_like(values) * .01},
        {NAME: mx.array([2, 3], dtype=mx.uint64)})
    policy = PlasticityPolicy(
        "ADAPTIVE", 7, (IdentityRowAge(0, 0, 7), IdentityRowAge(0, 1, 2)))
    return CandidateState(
        optimizer, policy, MotifAllocationSnapshot(MotifManifest(RELEASE)), 11)


def accepted_state(parent: CandidateState) -> CandidateState:
    transaction = begin_candidate(parent)
    transaction = candidate_step(
        transaction, {NAME: mx.array([[3., 4.], [0., 0.]], dtype=mx.float32)},
        {NAME: mx.array([True, False])}, HP, decay={NAME: True},
        loss_bearing=True, max_norm=1.)
    return resolve_candidate(transaction, accepted=True)


def rejected_state(parent: CandidateState) -> CandidateState:
    transaction = begin_candidate(parent)
    transaction = candidate_step(
        transaction, {NAME: mx.ones((2, 2), dtype=mx.float32)},
        {NAME: mx.array([True, False])}, HP, decay={NAME: True},
        loss_bearing=True, max_norm=1.)
    return resolve_candidate(transaction, accepted=False)


def next_accepted_step(parent: CandidateState) -> CandidateState:
    transaction = begin_candidate(parent)
    transaction = candidate_step(
        transaction, {NAME: mx.array([[.25, -.5], [0., 0.]], dtype=mx.float32)},
        {NAME: mx.array([True, False])}, HP, decay={NAME: True},
        loss_bearing=True, max_norm=1.)
    return resolve_candidate(transaction, accepted=True)


def candidate(state: CandidateState, generation=0, parent=None) -> BamfBundleCandidate:
    motif_digest = state.allocations.manifest.digest
    extents = GenerationExtents(1, 1, "a" * 64, motif_digest, "c" * 64)
    provenance = GenerationProvenance("fixture-source", "d" * 64, "fixture-teacher", 3)
    transition = {
        "schema": "bilqis.mlx.bamf-generation-transition/v1",
        "kind": "INITIAL" if generation == 0 else "RETAINED_CANDIDATE",
        "invalidate_derived_caches": generation > 0,
    }
    return BamfBundleCandidate(
        "fixture-run", generation, parent, IMPLEMENTATION, ModelTopologySpecV2(),
        extents, state, HP, provenance,
        {"schema": "bilqis.mlx.bamf-semantic-abi/v1", "active_set_sha256": "a" * 64,
         "semantic_bank_count": 1, "bank_identities": ["bank:0"]},
        {"schema": "bilqis.mlx.bamf-compiler-features/v1", "factor_map_sha256": "c" * 64,
         "compiler_sha256": "f" * 64, "rights_epoch": 2,
         "correction_generation": 4},
        {"schema": "bilqis.mlx.bamf-correction-frontier/v1", "source_identity": "fixture-source",
         "release_digest": "d" * 64, "rights_epoch": 2,
         "correction_generation": 4, "frontier": []},
        {"schema": "bilqis.mlx.bamf-teacher-state/v1", "teacher_identity": "fixture-teacher",
         "teacher_epoch": 3, "next_seed": 42, "cursor": "lesson:7"},
        {"schema": "bilqis.mlx.bamf-evaluation-contract/v1", "contract_sha256": "9" * 64},
        transition, ({"event": "FIXTURE_ACCEPTED", "optimizer_step": state.optimizer_step},))


def shape_patch():
    return patch("bilqis_mlx.runtime.model_topology_v2.expected_bamf_shapes",
                 return_value=DECLARED)
