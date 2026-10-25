"""Explicit mapping-source input boundary and loss-accounted held records (#64)."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .errors import ProfileError
from .ledger_model import LedgerEntry, require_public_identity_safe
from .mapping_admission import PolicyTable, decide_row
from .resolver import RecordRef
from .source_public import safe_public_literal


SOURCE_TABLES = {
    "crosswalk": ("bilqis_ithkuil_crosswalk", "crosswalk_id"),
    "bridge": ("bilqis_semantic_bridges", "bridge_id"),
}
STATE_FIELDS = (
    "relation_type", "link_type", "equivalence_state", "mapping_disposition",
    "crosswalk_state", "bridge_epistemic_state", "registry_state_raw",
    "source_era", "target_kind", "source_match_state",
)
ENDPOINT_FIELDS = (
    "bilqis_token_id", "bilqis_pasigraphy_identity", "target_id",
    "resolved_source_id", "resolved_section_id",
)
LOCUS_FIELDS = (
    "official_source_url", "official_locus", "primary_source", "source_locus_or_era",
    "resolved_source_id", "resolved_section_id", "source_tab", "source_row",
)
COMMENTARY_FIELDS = (
    "semantic_differential", "semantic_caution_or_dependencies",
)
STATUS_MAP = {"HOLD": "HELD", "REJECT": "REJECTED", "UNSUPPORTED": "UNSUPPORTED"}


@dataclass(frozen=True, order=True)
class MappingSourceRow:
    record_kind: str
    fields: tuple[tuple[str, str], ...]

    @property
    def values(self) -> dict[str, str]:
        return dict(self.fields)

    @property
    def record_ref(self) -> RecordRef:
        table, key = SOURCE_TABLES[self.record_kind]
        return RecordRef(table, self.values[key])


@dataclass(frozen=True)
class MappingHeldRecord:
    entry: LedgerEntry
    original_states: tuple[tuple[str, str], ...]
    endpoint_ids: tuple[tuple[str, str], ...]
    commentary: tuple[tuple[str, str], ...]
    withheld_fields: tuple[str, ...]

    def as_dict(self) -> dict:
        return {**self.entry.as_dict(), "original_states": dict(self.original_states),
                "endpoint_ids": dict(self.endpoint_ids), "commentary": dict(self.commentary),
                "withheld_fields": list(self.withheld_fields)}


def source_row(record_kind: str, row: Mapping[str, str]) -> MappingSourceRow:
    if record_kind not in SOURCE_TABLES:
        raise ProfileError("MAPPING_SOURCE_KIND_UNSUPPORTED", record_kind)
    key_field = SOURCE_TABLES[record_kind][1]
    key = row.get(key_field)
    if not isinstance(key, str) or not key or key != key.strip():
        raise ProfileError("MAPPING_SOURCE_ID_REQUIRED", record_kind, key_field)
    require_public_identity_safe(key_field, key)
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in row.items()):
        raise ProfileError("MAPPING_SOURCE_FIELD_INVALID", record_kind, key)
    return MappingSourceRow(record_kind, tuple(sorted(row.items())))


def load_mapping_rows(input_root: str | Path) -> tuple[MappingSourceRow, ...]:
    rows = []
    for kind, (table, key_field) in SOURCE_TABLES.items():
        path = Path(input_root) / f"{table}.csv"
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle, strict=True)
                columns = reader.fieldnames or []
                if key_field not in columns or len(columns) != len(set(columns)):
                    raise ProfileError("MAPPING_SOURCE_SCHEMA_INVALID", table)
                for row in reader:
                    if None in row or any(value is None for value in row.values()):
                        raise ProfileError("MAPPING_SOURCE_ROW_SHAPE_INVALID", table)
                    rows.append(source_row(kind, row))
        except (OSError, UnicodeError, csv.Error) as error:
            raise ProfileError("MAPPING_SOURCE_READ_ERROR", table, type(error).__name__) from error
    seen = set()
    for row in rows:
        if row.record_ref in seen:
            raise ProfileError("DUPLICATE_MAPPING_SOURCE_ID", row.record_ref.table, row.record_ref.key)
        seen.add(row.record_ref)
    return tuple(sorted(rows, key=lambda row: row.record_ref))


def mapping_held_record(row: MappingSourceRow, status: str, reason: str) -> MappingHeldRecord:
    """Format one non-emitting outcome supplied by an owning validation gate."""
    if status not in STATUS_MAP.values():
        raise ProfileError("MAPPING_HELD_STATUS_INVALID", status)
    ref, values = row.record_ref, row.values
    states = tuple((name, values[name]) for name in STATE_FIELDS if name in values)
    for name, value in states:
        require_public_identity_safe("mapping_state." + name, value)
    endpoint_ids = tuple((name, values[name]) for name in ENDPOINT_FIELDS if values.get(name))
    for name, value in endpoint_ids:
        require_public_identity_safe("mapping_endpoint." + name, value, allow_project_iri=True)
    loci, commentary, withheld = [], [], []
    for name in (*LOCUS_FIELDS, *COMMENTARY_FIELDS):
        value = values.get(name)
        if not value:
            continue
        if safe_public_literal(value) is None:
            withheld.append(name)
        elif name in LOCUS_FIELDS:
            loci.append(f"{name}={value}")
        else:
            commentary.append((name, value))
    entry = LedgerEntry(ref.table, ref.key, status, reason, (), status == "UNSUPPORTED",
                        "Mapping is not admitted by the finite source-state policy and owning gates.",
                        (ref,), tuple(sorted(loci)), "", ())
    return MappingHeldRecord(entry, states, endpoint_ids, tuple(commentary), tuple(sorted(withheld)))


def preserve_nonadmitted(
    rows: Iterable[MappingSourceRow], policy: PolicyTable,
) -> tuple[MappingHeldRecord, ...]:
    """Use the #42 ledger shape while retaining exact finite source dispositions."""
    records, seen = [], set()
    for row in sorted(rows, key=lambda item: item.record_ref):
        ref, values = row.record_ref, row.values
        if ref in seen:
            raise ProfileError("DUPLICATE_MAPPING_SOURCE_ID", ref.table, ref.key)
        seen.add(ref)
        try:
            decision = decide_row(row.record_kind, values, policy)
            outcome, reason = decision.outcome, decision.reason_code
        except ProfileError as error:
            outcome, reason = "UNSUPPORTED", error.code
        if outcome not in STATUS_MAP:
            raise ProfileError("MAPPING_ROW_REQUIRES_EMISSION", ref.table, ref.key, outcome)
        records.append(mapping_held_record(row, STATUS_MAP[outcome], reason or "MAPPING_POLICY_NO_MATCH"))
    return tuple(records)
