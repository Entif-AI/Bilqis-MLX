"""Atlas retention decision owner.

The owner evaluates the measured retention evidence with the repository's
authoritative precedence and issues the decision. Only an owner-issued accepted
decision can mint an acceptance binding, so a caller cannot assert that
retention accepted its own candidate.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.retention_policy import retention_reason

DECISION_SCHEMA = "bilqis.mlx.candidate-retention-decision/v1"
ACCEPTED_DECISION = "PROVISIONAL"
REJECTED_DECISION = "REJECT"
ACCEPTING_REASON = "PAIRED_SCREEN_WITHIN_BUDGET"
_DECISION_ISSUER = object()


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


@dataclass(frozen=True)
class CandidateRetentionDecision:
    """One retention decision issued by the retention decision owner."""

    decision: str
    reason: str
    target_gain: bool
    protected_net_gain: int
    schema_version: str = DECISION_SCHEMA
    _issuance: object = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if getattr(self, "_issuance", None) is not _DECISION_ISSUER:
            _invalid()
        if (self.decision not in {ACCEPTED_DECISION, REJECTED_DECISION}
                or not isinstance(self.reason, str) or not self.reason
                or type(self.target_gain) is not bool
                or type(self.protected_net_gain) is not int
                or self.schema_version != DECISION_SCHEMA):
            _invalid()
        if (self.decision == ACCEPTED_DECISION) != (self.reason == ACCEPTING_REASON):
            _invalid()

    @property
    def accepted(self) -> bool:
        return self.decision == ACCEPTED_DECISION

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical({
            "decision": self.decision, "reason": self.reason,
            "target_gain": self.target_gain,
            "protected_net_gain": self.protected_net_gain,
            "schema_version": self.schema_version})).hexdigest()

    def to_record(self) -> dict:
        return {
            "decision": self.decision, "reason": self.reason,
            "target_gain": self.target_gain,
            "protected_net_gain": self.protected_net_gain,
            "schema_version": self.schema_version, "decision_sha256": self.digest,
        }

    @classmethod
    def from_record(cls, record) -> "ParsedCandidateRetentionDecision":
        """Read a historical decision without restoring live issuer capability."""
        names = ("decision", "reason", "target_gain", "protected_net_gain",
                 "schema_version")
        if not isinstance(record, dict) or set(record) != set(names) | {"decision_sha256"}:
            _invalid()
        decision = object.__new__(ParsedCandidateRetentionDecision)
        for name in names:
            object.__setattr__(decision, name, record[name])
        object.__setattr__(decision, "_issuance", _DECISION_ISSUER)
        decision.__post_init__()
        if record["decision_sha256"] != decision.digest:
            _invalid()
        return decision


class ParsedCandidateRetentionDecision(CandidateRetentionDecision):
    """Verified historical decision; never accepted as a live owner-issued decision."""


def decide_candidate_retention(
        *, no_target_gain: bool, same_grade_net_gain: int,
        fixed_grade_regression: bool, active_grade_regression: bool,
        whole_school_regression: bool, frontier_measured: bool,
        fragile_losses: int, exceeded: bool) -> CandidateRetentionDecision:
    """Evaluate measured retention evidence and issue the retention decision.

    The precedence is the repository's own retention policy owner, so this
    decision uses the same reasons the live trainer applies.
    """
    reason = retention_reason(
        no_target_gain=no_target_gain, same_grade_net_gain=same_grade_net_gain,
        fixed_grade_regression=fixed_grade_regression,
        active_grade_regression=active_grade_regression,
        whole_school_regression=whole_school_regression,
        frontier_measured=frontier_measured, fragile_losses=fragile_losses,
        exceeded=exceeded)
    decision = object.__new__(CandidateRetentionDecision)
    for name, value in (
            ("decision", ACCEPTED_DECISION if reason == ACCEPTING_REASON
             else REJECTED_DECISION),
            ("reason", reason), ("target_gain", not no_target_gain),
            ("protected_net_gain", same_grade_net_gain),
            ("schema_version", DECISION_SCHEMA), ("_issuance", _DECISION_ISSUER)):
        object.__setattr__(decision, name, value)
    decision.__post_init__()
    return decision
