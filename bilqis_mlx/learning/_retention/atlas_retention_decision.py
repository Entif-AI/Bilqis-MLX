"""C05-owned, custody-bound B13 retention decisions.

The runtime evaluator must execute the complete paired screen. Caller-provided
booleans and historical decision JSON cannot authorize generation publication.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from bilqis_mlx.errors import ErrorBus, SCHOOL

LEGACY_DECISION_SCHEMA = "bilqis.mlx.candidate-retention-decision/v1"
DECISION_SCHEMA = "bilqis.mlx.candidate-retention-decision/v2"
ACCEPTED_DECISION = "PROVISIONAL"
REJECTED_DECISION = "REJECT"
ACCEPTING_REASON = "PAIRED_SCREEN_WITHIN_BUDGET"
_DECISION_ISSUER = object()
_DECISION_FIELDS = (
    "decision", "reason", "parent_generation", "candidate_generation",
    "evidence_sha256", "policy_sha256", "schema_version",
)
_LEGACY_FIELDS = (
    "decision", "reason", "target_gain", "protected_net_gain", "schema_version",
)


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _digest(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


@dataclass(frozen=True)
class CandidateRetentionDecision:
    """Live token issued only after C05 runs its complete paired evaluation."""

    decision: str
    reason: str
    parent_generation: str
    candidate_generation: str
    evidence_sha256: str
    policy_sha256: str
    schema_version: str = DECISION_SCHEMA
    _issuance: object = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if (getattr(self, "_issuance", None) is not _DECISION_ISSUER
                or self.decision not in {ACCEPTED_DECISION, REJECTED_DECISION}
                or not isinstance(self.reason, str) or not self.reason
                or (self.decision == ACCEPTED_DECISION)
                != (self.reason == ACCEPTING_REASON)
                or any(not _digest(value) for value in (
                    self.parent_generation, self.candidate_generation,
                    self.evidence_sha256, self.policy_sha256))
                or self.schema_version != DECISION_SCHEMA):
            _invalid()

    @property
    def accepted(self) -> bool:
        return self.decision == ACCEPTED_DECISION

    def _public_record(self) -> dict:
        return {name: getattr(self, name) for name in _DECISION_FIELDS}

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical(self._public_record())).hexdigest()

    def to_record(self) -> dict:
        return {**self._public_record(), "decision_sha256": self.digest}

    @classmethod
    def from_record(cls, record) -> "ParsedCandidateRetentionDecision":
        """Parse v1/v2 evidence for inspection without granting issuer authority."""
        if not isinstance(record, dict):
            _invalid()
        names = (_LEGACY_FIELDS if record.get("schema_version") == LEGACY_DECISION_SCHEMA
                 else _DECISION_FIELDS if record.get("schema_version") == DECISION_SCHEMA
                 else ())
        if not names or set(record) != set(names) | {"decision_sha256"}:
            _invalid()
        if (record["decision"] not in {ACCEPTED_DECISION, REJECTED_DECISION}
                or not isinstance(record["reason"], str) or not record["reason"]
                or (record["decision"] == ACCEPTED_DECISION)
                != (record["reason"] == ACCEPTING_REASON)):
            _invalid()
        if names == _LEGACY_FIELDS:
            if (type(record["target_gain"]) is not bool
                    or type(record["protected_net_gain"]) is not int):
                _invalid()
        elif any(not _digest(record[name]) for name in (
                "parent_generation", "candidate_generation",
                "evidence_sha256", "policy_sha256")):
            _invalid()
        payload = {name: record[name] for name in names}
        if record["decision_sha256"] != hashlib.sha256(_canonical(payload)).hexdigest():
            _invalid()
        return ParsedCandidateRetentionDecision(payload)


@dataclass(frozen=True)
class ParsedCandidateRetentionDecision:
    """Historical evidence is not a live acceptance capability."""
    fields: dict

    @property
    def decision(self) -> str:
        return self.fields["decision"]

    @property
    def reason(self) -> str:
        return self.fields["reason"]

    @property
    def accepted(self) -> bool:
        return self.decision == ACCEPTED_DECISION

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical(self.fields)).hexdigest()

    def to_record(self) -> dict:
        return {**self.fields, "decision_sha256": self.digest}


def decide_candidate_retention(
        *, parent_solver, candidate_solver, target_capability, policy, cohorts,
        parent_state, candidate_state) -> CandidateRetentionDecision:
    """Run C05's evaluator using custody-derived candidate-state identities.

    A caller cannot issue a live decision using primitive measurements or by
    retargeting an existing PairedRetentionEvidence value.
    """
    from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
    from bilqis_mlx.learning.atlas_candidate import CandidateState
    from bilqis_mlx.runtime.capability_retention import (
        DecisionStatus, evaluate_retention_candidate,
    )

    if type(parent_state) is not CandidateState or type(candidate_state) is not CandidateState:
        _invalid()
    parent_id = candidate_identity_digest(parent_state)
    candidate_id = candidate_identity_digest(candidate_state)
    result = evaluate_retention_candidate(
        parent_solver, candidate_solver, target_capability, policy, cohorts,
        parent_id, candidate_id,
    )
    if (result.parent_generation != parent_id
            or result.candidate_generation != candidate_id):
        _invalid()
    decision = object.__new__(CandidateRetentionDecision)
    for name, value in (
            ("decision", ACCEPTED_DECISION
             if result.status is DecisionStatus.ELIGIBLE else REJECTED_DECISION),
            ("reason", result.reason),
            ("parent_generation", parent_id),
            ("candidate_generation", candidate_id),
            ("evidence_sha256", result.evidence_sha256),
            ("policy_sha256", result.policy_sha256),
            ("schema_version", DECISION_SCHEMA),
            ("_issuance", _DECISION_ISSUER)):
        object.__setattr__(decision, name, value)
    decision.__post_init__()
    return decision
