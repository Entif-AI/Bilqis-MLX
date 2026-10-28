"""No-omission reconciliation of the complete mapping domain (#66)."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import json

from .errors import ProfileError
from .ledger_model import sanitize_detail
from .mapping import PREDICATE_IRIS
from .mapping_admission import PolicyTable
from .mapping_emit import MappingEmission
from .mapping_rows import MappingHeldRecord, MappingSourceRow


SCHEMA = "bilqis.skos.mapping-reconciliation/v1"


def receipt_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def reconcile_mapping_records(
    rows: tuple[MappingSourceRow, ...], held: tuple[MappingHeldRecord, ...],
    emission: MappingEmission, policy: PolicyTable,
) -> dict:
    expected = [row.record_ref for row in rows]
    if len(expected) != len(set(expected)):
        raise ProfileError("MAPPING_RECONCILIATION_DUPLICATE_SOURCE")
    observed = [record.entry.source_refs[0] for record in held] + list(emission.emitted_records)
    counts = Counter(observed)
    missing, extra = set(expected) - set(observed), set(observed) - set(expected)
    duplicates = {ref for ref, count in counts.items() if count != 1}
    if missing or extra or duplicates:
        raise ProfileError("MAPPING_RECONCILIATION_MISMATCH", *(
            f"{kind}:{ref.table}:{ref.key}" for kind, refs in
            (("missing", missing), ("extra", extra), ("duplicate", duplicates)) for ref in sorted(refs)))
    indexed = {row.record_ref: row for row in rows}
    emitted = set(emission.emitted_records)
    claimed = {ref for assertion in emission.assertions for ref in assertion.record_refs}
    if claimed != emitted:
        raise ProfileError("MAPPING_ASSERTION_ACCOUNTING_MISMATCH")
    graph_triples = {(str(subject), str(predicate), str(target)) for subject, predicate, target in emission.graph}
    assertion_triples = {(item.source_iri, item.predicate_iri, item.target_iri) for item in emission.assertions}
    if graph_triples != assertion_triples:
        raise ProfileError("MAPPING_GRAPH_ACCOUNTING_MISMATCH")
    if any(item.predicate_iri not in {str(iri) for iri in PREDICATE_IRIS.values()} for item in emission.assertions):
        raise ProfileError("UNEXPECTED_MAPPING_OUTPUT_PREDICATE")
    by_status = Counter(record.entry.status for record in held)
    by_status["EMITTED"] = len(emitted)
    predicates = {name: sum(item.predicate_iri == str(iri) for item in emission.assertions)
                  for name, iri in PREDICATE_IRIS.items()}
    histories = sum(row.values.get("target_kind") == "historical_source" or
                    row.values.get("bridge_epistemic_state") == "historical_only" for row in rows)
    raw_pairs = {(row.record_kind,
                  row.values.get("bilqis_pasigraphy_identity", row.record_ref.key),
                  row.values.get("target_kind", ""), row.values.get("target_id", "")) for row in rows}
    equivalent_sets = {assertion.record_refs for assertion in emission.assertions}
    duplicate_count = sum(len(refs) - 1 for refs in equivalent_sets)
    issues = [{"code": issue.code,
               "record_refs": [{"table": ref.table, "key": ref.key} for ref in issue.record_refs],
               "details": [sanitize_detail(detail) for detail in issue.details]} for issue in emission.issues]
    entries = [record.as_dict() for record in held]
    entries.extend({"table": ref.table, "key": ref.key, "status": "EMITTED",
                    "reason_code": "EMITTED_ADMITTED_MAPPING",
                    "source_refs": [{"table": ref.table, "key": ref.key}],
                    "source_era": indexed[ref].values.get("source_era", "")}
                   for ref in sorted(emitted))
    input_rows = [{"kind": row.record_kind, "fields": row.values} for row in sorted(rows)]
    unsupported = by_status["UNSUPPORTED"]
    return {
        "schema": SCHEMA, "accounting_complete": True,
        "mapping_complete": not emission.issues and unsupported == 0,
        "requires_semantic_review": bool(by_status["HELD"] or by_status["REJECTED"]),
        "policy_version": policy.table_version,
        "policy_sha256": hashlib.sha256(receipt_bytes(asdict(policy))).hexdigest(),
        "input_sha256": hashlib.sha256(receipt_bytes({"rows": input_rows})).hexdigest(),
        "rows": {"crosswalk": sum(row.record_kind == "crosswalk" for row in rows),
                 "bridge": sum(row.record_kind == "bridge" for row in rows), "total": len(rows)},
        "dispositions": {status: by_status[status] for status in ("EMITTED", "HELD", "REJECTED", "UNSUPPORTED")},
        "by_reason": dict(sorted(Counter(record.entry.reason_code for record in held).items())),
        "by_source_state": dict(sorted(Counter(
            row.values.get("crosswalk_state", row.values.get("bridge_epistemic_state", "")) for row in rows).items())),
        "predicate_triples": predicates, "historical_only_rows": histories,
        "unsupported_rows": unsupported, "conflict_count": len(emission.issues),
        "declared_source_target_pairs": len(raw_pairs),
        "pair_basis": "stable source identity or bridge-row ID plus explicit target kind/ID; not inferred equivalence",
        "duplicate_equivalent_assertions": duplicate_count,
        "entries": sorted(entries, key=lambda entry: (entry["table"], entry["key"])),
        "issues": issues,
        "assertions": [{"source_iri": item.source_iri, "predicate_iri": item.predicate_iri,
                        "target_iri": item.target_iri,
                        "record_refs": [{"table": ref.table, "key": ref.key} for ref in item.record_refs]}
                       for item in emission.assertions],
    }
