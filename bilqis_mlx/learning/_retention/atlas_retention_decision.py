"""C05-owned, custody-bound B13 retention decisions.

The runtime evaluator must execute the stage-authoritative C05 screen.
Caller-provided booleans and historical decision JSON cannot authorize generation
publication. Foundation acquisition authorizes from fixed-school preservation;
fresh/generalization cohorts remain non-authorizing measurements under ADR-134.
"""
from __future__ import annotations

from dataclasses import dataclass

from bilqis_mlx.errors import ErrorBus, SCHOOL
from .atlas_retention_decision_codec import (
    ACCEPTED_DECISION, ACCEPTING_REASON, DECISION_FIELDS, DECISION_SCHEMA,
    LEGACY_DECISION_SCHEMA, PREVIOUS_BASELINE_DECISION_SCHEMA,
    PREVIOUS_DECISION_SCHEMA, PREVIOUS_SCOPE_DECISION_SCHEMA, REJECTED_DECISION,
    ParsedCandidateRetentionDecision, canonical as _canonical,
    invalid as _invalid, parse_record, valid_baseline_coverage,
    valid_blocking_score_budget as _valid_blocking_score_budget,
    valid_digest as _digest,
)


def _new_decision_owner():
    """Track live C05 decisions by owner-issued object identity, not a token."""
    issued = {}
    generation_authority = {}
    baseline_ledger_sha256 = {}

    def require(value):
        if issued.get(id(value)) is not value:
            _invalid()
        return value

    def issue(values, *, generation_authority_sha256=None,
              expected_baseline_ledger_sha256=None):
        decision = object.__new__(CandidateRetentionDecision)
        for name, value in values:
            object.__setattr__(decision, name, value)
        issued[id(decision)] = decision
        generation_authority[id(decision)] = generation_authority_sha256
        baseline_ledger_sha256[id(decision)] = expected_baseline_ledger_sha256
        decision.__post_init__()
        return decision

    def require_generation_authority(value, expected):
        require(value)
        if (not _digest(expected)
                or generation_authority.get(id(value)) != expected):
            _invalid()
        return value

    def issued_generation_authority(value):
        return generation_authority.get(id(value))

    def issued_baseline_ledger_sha256(value):
        return baseline_ledger_sha256.get(id(value))

    def rebind_generation_authority(value, previous, expected):
        """Advance one live decision from its screened candidate to final B13 custody."""
        require(value)
        if (not _digest(previous) or not _digest(expected)
                or generation_authority.get(id(value)) != previous):
            _invalid()
        generation_authority[id(value)] = expected
        return value

    return (require, require_generation_authority, issued_generation_authority,
            issued_baseline_ledger_sha256, rebind_generation_authority, issue)
@dataclass(frozen=True)
class CandidateRetentionDecision:
    """Live token issued only after C05 runs its stage-authoritative evaluation."""

    decision: str
    reason: str
    parent_generation: str
    candidate_generation: str
    evidence_sha256: str
    policy_sha256: str
    blocking_capability: str | None = None
    blocking_scope: str | None = None
    baseline_coverage: dict | None = None
    evaluated_capability_ids: tuple[str, ...] = ()
    retention_protection_plan_sha256: str | None = None
    broad_certification_trigger: str | None = None
    blocking_score_budget: tuple[str, int, int, int, int] | None = None
    schema_version: str = DECISION_SCHEMA

    def __post_init__(self) -> None:
        _require_issued_decision(self)
        if (self.decision not in {ACCEPTED_DECISION, REJECTED_DECISION}
                or not isinstance(self.reason, str) or not self.reason
                or (self.decision == ACCEPTED_DECISION)
                != (self.reason == ACCEPTING_REASON)
                or any(not _digest(value) for value in (
                    self.parent_generation, self.candidate_generation,
                    self.evidence_sha256, self.policy_sha256))
                or (self.blocking_capability is not None
                    and (not isinstance(self.blocking_capability, str)
                         or not self.blocking_capability))
                or (self.blocking_scope is not None
                    and (not isinstance(self.blocking_scope, str)
                         or not self.blocking_scope))
                or (self.baseline_coverage is not None
                    and not valid_baseline_coverage(self.baseline_coverage))
                or not isinstance(self.evaluated_capability_ids, tuple)
                or any(not isinstance(item, str) or not item
                       for item in self.evaluated_capability_ids)
                or len(set(self.evaluated_capability_ids))
                != len(self.evaluated_capability_ids)
                or (self.retention_protection_plan_sha256 is not None
                    and not _digest(self.retention_protection_plan_sha256))
                or (self.broad_certification_trigger is not None
                    and (not isinstance(self.broad_certification_trigger, str)
                         or not self.broad_certification_trigger))
                or (self.retention_protection_plan_sha256 is not None
                    and self.broad_certification_trigger is not None)
                or not _valid_blocking_score_budget(self.blocking_score_budget)
                or self.schema_version != DECISION_SCHEMA):
            _invalid()

    @property
    def accepted(self) -> bool:
        return self.decision == ACCEPTED_DECISION

    def _public_record(self) -> dict:
        return {name: getattr(self, name) for name in DECISION_FIELDS}

    @property
    def digest(self) -> str:
        import hashlib
        return hashlib.sha256(_canonical(self._public_record())).hexdigest()

    def to_record(self) -> dict:
        return {**self._public_record(), "decision_sha256": self.digest}

    @classmethod
    def from_record(cls, record) -> "ParsedCandidateRetentionDecision":
        """Parse historical evidence without granting live issuer authority."""
        return parse_record(record)


def decide_candidate_retention(
        *, parent_solver, candidate_solver, target_capability, policy, cohorts,
        parent_state, candidate_state) -> CandidateRetentionDecision:
    """Fail closed until Factory/source owns the complete C05 screen.

    C05 currently provides owner-run evaluation, but these arguments still
    include caller-supplied solvers, policy and cohorts. Their self-consistency
    cannot establish source provenance. Only an integrated Factory/backend
    evaluator may eventually authorize live B13 acceptance.
    """
    ErrorBus.Raise(
        SCHOOL.MODEL_TOPOLOGY.INVALID,
        reason="BAMF_C05_SOURCE_OWNER_REQUIRED",
    )


(_require_issued_decision, _require_issued_decision_generation_authority,
 _issued_decision_generation_authority, _issued_decision_baseline_ledger_sha256,
 _rebind_issued_decision_generation_authority,
 _raw_issue_decision) = _new_decision_owner()


from .atlas_retention_decision_factory import make_factory_retention_issuer
issue_factory_retention_decision = make_factory_retention_issuer(_raw_issue_decision)
del _raw_issue_decision
