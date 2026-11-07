"""Small real-B12 fixtures for B13.1 custody tests."""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import os
from pathlib import Path
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.data_plane import data_plane
from bilqis_mlx.factory.executable_release import admit_executable_factory_release
from bilqis_mlx.learning.atlas_acceptance import mint_acceptance_binding
from bilqis_mlx.learning.atlas_retention_decision import decide_candidate_retention
from bilqis_mlx.learning.atlas_candidate import (
    CandidateCustodyIdentity, CandidateState, begin_candidate, candidate_step,
    resolve_candidate,
)
from bilqis_mlx.learning._retention.tests.execution_fixtures import execution_provenance
from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge, PlasticityPolicy
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, AdamWStateTree
from bilqis_mlx.runtime.bamf_bundle import (
    BamfBundleCandidate, prepare_initial_generation, publish_bamf_generation,
    publish_initial_generation, load_bamf_generation,
)
from bilqis_mlx.runtime.bamf_bundle.genesis_foundation import (
    initial_foundation_sidecars,
)
from bilqis_mlx.runtime.bamf_bundle.motif_codec import snapshot_to_record
from bilqis_mlx.runtime.bamf_bundle.records import canonical, sha
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, GenerationProvenance, Initializer, ModelTopologySpecV2,
    ParameterCensus, ParameterGroup, ParameterSpec, b01_generation_authority,
    b01_generation_extents, b01_model_implementation_sha256,
)
from bilqis_mlx.runtime.state import _fingerprint

NAME = "identity.bank.0"
RELEASE = "b" * 64
IMPLEMENTATION = b01_model_implementation_sha256()
DECLARED = (ParameterSpec(NAME, (2, 2), Initializer.EMBEDDING,
                          ParameterGroup.IDENTITY_ROW_AGE, True),)
HP = AdamWHyperparameters(.001, (.9, .95), 1e-8, .01)
FIXTURE_PARENT_MANIFEST = "6" * 64


def _genesis_defaults(release):
    source_identity = (release.source_bindings.source_attestation_sha256
                       or release.source_bindings.digest())
    teacher_identity = release.execution_plan.projection_digests.teaching
    provenance = GenerationProvenance(
        source_identity, release.release_sha256, teacher_identity, 0)
    motif = MotifManifest(provenance.release_digest)
    extents = GenerationExtents(
        1, 1, "a" * 64, motif.digest, "c" * 64)
    return {
        "provenance": provenance,
        "extents": extents,
        "semantic_abi": {
            "schema": "bilqis.mlx.bamf-semantic-abi/v1",
            "active_set_sha256": "a" * 64,
            "semantic_bank_count": 1,
            "bank_identities": ["bank:0"],
        },
        "compiler_features": {
            "schema": "bilqis.mlx.bamf-compiler-features/v1",
            "factor_map_sha256": "c" * 64,
            "compiler_sha256": "f" * 64,
            "rights_epoch": 2,
            "correction_generation": 4,
        },
        "correction_frontier": {
            "schema": "bilqis.mlx.bamf-correction-frontier/v1",
            "source_identity": source_identity,
            "release_digest": release.release_sha256,
            "rights_epoch": 2,
            "correction_generation": 4,
            "frontier": [],
        },
        "teacher_state": {
            "schema": "bilqis.mlx.bamf-teacher-state/v1",
            "teacher_identity": teacher_identity,
            "teacher_epoch": 0,
            "next_seed": 42,
            "cursor": "lesson:7",
        },
        "evaluation_contract": {
            "schema": "bilqis.mlx.bamf-evaluation-contract/v1",
            "contract_sha256": "9" * 64,
        },
    }


def genesis_preparation(*, run_id="fixture-run", run_seed=17,
                        delivery_events=None, foundation_row_ages=None, **overrides):
    """Enter B13 generation zero through the production constructor and issuer."""
    from bilqis_mlx.runtime.tests.operator.test_admission import _executable_fixture
    release, graph = _executable_fixture()
    origin = Checkpoint("7" * 64, "bundles/foundation-origin", 0, True)
    admission = admit_executable_factory_release(
        release, student_sha256=origin.sha256,
        optimizer_step=origin.optimizer_step,
        semantic_graph_sha256=_fingerprint(graph), graph=graph)
    forbidden = {
        "semantic_abi", "compiler_features", "correction_frontier",
        "teacher_state", "evaluation_contract",
    } & set(overrides)
    if forbidden:
        raise AssertionError(
            "generation-zero sidecars are owner-derived: " + ",".join(sorted(forbidden)))
    values = _genesis_defaults(release) | overrides
    (semantic_abi, compiler_features, _correction_frontier,
     _teacher_state, _evaluation_contract) = initial_foundation_sidecars(
        release, admission, graph, run_seed=run_seed)
    motif = MotifManifest(values["provenance"].release_digest)
    extents = b01_generation_extents(
        semantic_abi=semantic_abi,
        compiler_features=compiler_features, motif_page_count=1,
        motif_key_map_digest=motif.digest)
    return prepare_initial_generation(
        run_id=run_id, run_seed=run_seed, origin_checkpoint=origin,
        release=release, admission=admission, graph=graph,
        model_authority=b01_generation_authority(extents),
        optimizer_hyperparameters=HP,
        provenance=values["provenance"],
        foundation_row_ages=(
            () if foundation_row_ages is None else foundation_row_ages),
        delivery_events=(
            ({"event": "FIXTURE_GENESIS", "optimizer_step": 0},)
            if delivery_events is None else delivery_events),
    )


def publish_genesis(run_dir, *, run_seed=17, **overrides):
    """Publish a real production generation zero, never a test-minted C05 token."""
    return publish_initial_generation(
        run_dir, genesis_preparation(run_seed=run_seed, **overrides),
        reserve_gib=0.)


def parent_state() -> CandidateState:
    values = mx.array([[.5, -.25], [1., 2.]], dtype=mx.float32)
    optimizer = AdamWStateTree(
        {NAME: values}, {NAME: mx.ones_like(values) * .1},
        {NAME: mx.ones_like(values) * .01},
        {NAME: mx.array([2, 3], dtype=mx.uint64)})
    policy = PlasticityPolicy(
        "ADAPTIVE", 7, (IdentityRowAge(0, 0, 7), IdentityRowAge(0, 1, 2)))
    allocations = MotifAllocationSnapshot(MotifManifest(RELEASE))
    extents = GenerationExtents(1, 1, "a" * 64, allocations.manifest.digest, "c" * 64)
    return CandidateState(
        optimizer, policy, allocations, 11,
        CandidateCustodyIdentity(
            "fixture-run", 0, FIXTURE_PARENT_MANIFEST,
            ModelTopologySpecV2().digest, extents.digest))


def accepted_state(
        parent: CandidateState,
        extents: GenerationExtents | None = None) -> CandidateState:
    transaction = begin_candidate(parent)
    spec = ModelTopologySpecV2()
    extents = extents or GenerationExtents(
        1, 1, "a" * 64, parent.allocations.manifest.digest, "c" * 64)
    with shape_patch():
        transaction = candidate_step(
            transaction, {NAME: mx.array([[3., 4.], [0., 0.]], dtype=mx.float32)},
            execution_provenance(transaction.parent, rows=(0,),
                                       candidate_step=transaction.update_steps + 1), HP,
            spec=spec, extents=extents,
            loss_bearing=True, max_norm=1.)
    return resolve_candidate(transaction, accepted=True)


def rejected_state(
        parent: CandidateState,
        extents: GenerationExtents | None = None) -> CandidateState:
    transaction = begin_candidate(parent)
    spec = ModelTopologySpecV2()
    extents = extents or GenerationExtents(
        1, 1, "a" * 64, parent.allocations.manifest.digest, "c" * 64)
    with shape_patch():
        transaction = candidate_step(
            transaction, {NAME: mx.ones((2, 2), dtype=mx.float32)},
            execution_provenance(transaction.parent, rows=(0,),
                                       candidate_step=transaction.update_steps + 1), HP,
            spec=spec, extents=extents,
            loss_bearing=True, max_norm=1.)
    return resolve_candidate(transaction, accepted=False)


def next_accepted_step(
        parent: CandidateState,
        extents: GenerationExtents | None = None) -> CandidateState:
    transaction = begin_candidate(parent)
    spec = ModelTopologySpecV2()
    extents = extents or GenerationExtents(
        1, 1, "a" * 64, parent.allocations.manifest.digest, "c" * 64)
    with shape_patch():
        transaction = candidate_step(
            transaction, {NAME: mx.array([[.25, -.5], [0., 0.]], dtype=mx.float32)},
            execution_provenance(transaction.parent, rows=(0,),
                                       candidate_step=transaction.update_steps + 1), HP,
            spec=spec, extents=extents,
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
                   "bilqis_mlx.runtime.topology_v2.validation.expected_bamf_shapes",
                   "bilqis_mlx.runtime.backbone_identity.expected_bamf_shapes",
                   "bilqis_mlx.learning.atlas_participation_census."
                   "expected_bamf_shapes",
                   "bilqis_mlx.learning._retention.atlas_participation_census."
                   "expected_bamf_shapes",
                   ):
        stack.enter_context(patch(target, return_value=DECLARED))
    def census(spec, extents):
        return ParameterCensus(spec.digest, extents.digest, DECLARED)
    stack.enter_context(patch(
        "bilqis_mlx.runtime.topology_v2.construction.bamf_parameter_census",
        side_effect=census))
    return stack


def retention_decision(*, accepted=True, parent=None, retained=None) -> object:
    """Issue a test-only token from the unshipped disposable C05 harness."""
    from bilqis_mlx.runtime.tests.capability.capability_retention_helpers import (
        _screen_inputs,
    )
    from tests.bamf_disposable_retention import issue_disposable_screen
    screen = _screen_inputs(protected_loss=2 if accepted else 3)
    return issue_disposable_screen(
        screen,
        parent if parent is not None else parent_state(),
        retained if retained is not None else parent_state(),
    )


def acceptance(bundle, *, parent=None) -> object:
    """Mint the retention owner's acceptance binding for one candidate bundle."""
    return mint_acceptance_binding(
        retention_decision(parent=parent, retained=bundle.retained_state),
        bundle.retained_state, run_id=bundle.run_id,
        generation=bundle.generation,
        feature_sha256=bundle.extents.factor_map_digest)


def publish_candidate(run_dir, bundle):
    """Use production genesis for fixture generation zero; C05 only for successors."""
    if bundle.generation == 0:
        prepared = genesis_preparation(
            run_id=bundle.run_id,
            foundation_row_ages=bundle.retained_state.policy.row_ages,
            delivery_events=({"event": "FIXTURE_GENESIS", "optimizer_step": 0},))
        return publish_initial_generation(run_dir, prepared, reserve_gib=0.)
    parent = None
    if bundle.run_identity is None:
        parent = load_bamf_generation(Path(run_dir) / "bamf-state.json")
        bundle = replace(bundle, run_identity=parent.run_identity)
    elif bundle.generation > 0:
        parent = load_bamf_generation(Path(run_dir) / "bamf-state.json")
    if (parent is not None and bundle.topology == parent.topology
            and bundle.extents.semantic_bank_count == parent.extents.semantic_bank_count
            and bundle.extents.motif_page_count == parent.extents.motif_page_count
            and bundle.extents.active_semantic_digest
            == parent.extents.active_semantic_digest
            and bundle.extents.factor_map_digest == parent.extents.factor_map_digest):
        retained = replace(
            bundle.retained_state,
            allocations=parent.retained_state.allocations,
            custody=parent.retained_state.custody)
        bundle = replace(
            bundle, extents=parent.extents, retained_state=retained)
    return publish_bamf_generation(
        run_dir, bundle,
        acceptance=acceptance(
            bundle, parent=None if parent is None else parent.retained_state))
