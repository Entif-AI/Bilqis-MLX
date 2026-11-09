"""Retention-owner acceptance binding for accepted candidate generations.

Live bindings attest the C05 screen and both optimizer identities. Historical
records remain parseable but cannot become publication capabilities.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from bilqis_mlx.errors import ErrorBus, SCHOOL

from .atlas_retention_decision import CandidateRetentionDecision

LEGACY_ACCEPTANCE_SCHEMA = "bilqis.mlx.accepted-candidate-binding/v1"
PREVIOUS_ACCEPTANCE_SCHEMA = "bilqis.mlx.accepted-candidate-binding/v2"
PREVIOUS_SOURCE_ACCEPTANCE_SCHEMA = "bilqis.mlx.accepted-candidate-binding/v3"
PREVIOUS_DEPENDENCY_ACCEPTANCE_SCHEMA = "bilqis.mlx.accepted-candidate-binding/v4"
ACCEPTANCE_SCHEMA = "bilqis.mlx.accepted-candidate-binding/v5"
DIGEST_HEX_LENGTH = 64
_LEGACY_FIELDS = (
    "run_id", "generation", "candidate_identity_sha256", "feature_sha256",
    "optimizer_step", "retention_reason", "step_proof_sha256",
    "decision_sha256", "schema_version",
)
_V2_BINDING_FIELDS = (
    "run_id", "generation", "candidate_identity_sha256",
    "parent_candidate_identity_sha256", "feature_sha256", "optimizer_step",
    "retention_reason", "step_proof_sha256", "decision_sha256",
    "evidence_sha256", "policy_sha256", "schema_version",
)
_V3_BINDING_FIELDS = _V2_BINDING_FIELDS[:-1] + ("source_anchors", "schema_version")
_V4_BINDING_FIELDS = _V3_BINDING_FIELDS
_BINDING_FIELDS = _V4_BINDING_FIELDS[:-1] + (
    "source_authority_registry_sha256", "schema_version")
_V3_SOURCE_ANCHOR_WIDTH = 9
_SOURCE_ANCHOR_WIDTH = 10
_DEPENDENCY_RECORD_WIDTH = 2
_SOURCE_ANCHOR_DIGEST_INDEXES = (2, 5, 6, 7, 8)
_SOURCE_ANCHOR_DEPENDENCIES_INDEX = 9


def _new_binding_owner():
    """Track live acceptance bindings by mint-owned object identity."""
    issued = {}

    def require(value):
        if issued.get(id(value)) is not value:
            _invalid()
        return value

    def issue(values):
        binding = object.__new__(AcceptedCandidateBinding)
        for name, value in values:
            object.__setattr__(binding, name, value)
        issued[id(binding)] = binding
        binding.__post_init__()
        return binding

    return require, issue


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _is_digest(value) -> bool:
    return (isinstance(value, str) and len(value) == DIGEST_HEX_LENGTH
            and all(char in "0123456789abcdef" for char in value))


def _canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _dependency_record(authority) -> tuple[tuple[str, str], ...]:
    return tuple(
        (ref.kind.value, ref.key) for ref in authority.immediate_dependencies)


def _source_anchors(training_authorities, state) -> tuple[tuple, ...]:
    if training_authorities is None:
        if any(proof.training_authority_sha256 is not None
               for proof in state.step_proofs):
            _invalid()
        return ()
    if type(training_authorities) is not tuple:
        _invalid()
    from bilqis_mlx.runtime.atlas_training_authority import BamfTrainingAuthority
    if len(training_authorities) != len(state.step_proofs):
        _invalid()
    anchors = []
    for proof, authority in zip(state.step_proofs, training_authorities):
        if type(authority) is not BamfTrainingAuthority:
            _invalid()
        authority.__post_init__()
        if (proof.training_authority_sha256 != authority.digest
                or proof.source_release_sha256 != authority.release_sha256
                or proof.training_batch_sha256 != authority.training_batch_sha256
                or proof.target_capability_id != authority.delivery_capability
                or proof.source_family_id != authority.source_family_id
                or proof.episode_id != authority.episode_id):
            _invalid()
        anchors.append((
            authority.delivery_capability,
            authority.source_row_id,
            authority.source_row_sha256,
            authority.source_family_id,
            authority.episode_id,
            authority.release_sha256,
            authority.training_batch_sha256,
            authority.generation_binding,
            authority.digest,
            _dependency_record(authority),
        ))
    return tuple(anchors)


def _dependency_records(value) -> bool:
    return (type(value) is tuple and value
            and all(type(item) is tuple and len(item) == _DEPENDENCY_RECORD_WIDTH
                    and all(isinstance(part, str) and part for part in item)
                    for item in value)
            and value == tuple(sorted(set(value))))


def _normalize_source_anchors(value, schema):
    if not isinstance(value, (tuple, list)):
        _invalid()
    normalized = []
    for anchor in value:
        if not isinstance(anchor, (tuple, list)):
            _invalid()
        anchor = tuple(anchor)
        if schema in (PREVIOUS_DEPENDENCY_ACCEPTANCE_SCHEMA, ACCEPTANCE_SCHEMA):
            if len(anchor) != _SOURCE_ANCHOR_WIDTH:
                _invalid()
            dependencies = anchor[-1]
            if not isinstance(dependencies, (tuple, list)):
                _invalid()
            anchor = (*anchor[:-1], tuple(
                tuple(item) if isinstance(item, (tuple, list)) else item
                for item in dependencies))
        normalized.append(anchor)
    return tuple(normalized)


def _valid_source_anchors(value, schema=ACCEPTANCE_SCHEMA) -> bool:
    if type(value) is not tuple:
        return False
    width = (_SOURCE_ANCHOR_WIDTH if schema in (
                 PREVIOUS_DEPENDENCY_ACCEPTANCE_SCHEMA, ACCEPTANCE_SCHEMA)
             else _V3_SOURCE_ANCHOR_WIDTH)
    for anchor in value:
        if type(anchor) is not tuple or len(anchor) != width:
            return False
        strings = anchor[:_SOURCE_ANCHOR_DEPENDENCIES_INDEX]
        if (not all(isinstance(item, str) and item for item in strings)
                or not all(_is_digest(strings[index])
                           for index in _SOURCE_ANCHOR_DIGEST_INDEXES)):
            return False
        if (schema in (PREVIOUS_DEPENDENCY_ACCEPTANCE_SCHEMA, ACCEPTANCE_SCHEMA)
                and not _dependency_records(
                    anchor[_SOURCE_ANCHOR_DEPENDENCIES_INDEX])):
            return False
    return True


def candidate_identity_digest(state) -> str:
    """Digest the full candidate optimizer state, including native AdamW."""
    import numpy as np
    optimizer = state.optimizer
    parts = {}
    for group in ("parameters", "m", "v", "update_counts"):
        parts[group] = {
            name: np.asarray(value).tobytes().hex()
            for name, value in sorted(getattr(optimizer, group).items())}
    return hashlib.sha256(_canonical({
        "state": parts, "optimizer_step": state.optimizer_step})).hexdigest()


@dataclass(frozen=True)
class AcceptedCandidateBinding:
    """Live owner-issued acceptance for one exact candidate and parent."""

    run_id: str
    generation: int
    candidate_identity_sha256: str
    parent_candidate_identity_sha256: str
    feature_sha256: str
    optimizer_step: int
    retention_reason: str
    decision_sha256: str
    evidence_sha256: str
    policy_sha256: str
    step_proof_sha256: tuple = ()
    source_anchors: tuple = ()
    source_authority_registry_sha256: str | None = None
    schema_version: str = ACCEPTANCE_SCHEMA

    def __post_init__(self) -> None:
        _require_issued_binding(self)
        if (not isinstance(self.run_id, str) or not self.run_id
                or type(self.generation) is not int or self.generation < 0
                or any(not _is_digest(value) for value in (
                    self.candidate_identity_sha256,
                    self.parent_candidate_identity_sha256, self.feature_sha256,
                    self.decision_sha256, self.evidence_sha256, self.policy_sha256))
                or type(self.optimizer_step) is not int or self.optimizer_step < 0
                or not isinstance(self.retention_reason, str) or not self.retention_reason
                or type(self.step_proof_sha256) is not tuple
                or any(not _is_digest(value) for value in self.step_proof_sha256)
                or not _valid_source_anchors(
                    self.source_anchors, ACCEPTANCE_SCHEMA)
                or (self.source_authority_registry_sha256 is not None
                    and not _is_digest(self.source_authority_registry_sha256))
                or self.schema_version != ACCEPTANCE_SCHEMA):
            _invalid()

    def _public_record(self) -> dict:
        return {name: getattr(self, name) for name in _BINDING_FIELDS}

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical(self._public_record())).hexdigest()

    def to_record(self) -> dict:
        return {**self._public_record(), "binding_sha256": self.digest}

    @classmethod
    def from_record(cls, record) -> "ParsedAcceptedCandidateBinding":
        """Validate a historical v1/v2 record without restoring live authority."""
        if not isinstance(record, dict):
            _invalid()
        schema = record.get("schema_version")
        names = (_LEGACY_FIELDS if schema == LEGACY_ACCEPTANCE_SCHEMA
                 else _V2_BINDING_FIELDS if schema == PREVIOUS_ACCEPTANCE_SCHEMA
                 else _V3_BINDING_FIELDS
                 if schema == PREVIOUS_SOURCE_ACCEPTANCE_SCHEMA
                 else _V4_BINDING_FIELDS
                 if schema == PREVIOUS_DEPENDENCY_ACCEPTANCE_SCHEMA
                 else _BINDING_FIELDS if schema == ACCEPTANCE_SCHEMA else ())
        if not names or set(record) != set(names) | {"binding_sha256"}:
            _invalid()
        if (not isinstance(record["run_id"], str) or not record["run_id"]
                or type(record["generation"]) is not int or record["generation"] < 0
                or type(record["optimizer_step"]) is not int
                or record["optimizer_step"] < 0
                or not isinstance(record["retention_reason"], str)
                or not record["retention_reason"]
                or not isinstance(record["step_proof_sha256"], (tuple, list))
                or any(not _is_digest(value) for value in record["step_proof_sha256"])
                or any(not _is_digest(record[name]) for name in (
                    "candidate_identity_sha256", "feature_sha256",
                    "decision_sha256"))):
            _invalid()
        if names in (_V2_BINDING_FIELDS, _V4_BINDING_FIELDS, _BINDING_FIELDS) and any(
                not _is_digest(record[name]) for name in (
                    "parent_candidate_identity_sha256", "evidence_sha256",
                    "policy_sha256")):
            _invalid()
        if names in (_V3_BINDING_FIELDS, _V4_BINDING_FIELDS, _BINDING_FIELDS):
            anchors = _normalize_source_anchors(record.get("source_anchors"), schema)
            if not _valid_source_anchors(anchors, schema):
                _invalid()
        if (names == _BINDING_FIELDS
                and record["source_authority_registry_sha256"] is not None
                and not _is_digest(record["source_authority_registry_sha256"])):
            _invalid()
        payload = {name: record[name] for name in names}
        if names in (_V3_BINDING_FIELDS, _V4_BINDING_FIELDS, _BINDING_FIELDS):
            payload["source_anchors"] = anchors
        if record["binding_sha256"] != hashlib.sha256(_canonical(payload)).hexdigest():
            _invalid()
        payload["step_proof_sha256"] = tuple(payload["step_proof_sha256"])
        return ParsedAcceptedCandidateBinding(payload)


@dataclass(frozen=True)
class ParsedAcceptedCandidateBinding:
    """Verified custody evidence, never accepted as a live publication token."""
    fields: dict

    def __getattr__(self, name: str):
        if (name in _LEGACY_FIELDS or name in _V2_BINDING_FIELDS
                or name in _V3_BINDING_FIELDS or name in _V4_BINDING_FIELDS
                or name in _BINDING_FIELDS):
            return self.fields.get(name)
        raise AttributeError(name)

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical(self.fields)).hexdigest()

    def to_record(self) -> dict:
        return {**self.fields, "binding_sha256": self.digest}


_require_issued_binding, _raw_issue_binding = _new_binding_owner()


def _make_acceptance_minter(raw_issue):
    def mint_acceptance_binding(
            decision: CandidateRetentionDecision, state, *,
            run_id: str, generation: int, feature_sha256: str,
            training_authorities=None,
            source_authority_registry_sha256: str | None = None,
    ) -> AcceptedCandidateBinding:
        """Bind a C05-approved decision to the exact B12 optimizer state."""
        from .atlas_retention_decision import _require_issued_decision

        state_digest = candidate_identity_digest(state)
        if type(decision) is not CandidateRetentionDecision:
            _invalid()
        _require_issued_decision(decision)
        decision.__post_init__()
        if (not decision.accepted or decision.candidate_generation != state_digest):
            _invalid()
        source_anchors = _source_anchors(training_authorities, state)
        return raw_issue((
            ("run_id", run_id), ("generation", generation),
            ("candidate_identity_sha256", state_digest),
            ("parent_candidate_identity_sha256", decision.parent_generation),
            ("feature_sha256", feature_sha256),
            ("optimizer_step", state.optimizer_step),
            ("retention_reason", decision.reason),
            ("step_proof_sha256", tuple(proof.digest for proof in state.step_proofs)),
            ("decision_sha256", decision.digest),
            ("evidence_sha256", decision.evidence_sha256),
            ("policy_sha256", decision.policy_sha256),
            ("source_anchors", source_anchors),
            ("source_authority_registry_sha256",
             source_authority_registry_sha256),
            ("schema_version", ACCEPTANCE_SCHEMA),
        ))

    return mint_acceptance_binding


mint_acceptance_binding = _make_acceptance_minter(_raw_issue_binding)
del _raw_issue_binding
