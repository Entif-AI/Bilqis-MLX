"""Finite mapping-admission policy for normalized crosswalk/bridge state (#62)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

from .errors import ProfileError


POLICY_SCHEMA = "bilqis.skos.mapping-admission/v1"
DEFAULT_POLICY_PATH = Path(__file__).with_name("mapping_admission_table.json")
ABSENT = "__NOT_PRESENT__"
KEY_FIELDS = (
    "record_kind",
    "relation_state",
    "equivalence_state",
    "mapping_disposition",
    "review_state",
    "registry_state",
    "source_era",
    "target_kind",
    "source_match_state",
)
OUTCOMES = frozenset(
    {
        "EMIT_EXACT",
        "EMIT_CLOSE",
        "EMIT_BROAD",
        "EMIT_NARROW",
        "EMIT_RELATED",
        "HOLD",
        "REJECT",
        "UNSUPPORTED",
    }
)
EMIT_OUTCOMES = frozenset(outcome for outcome in OUTCOMES if outcome.startswith("EMIT_"))
COMMENTARY_FIELDS = frozenset(
    {
        "bilqis_source_definition",
        "new_ithkuil_bridge",
        "official_locus",
        "semantic_differential",
        "source_grounded_semantic_meaning",
        "semantic_caution_or_dependencies",
    }
)

_FIELD_MAPS = {
    "crosswalk": {
        "relation_state": "relation_type",
        "equivalence_state": "equivalence_state",
        "mapping_disposition": "mapping_disposition",
        "review_state": "crosswalk_state",
        "registry_state": None,
        "source_era": "source_era",
        "target_kind": "target_kind",
        "source_match_state": "source_match_state",
    },
    "bridge": {
        "relation_state": "link_type",
        "equivalence_state": None,
        "mapping_disposition": None,
        "review_state": "bridge_epistemic_state",
        "registry_state": "registry_state_raw",
        "source_era": "source_era",
        "target_kind": "target_kind",
        "source_match_state": "source_match_state",
    },
}


@dataclass(frozen=True)
class AdmissionRule:
    key: tuple[str, ...]
    outcome: str
    reason_code: str | None


@dataclass(frozen=True)
class NormalizedAdmission:
    predicate: str
    review_state: str
    outcome: str


@dataclass(frozen=True)
class PolicyTable:
    schema: str
    table_version: str
    key_fields: tuple[str, ...]
    rules: tuple[AdmissionRule, ...]
    normalized_admissions: tuple[NormalizedAdmission, ...]


@dataclass(frozen=True)
class AdmissionDecision:
    key: tuple[str, ...]
    outcome: str
    reason_code: str | None

    @property
    def emitting(self) -> bool:
        return self.outcome in EMIT_OUTCOMES


def _required_string(value: object, code: str, *details: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProfileError(code, *details)
    return value


def mapping_key(record_kind: str, row: Mapping[str, str]) -> tuple[str, ...]:
    """Return the exact finite policy key; prose/commentary fields are excluded."""
    field_map = _FIELD_MAPS.get(record_kind)
    if field_map is None:
        raise ProfileError("MAPPING_POLICY_RECORD_KIND_UNSUPPORTED", record_kind)
    values = [record_kind]
    for key_field in KEY_FIELDS[1:]:
        source_field = field_map[key_field]
        if source_field is None:
            values.append(ABSENT)
            continue
        if source_field not in row:
            raise ProfileError("MAPPING_POLICY_INPUT_FIELD_MISSING", record_kind, source_field)
        values.append(_required_string(row[source_field], "MAPPING_POLICY_INPUT_FIELD_INVALID", record_kind, source_field))
    return tuple(values)


def _rule_from_json(raw: Mapping[str, object]) -> AdmissionRule:
    if set(raw) != {"key", "outcome", "reason_code"}:
        raise ProfileError("MAPPING_POLICY_RULE_SCHEMA_INVALID")
    key_raw = raw["key"]
    if not isinstance(key_raw, dict) or set(key_raw) != set(KEY_FIELDS):
        raise ProfileError("MAPPING_POLICY_RULE_KEY_SCHEMA_INVALID")
    key = tuple(_required_string(key_raw[field], "MAPPING_POLICY_RULE_KEY_INVALID", field) for field in KEY_FIELDS)
    if any(value in {"*", "ANY", "__ANY__"} for value in key):
        raise ProfileError("MAPPING_POLICY_WILDCARD_FORBIDDEN", *key)
    outcome = _required_string(raw["outcome"], "MAPPING_POLICY_OUTCOME_INVALID")
    if outcome not in OUTCOMES or outcome == "UNSUPPORTED":
        raise ProfileError("MAPPING_POLICY_OUTCOME_INVALID", outcome)
    reason = raw["reason_code"]
    if outcome in EMIT_OUTCOMES:
        if reason is not None:
            raise ProfileError("MAPPING_POLICY_EMIT_REASON_FORBIDDEN", outcome)
        dimensions = dict(zip(KEY_FIELDS, key))
        if dimensions["target_kind"] != "concept" or dimensions["source_era"] != "current_snapshot":
            raise ProfileError("MAPPING_POLICY_UNSAFE_EMIT_RULE", dimensions["target_kind"], dimensions["source_era"])
    else:
        reason = _required_string(reason, "MAPPING_POLICY_REASON_REQUIRED", outcome)
    return AdmissionRule(key, outcome, reason)


def _normalized_from_json(raw: Mapping[str, object]) -> NormalizedAdmission:
    if set(raw) != {"predicate", "review_state", "outcome"}:
        raise ProfileError("MAPPING_NORMALIZED_FIXTURE_SCHEMA_INVALID")
    predicate = _required_string(raw["predicate"], "MAPPING_NORMALIZED_PREDICATE_INVALID")
    review_state = _required_string(raw["review_state"], "MAPPING_NORMALIZED_REVIEW_STATE_INVALID")
    outcome = _required_string(raw["outcome"], "MAPPING_NORMALIZED_OUTCOME_INVALID")
    if outcome not in EMIT_OUTCOMES:
        raise ProfileError("MAPPING_NORMALIZED_OUTCOME_INVALID", outcome)
    expected = {
        "exactMatch": ("admitted_exact_equivalence", "EMIT_EXACT"),
        "closeMatch": ("admitted_close_match", "EMIT_CLOSE"),
        "broadMatch": ("admitted_broad_match", "EMIT_BROAD"),
        "narrowMatch": ("admitted_narrow_match", "EMIT_NARROW"),
        "relatedMatch": ("admitted_related_match", "EMIT_RELATED"),
    }
    if expected.get(predicate) != (review_state, outcome):
        raise ProfileError("MAPPING_NORMALIZED_STRENGTH_MISMATCH", predicate, review_state, outcome)
    return NormalizedAdmission(predicate, review_state, outcome)


def load_policy(path: str | Path = DEFAULT_POLICY_PATH) -> PolicyTable:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema") != POLICY_SCHEMA:
        raise ProfileError("MAPPING_POLICY_SCHEMA_UNSUPPORTED", str(raw.get("schema")))
    version = _required_string(raw.get("table_version"), "MAPPING_POLICY_VERSION_REQUIRED")
    if tuple(raw.get("key_fields", ())) != KEY_FIELDS:
        raise ProfileError("MAPPING_POLICY_KEY_FIELDS_INVALID")
    if raw.get("normalized_caution_dimensions") != []:
        raise ProfileError("MAPPING_POLICY_CAUTION_DIMENSIONS_UNDECLARED")
    if set(raw.get("commentary_excluded", ())) != COMMENTARY_FIELDS:
        raise ProfileError("MAPPING_POLICY_COMMENTARY_BOUNDARY_INVALID")
    rules = tuple(_rule_from_json(item) for item in raw.get("rules", ()))
    normalized = tuple(_normalized_from_json(item) for item in raw.get("synthetic_normalized_admissions", ()))
    table = PolicyTable(POLICY_SCHEMA, version, KEY_FIELDS, rules, normalized)
    validate_policy(table)
    return table


def validate_policy(table: PolicyTable) -> None:
    if table.schema != POLICY_SCHEMA or table.key_fields != KEY_FIELDS:
        raise ProfileError("MAPPING_POLICY_SCHEMA_UNSUPPORTED", table.schema)
    seen: set[tuple[str, ...]] = set()
    for rule in table.rules:
        if rule.key in seen:
            raise ProfileError("MAPPING_POLICY_DUPLICATE_RULE", *rule.key)
        seen.add(rule.key)
    normalized_seen: set[tuple[str, str]] = set()
    for item in table.normalized_admissions:
        key = (item.predicate, item.review_state)
        if key in normalized_seen:
            raise ProfileError("MAPPING_NORMALIZED_DUPLICATE_RULE", *key)
        normalized_seen.add(key)


def decide_key(key: tuple[str, ...], table: PolicyTable) -> AdmissionDecision:
    matches = tuple(rule for rule in table.rules if rule.key == key)
    if not matches:
        return AdmissionDecision(key, "UNSUPPORTED", "MAPPING_POLICY_NO_MATCH")
    if len(matches) != 1:
        raise ProfileError("MAPPING_POLICY_MULTIPLE_MATCHES", *key)
    rule = matches[0]
    return AdmissionDecision(key, rule.outcome, rule.reason_code)


def decide_row(record_kind: str, row: Mapping[str, str], table: PolicyTable) -> AdmissionDecision:
    return decide_key(mapping_key(record_kind, row), table)


def decide_normalized(predicate: str, review_state: str, table: PolicyTable) -> AdmissionDecision:
    key = (predicate, review_state)
    matches = tuple(
        item for item in table.normalized_admissions
        if (item.predicate, item.review_state) == key
    )
    if not matches:
        return AdmissionDecision(key, "UNSUPPORTED", "MAPPING_NORMALIZED_STATE_UNSUPPORTED")
    if len(matches) != 1:
        raise ProfileError("MAPPING_NORMALIZED_MULTIPLE_MATCHES", *key)
    return AdmissionDecision(key, matches[0].outcome, None)


def coverage_report(
    crosswalk_rows: Iterable[Mapping[str, str]],
    bridge_rows: Iterable[Mapping[str, str]],
    table: PolicyTable,
) -> dict[str, object]:
    crosswalk = tuple(crosswalk_rows)
    bridges = tuple(bridge_rows)
    keyed_rows = (
        tuple(("crosswalk", row, mapping_key("crosswalk", row)) for row in crosswalk)
        + tuple(("bridge", row, mapping_key("bridge", row)) for row in bridges)
    )
    observed_keys = {key for _, _, key in keyed_rows}
    rule_keys = {rule.key for rule in table.rules}
    missing = sorted(observed_keys - rule_keys)
    extra = sorted(rule_keys - observed_keys)
    if missing:
        raise ProfileError("MAPPING_POLICY_OBSERVED_KEY_UNCOVERED", repr(missing[0]))
    if extra:
        raise ProfileError("MAPPING_POLICY_STALE_RULE", repr(extra[0]))

    decisions = tuple(decide_key(key, table) for _, _, key in keyed_rows)
    outcomes = Counter(decision.outcome for decision in decisions)
    reasons = Counter(decision.reason_code for decision in decisions if decision.reason_code)
    unique_by_kind = Counter(key[0] for key in observed_keys)
    canonical_rows = [
        {**dict(zip(KEY_FIELDS, rule.key)), "outcome": rule.outcome, "reason_code": rule.reason_code}
        for rule in sorted(table.rules, key=lambda item: item.key)
    ]
    digest = hashlib.sha256(
        json.dumps(canonical_rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    normalized = {
        item.outcome: {"predicate": item.predicate, "review_state": item.review_state}
        for item in sorted(table.normalized_admissions, key=lambda item: item.outcome)
    }
    return {
        "schema": "bilqis.skos.mapping-admission-coverage/v1",
        "table_version": table.table_version,
        "rows": {"crosswalk": len(crosswalk), "bridge": len(bridges), "total": len(keyed_rows)},
        "unique_policy_keys": {
            "crosswalk": unique_by_kind["crosswalk"],
            "bridge": unique_by_kind["bridge"],
            "total": len(observed_keys),
        },
        "outcomes": dict(sorted(outcomes.items())),
        "reasons": dict(sorted(reasons.items())),
        "synthetic_normalized_admissions": normalized,
        "policy_digest_sha256": digest,
    }
