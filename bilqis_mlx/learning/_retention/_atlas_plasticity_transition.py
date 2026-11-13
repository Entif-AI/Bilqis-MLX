"""Persisted proof for the one-way FOUNDATION to ADAPTIVE transition."""
from __future__ import annotations

from dataclasses import dataclass

from bilqis_mlx.errors import ErrorBus, SCHOOL


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)

POLICY_VERSION = "bilqis.mlx.plasticity-policy/v1"
POLICY_STATE_SCHEMA = "bilqis.mlx.plasticity-policy-state/v1"
TRANSITIONED_POLICY_VERSION = "bilqis.mlx.plasticity-policy/v2"
TRANSITIONED_POLICY_STATE_SCHEMA = "bilqis.mlx.plasticity-policy-state/v2"
MODE_TRANSITION_SCHEMA = "bilqis.mlx.plasticity-mode-transition/v1"
FOUNDATION_MODE = "FOUNDATION"
ADAPTIVE_MODE = "ADAPTIVE"
FAST_UPDATE = "FAST"
FULL_UPDATE = "FULL"
ACCEPTED_FAST_INTERVAL = 8
_POLICY_RECORD_FIELDS = frozenset((
    "schema_version", "policy_version", "mode", "accepted_fast_since_full", "row_ages"))
_POLICY_RECORD_FIELDS_V2 = _POLICY_RECORD_FIELDS | {"mode_transition"}
_AGE_RECORD_FIELDS = frozenset(("bank_index", "row_index", "accepted_age", "schema_version"))
_MODE_TRANSITION_FIELDS = frozenset((
    "run_id", "parent_generation", "candidate_generation",
    "candidate_identity_sha256", "optimizer_step", "decision_sha256",
    "initial_factory_release_sha256", "foundation_capability_ids",
    "promotion_evidence_sha256", "assessment_epoch", "outcome",
    "carried_debt", "promotion_receipt_sha256", "schema_version",
))


def _is_digest(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


@dataclass(frozen=True)
class ModeTransition:
    """Persisted B09 proof that one accepted promotion changed cadence mode."""

    run_id: str
    parent_generation: int
    candidate_generation: int
    candidate_identity_sha256: str
    optimizer_step: int
    decision_sha256: str
    initial_factory_release_sha256: str
    foundation_capability_ids: tuple[str, ...]
    promotion_evidence_sha256: str
    assessment_epoch: int
    outcome: str
    carried_debt: tuple[str, ...]
    promotion_receipt_sha256: str
    schema_version: str = MODE_TRANSITION_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.run_id, str) or not self.run_id
                or type(self.parent_generation) is not int
                or self.parent_generation < 0
                or self.candidate_generation != self.parent_generation + 1
                or type(self.optimizer_step) is not int or self.optimizer_step < 0
                or any(not _is_digest(value) for value in (
                    self.candidate_identity_sha256, self.decision_sha256,
                    self.initial_factory_release_sha256,
                    self.promotion_evidence_sha256,
                    self.promotion_receipt_sha256))
                or type(self.foundation_capability_ids) is not tuple
                or not self.foundation_capability_ids
                or len(set(self.foundation_capability_ids))
                != len(self.foundation_capability_ids)
                or any(not isinstance(item, str) or not item
                       for item in self.foundation_capability_ids)
                or type(self.assessment_epoch) is not int
                or self.assessment_epoch < 0
                or self.outcome not in {"PROMOTED", "PROMOTED_WITH_DEBT"}
                or type(self.carried_debt) is not tuple
                or len(set(self.carried_debt)) != len(self.carried_debt)
                or any(not isinstance(item, str) or not item
                       for item in self.carried_debt)
                or (self.outcome == "PROMOTED" and self.carried_debt)
                or self.schema_version != MODE_TRANSITION_SCHEMA):
            _invalid()

    def to_record(self) -> dict:
        self.__post_init__()
        return {
            "run_id": self.run_id,
            "parent_generation": self.parent_generation,
            "candidate_generation": self.candidate_generation,
            "candidate_identity_sha256": self.candidate_identity_sha256,
            "optimizer_step": self.optimizer_step,
            "decision_sha256": self.decision_sha256,
            "initial_factory_release_sha256": self.initial_factory_release_sha256,
            "foundation_capability_ids": list(self.foundation_capability_ids),
            "promotion_evidence_sha256": self.promotion_evidence_sha256,
            "assessment_epoch": self.assessment_epoch,
            "outcome": self.outcome,
            "carried_debt": list(self.carried_debt),
            "promotion_receipt_sha256": self.promotion_receipt_sha256,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_record(cls, record: object) -> "ModeTransition":
        if (type(record) is not dict or set(record) != _MODE_TRANSITION_FIELDS
                or type(record["foundation_capability_ids"]) is not list
                or type(record["carried_debt"]) is not list):
            _invalid()
        return cls(
            run_id=record["run_id"],
            parent_generation=record["parent_generation"],
            candidate_generation=record["candidate_generation"],
            candidate_identity_sha256=record["candidate_identity_sha256"],
            optimizer_step=record["optimizer_step"],
            decision_sha256=record["decision_sha256"],
            initial_factory_release_sha256=record["initial_factory_release_sha256"],
            foundation_capability_ids=tuple(record["foundation_capability_ids"]),
            promotion_evidence_sha256=record["promotion_evidence_sha256"],
            assessment_epoch=record["assessment_epoch"],
            outcome=record["outcome"],
            carried_debt=tuple(record["carried_debt"]),
            promotion_receipt_sha256=record["promotion_receipt_sha256"],
            schema_version=record["schema_version"],
        )
