"""Immutable B13 generation-zero identity and bootstrap binding records."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Mapping

from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest

from .records import canonical, invalid, sha

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


def mint_initial_generation_binding(candidate) -> InitialGenerationBinding:
    """Issue one live bootstrap binding after the caller proves source authority."""
    identity = candidate.run_identity
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
