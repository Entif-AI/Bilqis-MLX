"""Historical codec and validation helpers for C05 retention decisions."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from bilqis_mlx.errors import ErrorBus, SCHOOL

LEGACY_DECISION_SCHEMA = "bilqis.mlx.candidate-retention-decision/v1"
PREVIOUS_DECISION_SCHEMA = "bilqis.mlx.candidate-retention-decision/v2"
PREVIOUS_BASELINE_DECISION_SCHEMA = "bilqis.mlx.candidate-retention-decision/v3"
PREVIOUS_SCOPE_DECISION_SCHEMA = "bilqis.mlx.candidate-retention-decision/v4"
DECISION_SCHEMA = "bilqis.mlx.candidate-retention-decision/v5"
BLOCKING_SCORE_BUDGET_WIDTH = 5
ACCEPTED_DECISION = "PROVISIONAL"
REJECTED_DECISION = "REJECT"
ACCEPTING_REASON = "PAIRED_SCREEN_WITHIN_BUDGET"
V2_FIELDS = (
    "decision", "reason", "parent_generation", "candidate_generation",
    "evidence_sha256", "policy_sha256", "schema_version",
)
V3_FIELDS = (
    "decision", "reason", "parent_generation", "candidate_generation",
    "evidence_sha256", "policy_sha256", "blocking_capability",
    "blocking_scope", "baseline_coverage", "schema_version",
)
V4_FIELDS = (
    *V3_FIELDS[:-1], "evaluated_capability_ids",
    "retention_protection_plan_sha256", "broad_certification_trigger",
    "schema_version",
)
DECISION_FIELDS = (*V4_FIELDS[:-1], "blocking_score_budget", "schema_version")
LEGACY_FIELDS = (
    "decision", "reason", "target_gain", "protected_net_gain", "schema_version",
)


def invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def canonical(value) -> bytes:
    return (json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False) + "\n").encode("utf-8")


def valid_digest(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def valid_blocking_score_budget(value) -> bool:
    if value is None:
        return True
    if not isinstance(value, (list, tuple)) or len(value) != BLOCKING_SCORE_BUDGET_WIDTH:
        return False
    capability, before, after, total, allowed = value
    return (isinstance(capability, str) and bool(capability)
            and all(type(number) is int for number in (before, after, total, allowed))
            and 0 <= before <= total and 0 <= after <= total
            and 0 <= allowed <= total)


def valid_baseline_coverage(record) -> bool:
    if record is None:
        return True
    try:
        from bilqis_mlx.runtime.baseline.currentness import BaselineCoverage
        BaselineCoverage.from_record(record)
    except Exception:
        return False
    return True


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
        return hashlib.sha256(canonical(self.fields)).hexdigest()

    def to_record(self) -> dict:
        return {**self.fields, "decision_sha256": self.digest}


def parse_record(record) -> ParsedCandidateRetentionDecision:
    if not isinstance(record, dict):
        invalid()
    schema = record.get("schema_version")
    names = (
        LEGACY_FIELDS if schema == LEGACY_DECISION_SCHEMA
        else V2_FIELDS if schema == PREVIOUS_DECISION_SCHEMA
        else V3_FIELDS if schema == PREVIOUS_BASELINE_DECISION_SCHEMA
        else V4_FIELDS if schema == PREVIOUS_SCOPE_DECISION_SCHEMA
        else DECISION_FIELDS if schema == DECISION_SCHEMA else ()
    )
    if not names or set(record) != set(names) | {"decision_sha256"}:
        invalid()
    if (record["decision"] not in {ACCEPTED_DECISION, REJECTED_DECISION}
            or not isinstance(record["reason"], str) or not record["reason"]
            or (record["decision"] == ACCEPTED_DECISION)
            != (record["reason"] == ACCEPTING_REASON)):
        invalid()
    if names == LEGACY_FIELDS:
        if type(record["target_gain"]) is not bool or type(record["protected_net_gain"]) is not int:
            invalid()
    elif any(not valid_digest(record[name]) for name in (
            "parent_generation", "candidate_generation", "evidence_sha256",
            "policy_sha256")):
        invalid()
    if names in {V3_FIELDS, DECISION_FIELDS}:
        if ((record["blocking_capability"] is not None
             and (not isinstance(record["blocking_capability"], str)
                  or not record["blocking_capability"]))
                or (record["blocking_scope"] is not None
                    and (not isinstance(record["blocking_scope"], str)
                         or not record["blocking_scope"]))
                or not valid_baseline_coverage(record["baseline_coverage"])):
            invalid()
    if names in {V4_FIELDS, DECISION_FIELDS}:
        evaluated = record["evaluated_capability_ids"]
        if (not isinstance(evaluated, (list, tuple))
                or any(not isinstance(item, str) or not item for item in evaluated)
                or len(set(evaluated)) != len(evaluated)
                or (record["retention_protection_plan_sha256"] is not None
                    and not valid_digest(record["retention_protection_plan_sha256"]))
                or (record["broad_certification_trigger"] is not None
                    and (not isinstance(record["broad_certification_trigger"], str)
                         or not record["broad_certification_trigger"]))
                or (record["retention_protection_plan_sha256"] is not None
                    and record["broad_certification_trigger"] is not None)):
            invalid()
    if names == DECISION_FIELDS and not valid_blocking_score_budget(
            record["blocking_score_budget"]):
        invalid()
    payload = {name: record[name] for name in names}
    if record["decision_sha256"] != hashlib.sha256(canonical(payload)).hexdigest():
        invalid()
    return ParsedCandidateRetentionDecision(payload)
