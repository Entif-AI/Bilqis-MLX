"""B13 generation-zero run identity, construction, and bootstrap authority."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Mapping

from bilqis_mlx.factory.executable_release import (
    ExecutableAdmissionReceipt, ExecutableFactoryRelease,
)
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import CandidateState
from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge, PlasticityPolicy
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.atlas_optimizer import (
    AdamWHyperparameters, _create_unbound_bamf_optimizer,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, GenerationProvenance, ModelTopologySpecV2,
)
from bilqis_mlx.runtime.state import _fingerprint

from .records import BamfBundleCandidate, canonical, invalid, sha, sidecar_records

RUN_IDENTITY_SCHEMA = "bilqis.mlx.bamf-run-identity/v1"
INITIAL_BINDING_SCHEMA = "bilqis.mlx.bamf-initial-generation-binding/v1"
_INITIAL_BINDING_ISSUER = object()


def _hex(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


@dataclass(frozen=True)
class BamfRunIdentity:
    """Immutable birth identity shared by every generation in one BAMF run."""

    run_id: str
    run_seed: int
    origin_checkpoint_sha256: str
    origin_checkpoint_filename: str
    origin_optimizer_step: int
    factory_release_sha256: str
    semantic_graph_sha256: str
    initial_candidate_identity_sha256: str
    initial_topology_digest: str
    initial_extents_digest: str
    initial_implementation_sha256: str
    initial_source_identity: str
    initial_release_digest: str
    initial_teacher_identity: str
    initial_teacher_epoch: int
    schema_version: str = RUN_IDENTITY_SCHEMA

    def __post_init__(self) -> None:
        digests = (
            self.origin_checkpoint_sha256, self.factory_release_sha256,
            self.semantic_graph_sha256, self.initial_candidate_identity_sha256,
            self.initial_topology_digest, self.initial_extents_digest,
            self.initial_implementation_sha256, self.initial_release_digest,
        )
        if (self.schema_version != RUN_IDENTITY_SCHEMA
                or not isinstance(self.run_id, str) or not self.run_id
                or type(self.run_seed) is not int or self.run_seed < 0
                or not isinstance(self.origin_checkpoint_filename, str)
                or not self.origin_checkpoint_filename
                or type(self.origin_optimizer_step) is not int
                or self.origin_optimizer_step < 0
                or any(not _hex(value) for value in digests)
                or not isinstance(self.initial_source_identity, str)
                or not self.initial_source_identity
                or not isinstance(self.initial_teacher_identity, str)
                or not self.initial_teacher_identity
                or type(self.initial_teacher_epoch) is not int
                or self.initial_teacher_epoch < 0):
            invalid("BAMF_RUN_IDENTITY_INVALID")

    @property
    def digest(self) -> str:
        return sha(canonical(asdict(self)))

    def to_record(self) -> dict:
        return {**asdict(self), "run_identity_sha256": self.digest}

    @classmethod
    def from_record(cls, record: Mapping) -> "BamfRunIdentity":
        names = {item.name for item in fields(cls)}
        if not isinstance(record, Mapping) or set(record) != names | {"run_identity_sha256"}:
            invalid("BAMF_RUN_IDENTITY_INVALID")
        identity = cls(**{name: record[name] for name in names})
        if record["run_identity_sha256"] != identity.digest:
            invalid("BAMF_RUN_IDENTITY_INVALID")
        return identity


@dataclass(frozen=True)
class InitialGenerationBinding:
    """Live B13 capability for exactly one generation-zero bundle."""

    run_id: str
    generation: int
    run_identity_sha256: str
    candidate_identity_sha256: str
    feature_sha256: str
    optimizer_step: int
    schema_version: str = INITIAL_BINDING_SCHEMA
    _issuance: object = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if (getattr(self, "_issuance", None) is not _INITIAL_BINDING_ISSUER
                or not isinstance(self.run_id, str) or not self.run_id
                or self.generation != 0 or self.optimizer_step != 0
                or self.schema_version != INITIAL_BINDING_SCHEMA
                or any(not _hex(value) for value in (
                    self.run_identity_sha256, self.candidate_identity_sha256,
                    self.feature_sha256))):
            invalid("BAMF_INITIAL_GENERATION_BINDING_INVALID")

    def _public_record(self) -> dict:
        return {name: getattr(self, name) for name in (
            "run_id", "generation", "run_identity_sha256",
            "candidate_identity_sha256", "feature_sha256", "optimizer_step",
            "schema_version")}

    @property
    def digest(self) -> str:
        return sha(canonical(self._public_record()))

    def to_record(self) -> dict:
        return {**self._public_record(), "binding_sha256": self.digest}

    @classmethod
    def from_record(cls, record: Mapping) -> "ParsedInitialGenerationBinding":
        names = {
            "run_id", "generation", "run_identity_sha256",
            "candidate_identity_sha256", "feature_sha256", "optimizer_step",
            "schema_version",
        }
        if not isinstance(record, Mapping) or set(record) != names | {"binding_sha256"}:
            invalid("BAMF_INITIAL_GENERATION_BINDING_INVALID")
        payload = {name: record[name] for name in names}
        if (payload["schema_version"] != INITIAL_BINDING_SCHEMA
                or not isinstance(payload["run_id"], str) or not payload["run_id"]
                or payload["generation"] != 0 or payload["optimizer_step"] != 0
                or any(not _hex(payload[name]) for name in (
                    "run_identity_sha256", "candidate_identity_sha256", "feature_sha256"))
                or record["binding_sha256"] != sha(canonical(payload))):
            invalid("BAMF_INITIAL_GENERATION_BINDING_INVALID")
        return ParsedInitialGenerationBinding(payload)


@dataclass(frozen=True)
class ParsedInitialGenerationBinding:
    """Verified historical bootstrap evidence, never a live publication token."""

    fields: dict

    def __getattr__(self, name: str):
        if name in self.fields:
            return self.fields[name]
        raise AttributeError(name)

    @property
    def digest(self) -> str:
        return sha(canonical(self.fields))


@dataclass(frozen=True)
class PreparedInitialGeneration:
    candidate: BamfBundleCandidate
    binding: InitialGenerationBinding


def _validated_factory_origin(release, admission, graph, origin: Checkpoint) -> None:
    if (type(release) is not ExecutableFactoryRelease
            or type(admission) is not ExecutableAdmissionReceipt
            or type(origin) is not Checkpoint or not isinstance(graph, dict)):
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_INVALID")
    try:
        release.verify()
        release.verify_semantic_catalog(graph)
        admission.verify(release)
    except (TypeError, ValueError):
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_INVALID")
    if (admission.student_sha256 != origin.sha256
            or admission.optimizer_step != origin.optimizer_step
            or admission.semantic_graph_sha256 != _fingerprint(graph)):
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_DRIFT")


def _issue_binding(candidate: BamfBundleCandidate) -> InitialGenerationBinding:
    identity = candidate.run_identity
    if type(identity) is not BamfRunIdentity:
        invalid("BAMF_RUN_IDENTITY_REQUIRED")
    binding = object.__new__(InitialGenerationBinding)
    for name, value in (
            ("run_id", candidate.run_id), ("generation", 0),
            ("run_identity_sha256", identity.digest),
            ("candidate_identity_sha256", candidate_identity_digest(candidate.retained_state)),
            ("feature_sha256", candidate.extents.factor_map_digest),
            ("optimizer_step", candidate.retained_state.optimizer_step),
            ("schema_version", INITIAL_BINDING_SCHEMA),
            ("_issuance", _INITIAL_BINDING_ISSUER)):
        object.__setattr__(binding, name, value)
    binding.__post_init__()
    return binding


def prepare_initial_generation(
        *, run_id: str, run_seed: int, origin_checkpoint: Checkpoint,
        release: ExecutableFactoryRelease, admission: ExecutableAdmissionReceipt,
        graph: dict, topology: ModelTopologySpecV2, extents: GenerationExtents,
        optimizer_hyperparameters: AdamWHyperparameters,
        provenance: GenerationProvenance, implementation_sha256: str,
        semantic_abi: Mapping, compiler_features: Mapping,
        correction_frontier: Mapping, teacher_state: Mapping,
        evaluation_contract: Mapping, foundation_row_ages: tuple[IdentityRowAge, ...] = (),
        delivery_events: tuple = ()) -> PreparedInitialGeneration:
    """Construct one source-bound generation-zero candidate and live B13 capability."""
    _validated_factory_origin(release, admission, graph, origin_checkpoint)
    if (not isinstance(run_id, str) or not run_id
            or type(run_seed) is not int or run_seed < 0
            or type(topology) is not ModelTopologySpecV2
            or type(extents) is not GenerationExtents
            or type(optimizer_hyperparameters) is not AdamWHyperparameters
            or type(provenance) is not GenerationProvenance
            or type(foundation_row_ages) is not tuple
            or any(type(item) is not IdentityRowAge for item in foundation_row_ages)
            or type(delivery_events) is not tuple):
        invalid("BAMF_INITIAL_GENERATION_INPUT_INVALID")
    allocations = MotifAllocationSnapshot(MotifManifest(provenance.release_digest))
    if allocations.manifest.digest != extents.motif_key_map_digest:
        invalid("BAMF_INITIAL_GENERATION_MOTIF_DRIFT")
    optimizer, _decay, _initialization = _create_unbound_bamf_optimizer(
        topology, extents, run_seed=run_seed)
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
    return PreparedInitialGeneration(candidate, _issue_binding(candidate))


def validate_initial_generation_binding(candidate, binding) -> None:
    """Require a live B13 bootstrap capability for the exact generation-zero state."""
    if (type(candidate) is not BamfBundleCandidate
            or type(binding) is not InitialGenerationBinding
            or candidate.generation != 0 or candidate.parent_manifest_sha256 is not None
            or type(candidate.run_identity) is not BamfRunIdentity
            or binding.run_id != candidate.run_id
            or binding.run_identity_sha256 != candidate.run_identity.digest
            or binding.candidate_identity_sha256
            != candidate_identity_digest(candidate.retained_state)
            or binding.feature_sha256 != candidate.extents.factor_map_digest
            or binding.optimizer_step != candidate.retained_state.optimizer_step):
        invalid("BAMF_INITIAL_GENERATION_BINDING_DRIFT")


def validate_parsed_initial_generation_binding(student, binding, expected_digest: str) -> None:
    """Revalidate persisted bootstrap evidence without restoring live authority."""
    if (type(binding) is not ParsedInitialGenerationBinding
            or type(student.run_identity) is not BamfRunIdentity
            or student.generation != 0 or binding.digest != expected_digest
            or binding.run_id != student.run_id
            or binding.run_identity_sha256 != student.run_identity.digest
            or binding.candidate_identity_sha256
            != candidate_identity_digest(student.retained_state)
            or binding.feature_sha256 != student.extents.factor_map_digest
            or binding.optimizer_step != student.retained_state.optimizer_step):
        invalid("BAMF_INITIAL_GENERATION_BINDING_DRIFT")


def publish_initial_generation(run_dir, prepared: PreparedInitialGeneration, *, reserve_gib=100.0):
    """Publish genesis through the existing B13 transaction, never through C05."""
    if type(prepared) is not PreparedInitialGeneration:
        invalid("BAMF_INITIAL_GENERATION_PREPARATION_REQUIRED")
    validate_initial_generation_binding(prepared.candidate, prepared.binding)
    from .publication import _publish_authorized_generation
    return _publish_authorized_generation(
        run_dir, prepared.candidate, prepared.binding, reserve_gib=reserve_gib)
