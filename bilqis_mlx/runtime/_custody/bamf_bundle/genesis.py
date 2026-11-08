"""B13 generation-zero run identity, construction, and bootstrap authority."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from bilqis_mlx.factory.executable_release import (
    ExecutableAdmissionReceipt, ExecutableFactoryRelease,
)
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import CandidateState
from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.atlas_engram import INITIAL_MOTIF_CAPACITY
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.atlas_optimizer import (
    AdamWHyperparameters, _create_unbound_bamf_optimizer,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    B01GenerationAuthority, GenerationProvenance,
    ModelTopologySpecV2, b01_generation_authority, b01_generation_extents,
    validate_b01_generation_authority,
)

from .records import BamfBundleCandidate, invalid, sidecar_records
from .genesis_records import (
    BamfRunIdentity, InitialGenerationBinding, ParsedInitialGenerationBinding,
    mint_initial_generation_binding, optimizer_hyperparameters_digest,
)
from .genesis_foundation import (
    InitialFoundationFeatureAuthority, initial_foundation_row_ages,
    initial_foundation_sidecars,
)
from .genesis_origin import (
    InitialFactoryFoundationAuthority, replay_initial_factory_foundation_authority,
)

_PREPARED_INITIAL_GENERATION_ISSUER = object()


@dataclass(frozen=True, init=False)
class PreparedInitialGeneration:
    candidate: BamfBundleCandidate
    binding: InitialGenerationBinding
    factory_authority: InitialFactoryFoundationAuthority
    graph: dict
    foundation_features: InitialFoundationFeatureAuthority
    _issuance: object = field(init=False, default=None, repr=False, compare=False)

    def __init__(self, *args, **kwargs) -> None:
        invalid("BAMF_INITIAL_GENERATION_PREPARATION_REQUIRED")

    def __post_init__(self) -> None:
        if getattr(self, "_issuance", None) is not _PREPARED_INITIAL_GENERATION_ISSUER:
            invalid("BAMF_INITIAL_GENERATION_PREPARATION_REQUIRED")

    @property
    def release(self) -> ExecutableFactoryRelease:
        return self.factory_authority.release

    @property
    def admission(self) -> ExecutableAdmissionReceipt:
        return self.factory_authority.admission

    @property
    def origin_checkpoint(self) -> Checkpoint:
        return self.factory_authority.origin_checkpoint


def _validated_factory_origin(
        factory_authority, graph, *, release=None, admission=None,
        origin_checkpoint=None) -> InitialFactoryFoundationAuthority:
    if (type(factory_authority) is not InitialFactoryFoundationAuthority
            or not isinstance(graph, dict)):
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_INVALID")
    authority = replay_initial_factory_foundation_authority(factory_authority, graph)
    if ((release is not None and release != authority.release)
            or (admission is not None and admission != authority.admission)
            or (origin_checkpoint is not None
                and origin_checkpoint != authority.origin_checkpoint)):
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_DRIFT")
    return authority


def _factory_generation_provenance(
        release: ExecutableFactoryRelease,
        features: InitialFoundationFeatureAuthority) -> GenerationProvenance:
    """Bind Factory source/teacher identity to the admitted Atlas semantic release."""
    source = (release.source_bindings.source_attestation_sha256
              or release.source_bindings.digest())
    return GenerationProvenance(
        source, features.features.semantic_release,
        release.execution_plan.projection_digests.teaching, 0)


def _validate_candidate_source_authority(
        candidate: BamfBundleCandidate, *, release: ExecutableFactoryRelease,
        admission: ExecutableAdmissionReceipt, graph: dict,
        origin_checkpoint: Checkpoint,
        factory_authority: InitialFactoryFoundationAuthority | None = None,
        foundation_features: InitialFoundationFeatureAuthority | None = None) -> None:
    """Re-prove Factory/source/teacher authority for a generation-zero candidate."""
    authority = _validated_factory_origin(
        factory_authority, graph, release=release, admission=admission,
        origin_checkpoint=origin_checkpoint)
    release = authority.release
    admission = authority.admission
    origin_checkpoint = authority.origin_checkpoint
    if type(foundation_features) is not InitialFoundationFeatureAuthority:
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_INVALID")
    identity = candidate.run_identity
    if type(identity) is not BamfRunIdentity:
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_DRIFT")
    expected = _factory_generation_provenance(release, foundation_features)
    expected_sidecars = initial_foundation_sidecars(
        release, admission, graph, run_seed=identity.run_seed,
        feature_authority=foundation_features)
    teacher = candidate.teacher_state
    correction = candidate.correction_frontier
    if (candidate.generation != 0 or candidate.parent_manifest_sha256 is not None
            or candidate.provenance != expected
            or tuple(dict(value) for value in (
                candidate.semantic_abi, candidate.compiler_features,
                candidate.correction_frontier, candidate.teacher_state,
                candidate.evaluation_contract)) != expected_sidecars
            or not isinstance(teacher, Mapping)
            or teacher.get("teacher_identity") != expected.teacher_identity
            or teacher.get("teacher_epoch") != expected.teacher_epoch
            or not isinstance(correction, Mapping)
            or correction.get("source_identity") != expected.source_identity
            or correction.get("release_digest") != expected.release_digest
            or identity.run_id != candidate.run_id
            or identity.origin_checkpoint_sha256 != origin_checkpoint.sha256
            or identity.origin_checkpoint_filename != origin_checkpoint.filename
            or identity.origin_optimizer_step != origin_checkpoint.optimizer_step
            or identity.factory_release_sha256 != release.release_sha256
            or identity.semantic_graph_sha256 != admission.semantic_graph_sha256
            or identity.initial_candidate_identity_sha256
            != candidate_identity_digest(candidate.retained_state)
            or identity.initial_topology_digest != candidate.topology.digest
            or identity.initial_extents_digest != candidate.extents.digest
            or identity.initial_implementation_sha256 != candidate.implementation_sha256
            or identity.initial_source_identity != expected.source_identity
            or identity.initial_release_digest != expected.release_digest
            or identity.initial_teacher_identity != expected.teacher_identity
            or identity.initial_teacher_epoch != expected.teacher_epoch):
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_DRIFT")


def _issue_binding(
        candidate: BamfBundleCandidate, *, release: ExecutableFactoryRelease,
        admission: ExecutableAdmissionReceipt, graph: dict,
        origin_checkpoint: Checkpoint,
        factory_authority: InitialFactoryFoundationAuthority | None = None,
        foundation_features: InitialFoundationFeatureAuthority | None = None,
        ) -> InitialGenerationBinding:
    _validate_candidate_source_authority(
        candidate, release=release, admission=admission, graph=graph,
        origin_checkpoint=origin_checkpoint,
        factory_authority=factory_authority,
        foundation_features=foundation_features)
    _validate_candidate_b01_authority(candidate, foundation_features)
    return mint_initial_generation_binding(candidate)


def _validate_candidate_b01_authority(
        candidate: BamfBundleCandidate,
        foundation_features: InitialFoundationFeatureAuthority) -> None:
    """Rebuild generation-zero B01 geometry and seeded numerical state."""
    if (type(candidate) is not BamfBundleCandidate
            or type(candidate.run_identity) is not BamfRunIdentity
            or type(candidate.topology) is not ModelTopologySpecV2
            or candidate.generation != 0):
        invalid("BAMF_INITIAL_GENERATION_MODEL_AUTHORITY_DRIFT")
    try:
        allocations = MotifAllocationSnapshot(
            MotifManifest(candidate.provenance.release_digest))
        extents = b01_generation_extents(
            semantic_abi=candidate.semantic_abi,
            compiler_features=candidate.compiler_features,
            motif_page_count=allocations.manifest.capacity // INITIAL_MOTIF_CAPACITY,
            motif_key_map_digest=allocations.manifest.digest)
        authority = b01_generation_authority(extents)
        topology, implementation_sha256 = validate_b01_generation_authority(
            authority, extents)
        optimizer, _decay, _initialization = _create_unbound_bamf_optimizer(
            topology, extents, run_seed=candidate.run_identity.run_seed)
        expected_policy = PlasticityPolicy(
            "FOUNDATION", 0, initial_foundation_row_ages(
                foundation_features))
        expected_state = CandidateState(
            optimizer, expected_policy, allocations, 0)
    except (TypeError, ValueError, KeyError, AttributeError):
        invalid("BAMF_INITIAL_GENERATION_MODEL_AUTHORITY_DRIFT")
    if (candidate.topology.digest != authority.parameter_census.topology_digest
            or candidate.extents != extents
            or candidate.extents.digest != authority.parameter_census.extents_digest
            or candidate.implementation_sha256 != implementation_sha256
            or candidate.retained_state.policy != expected_policy
            or candidate.retained_state.allocations != allocations
            or candidate.retained_state.optimizer_step != 0
            or candidate.retained_state.custody is not None
            or candidate.retained_state.step_proofs != ()
            or candidate_identity_digest(candidate.retained_state)
            != candidate_identity_digest(expected_state)):
        invalid("BAMF_INITIAL_GENERATION_MODEL_AUTHORITY_DRIFT")


def prepare_initial_generation(
        *, run_id: str, run_seed: int, graph: dict,
        model_authority: B01GenerationAuthority,
        optimizer_hyperparameters: AdamWHyperparameters,
        provenance: GenerationProvenance,
        factory_authority: InitialFactoryFoundationAuthority | None = None,
        release: ExecutableFactoryRelease | None = None,
        admission: ExecutableAdmissionReceipt | None = None,
        origin_checkpoint: Checkpoint | None = None,
        foundation_features: InitialFoundationFeatureAuthority | None = None,
        delivery_events: tuple = ()) -> PreparedInitialGeneration:
    """Construct one source-bound generation-zero candidate and live B13 capability."""
    authority = _validated_factory_origin(
        factory_authority, graph, release=release, admission=admission,
        origin_checkpoint=origin_checkpoint)
    release = authority.release
    admission = authority.admission
    origin_checkpoint = authority.origin_checkpoint
    if type(foundation_features) is not InitialFoundationFeatureAuthority:
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_INVALID")
    expected_provenance = _factory_generation_provenance(
        release, foundation_features)
    if (not isinstance(run_id, str) or not run_id
            or type(run_seed) is not int or run_seed < 0
            or type(model_authority) is not B01GenerationAuthority
            or type(optimizer_hyperparameters) is not AdamWHyperparameters
            or type(provenance) is not GenerationProvenance
            or provenance != expected_provenance
            or type(delivery_events) is not tuple):
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_DRIFT")
    (semantic_abi, compiler_features, correction_frontier,
     teacher_state, evaluation_contract) = initial_foundation_sidecars(
        release, admission, graph, run_seed=run_seed,
        feature_authority=foundation_features)
    allocations = MotifAllocationSnapshot(MotifManifest(provenance.release_digest))
    try:
        extents = b01_generation_extents(
            semantic_abi=semantic_abi, compiler_features=compiler_features,
            motif_page_count=(
                allocations.manifest.capacity // INITIAL_MOTIF_CAPACITY),
            motif_key_map_digest=allocations.manifest.digest)
        topology, implementation_sha256 = validate_b01_generation_authority(
            model_authority, extents)
    except (TypeError, ValueError, KeyError):
        invalid("BAMF_INITIAL_GENERATION_MODEL_AUTHORITY_DRIFT")
    optimizer, _decay, _initialization = _create_unbound_bamf_optimizer(
        topology, extents, run_seed=run_seed)
    foundation_row_ages = initial_foundation_row_ages(foundation_features)
    state = CandidateState(
        optimizer, PlasticityPolicy("FOUNDATION", 0, foundation_row_ages),
        allocations, 0)
    candidate_sha = candidate_identity_digest(state)
    identity = BamfRunIdentity(
        run_id, run_seed, origin_checkpoint.sha256, origin_checkpoint.filename,
        origin_checkpoint.optimizer_step, release.release_sha256,
        admission.semantic_graph_sha256, candidate_sha, topology.digest,
        extents.digest, implementation_sha256, provenance.source_identity,
        provenance.release_digest, provenance.teacher_identity,
        provenance.teacher_epoch)
    candidate = BamfBundleCandidate(
        run_id, 0, None, implementation_sha256, topology, extents, state,
        optimizer_hyperparameters, provenance, semantic_abi, compiler_features,
        correction_frontier, teacher_state, evaluation_contract,
        {"schema": "bilqis.mlx.bamf-generation-transition/v1", "kind": "INITIAL",
         "invalidate_derived_caches": False},
        delivery_events, identity)
    sidecar_records(candidate)
    binding = _issue_binding(
        candidate, release=release, admission=admission, graph=graph,
        origin_checkpoint=origin_checkpoint,
        factory_authority=authority,
        foundation_features=foundation_features)
    prepared = object.__new__(PreparedInitialGeneration)
    for name, value in (
            ("candidate", candidate), ("binding", binding),
            ("factory_authority", authority), ("graph", dict(graph)),
            ("foundation_features", foundation_features),
            ("_issuance", _PREPARED_INITIAL_GENERATION_ISSUER)):
        object.__setattr__(prepared, name, value)
    prepared.__post_init__()
    return prepared


def validate_initial_generation_binding(candidate, binding) -> None:
    """Require a live B13 bootstrap capability for the exact generation-zero state."""
    if type(binding) is InitialGenerationBinding:
        binding.__post_init__()
    if (type(candidate) is not BamfBundleCandidate
            or type(binding) is not InitialGenerationBinding
            or candidate.generation != 0 or candidate.parent_manifest_sha256 is not None
            or type(candidate.run_identity) is not BamfRunIdentity
            or binding.run_id != candidate.run_id
            or binding.run_identity_sha256 != candidate.run_identity.digest
            or binding.candidate_identity_sha256
            != candidate_identity_digest(candidate.retained_state)
            or binding.optimizer_hyperparameters_sha256
            != optimizer_hyperparameters_digest(candidate.optimizer_hyperparameters)
            or binding.feature_sha256 != candidate.extents.factor_map_digest
            or binding.optimizer_step != candidate.retained_state.optimizer_step):
        invalid("BAMF_INITIAL_GENERATION_BINDING_DRIFT")


def validate_initial_generation_preparation(prepared: PreparedInitialGeneration) -> None:
    """Replay all Factory/source/B01 authority immediately before mutation."""
    if type(prepared) is not PreparedInitialGeneration:
        invalid("BAMF_INITIAL_GENERATION_PREPARATION_REQUIRED")
    prepared.__post_init__()
    _validate_candidate_source_authority(
        prepared.candidate, release=prepared.release,
        admission=prepared.admission, graph=prepared.graph,
        origin_checkpoint=prepared.origin_checkpoint,
        factory_authority=prepared.factory_authority,
        foundation_features=prepared.foundation_features)
    _validate_candidate_b01_authority(
        prepared.candidate, prepared.foundation_features)
    validate_initial_generation_binding(prepared.candidate, prepared.binding)


def validate_parsed_initial_generation_binding(student, binding, expected_digest: str) -> None:
    """Revalidate persisted bootstrap evidence without restoring live authority."""
    if (type(binding) is not ParsedInitialGenerationBinding
            or type(student.run_identity) is not BamfRunIdentity
            or student.generation != 0 or binding.digest != expected_digest
            or binding.run_id != student.run_id
            or binding.run_identity_sha256 != student.run_identity.digest
            or binding.candidate_identity_sha256
            != candidate_identity_digest(student.retained_state)
            or binding.optimizer_hyperparameters_sha256
            != optimizer_hyperparameters_digest(student.optimizer_hyperparameters)
            or binding.feature_sha256 != student.extents.factor_map_digest
            or binding.optimizer_step != student.retained_state.optimizer_step):
        invalid("BAMF_INITIAL_GENERATION_BINDING_DRIFT")


def publish_initial_generation(run_dir, prepared: PreparedInitialGeneration, *, reserve_gib=100.0):
    """Publish genesis through the existing B13 transaction, never through C05."""
    from .publication import _publish_authorized_generation
    return _publish_authorized_generation(
        run_dir, prepared.candidate, prepared, reserve_gib=reserve_gib)
