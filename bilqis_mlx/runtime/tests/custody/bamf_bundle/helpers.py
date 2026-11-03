"""Small real-B12 fixtures for B13.1 custody tests."""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
import os
from pathlib import Path
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.data_plane import data_plane
from bilqis_mlx.learning.atlas_acceptance import mint_acceptance_binding
from bilqis_mlx.learning.atlas_retention_decision import decide_candidate_retention
from bilqis_mlx.learning.atlas_candidate import (
    CandidateState, begin_candidate, candidate_step, resolve_candidate,
)
from bilqis_mlx.learning._retention.tests.execution_fixtures import execution_provenance
from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge, PlasticityPolicy
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, AdamWStateTree
from bilqis_mlx.runtime.bamf_bundle import (
    BamfBundleCandidate, publish_bamf_generation,
)
from bilqis_mlx.runtime.bamf_bundle.motif_codec import snapshot_to_record
from bilqis_mlx.runtime.bamf_bundle.records import canonical, sha
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
        execution_provenance(transaction.parent, rows=(0,)), HP, decay={NAME: True},
        loss_bearing=True, max_norm=1.)
    return resolve_candidate(transaction, accepted=True)


def rejected_state(parent: CandidateState) -> CandidateState:
    transaction = begin_candidate(parent)
    transaction = candidate_step(
        transaction, {NAME: mx.ones((2, 2), dtype=mx.float32)},
        execution_provenance(transaction.parent, rows=(0,)), HP, decay={NAME: True},
        loss_bearing=True, max_norm=1.)
    return resolve_candidate(transaction, accepted=False)


def next_accepted_step(parent: CandidateState) -> CandidateState:
    transaction = begin_candidate(parent)
    transaction = candidate_step(
        transaction, {NAME: mx.array([[.25, -.5], [0., 0.]], dtype=mx.float32)},
        execution_provenance(transaction.parent, rows=(0,)), HP, decay={NAME: True},
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


def rewrite_motif_bundle_fixture(
        bundle_root: Path, manifest: dict, allocations: MotifAllocationSnapshot) -> dict:
    """Replace fixture motif bytes, then rebind exact immutable custody metadata."""
    root = Path(bundle_root)
    record = deepcopy({key: value for key, value in manifest.items()
                       if key != "manifest_sha256"})
    raw_motif = canonical(snapshot_to_record(allocations))
    motif_sha = sha(raw_motif)
    motif_path = root / record["sidecars"]["motif_allocation"]["filename"]
    with motif_path.open("wb") as stream:
        stream.write(raw_motif)
        stream.flush()
        os.fsync(stream.fileno())
    data_plane().put_object(motif_sha, raw_motif)
    record["sidecars"]["motif_allocation"] = {
        "filename": motif_path.name,
        "sha256": motif_sha,
        "object_sha256": motif_sha,
    }
    prior_extents = record["extents"]
    record["extents"] = GenerationExtents(
        prior_extents["semantic_bank_count"], prior_extents["motif_page_count"],
        prior_extents["active_semantic_digest"], allocations.manifest.digest,
        prior_extents["factor_map_digest"],
    ).to_record()
    raw_manifest = canonical(record)
    manifest_sha = sha(raw_manifest)
    manifest_path = root / "manifest.json"
    with manifest_path.open("wb") as stream:
        stream.write(raw_manifest)
        stream.flush()
        os.fsync(stream.fileno())
    data_plane().put_node(
        manifest_sha, raw_manifest, record["generation"],
        record["parent_manifest_sha256"])
    directory = os.open(root, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return {**record, "manifest_sha256": manifest_sha}


def shape_patch():
    """Bind the B01 parameter ledger owner to the fixture's single bank."""
    stack = ExitStack()
    for target in ("bilqis_mlx.runtime.model_topology_v2.expected_bamf_shapes",
                   "bilqis_mlx.runtime.topology_v2.ledger.expected_bamf_shapes",
                   "bilqis_mlx.learning.atlas_participation_census."
                   "expected_bamf_shapes",
                   "bilqis_mlx.learning._retention.atlas_participation_census."
                   "expected_bamf_shapes",
                   ):
        stack.enter_context(patch(target, return_value=DECLARED))
    return stack


def retention_decision(*, accepted=True) -> object:
    """Issue the retention decision owner's decision for the fixture candidate."""
    return decide_candidate_retention(
        no_target_gain=not accepted, same_grade_net_gain=1,
        fixed_grade_regression=False, active_grade_regression=False,
        whole_school_regression=False, frontier_measured=True,
        fragile_losses=0, exceeded=False)


def acceptance(bundle) -> object:
    """Mint the retention owner's acceptance binding for one candidate bundle."""
    return mint_acceptance_binding(
        retention_decision(), bundle.retained_state, run_id=bundle.run_id,
        generation=bundle.generation,
        feature_sha256=bundle.extents.factor_map_digest)


def publish_candidate(run_dir, bundle):
    """Publish one candidate with its retention acceptance binding."""
    return publish_bamf_generation(run_dir, bundle, acceptance=acceptance(bundle))
