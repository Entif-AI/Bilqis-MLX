"""Versioned semantic coverage receipt schema validator (#67)."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import sys

from .errors import ProfileError

SCHEMA_ID = "bilqis.skos.semantic-coverage/v1"
STATUSES = ("EMITTED", "HELD", "REJECTED", "UNSUPPORTED", "IR_ONLY")
BUILD_STATUSES = frozenset({"complete", "partial", "blocked"})
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SEMANTIC_FIELDS = ("concepts", "roots", "senses", "mappings", "compositions", "allomorphs")


def _required(value: dict, fields: tuple[str, ...], code: str) -> None:
    missing = [field for field in fields if field not in value]
    if missing:
        raise ProfileError(code, *(f"missing={field}" for field in missing))


def _object(value, code: str) -> dict:
    if not isinstance(value, dict):
        raise ProfileError(code, f"type={type(value).__name__}")
    return value


def _count(value, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProfileError("COVERAGE_COUNT_INVALID", field, repr(value))
    return value


def _digest(value, field: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise ProfileError("COVERAGE_DIGEST_INVALID", field, repr(value))
    return value


def _dispositions(value, field: str) -> dict[str, int]:
    obj = _object(value, "COVERAGE_DISPOSITIONS_REQUIRED")
    if set(obj) != set(STATUSES):
        unknown = sorted(set(obj) - set(STATUSES))
        missing = sorted(set(STATUSES) - set(obj))
        raise ProfileError(
            "COVERAGE_DISPOSITION_ENUM_INVALID",
            field,
            *(f"unknown={item}" for item in unknown),
            *(f"missing={item}" for item in missing),
        )
    return {status: _count(obj[status], f"{field}.{status}") for status in STATUSES}


def _domain(name: str, value) -> dict:
    obj = _object(value, "COVERAGE_DOMAIN_REQUIRED")
    _required(
        obj,
        ("source_rows", "dispositions", "rows", "semantic_counts", "notation_counts", "frontier_debt"),
        "COVERAGE_DOMAIN_FIELD_MISSING",
    )
    allowed = {"source_rows", "dispositions", "rows", "semantic_counts", "notation_counts", "frontier_debt"}
    if set(obj) - allowed:
        raise ProfileError("COVERAGE_DOMAIN_FIELD_UNKNOWN", name, *sorted(set(obj) - allowed))
    source_rows = _count(obj["source_rows"], f"domains.{name}.source_rows")
    dispositions = _dispositions(obj["dispositions"], f"domains.{name}.dispositions")
    if sum(dispositions.values()) != source_rows:
        raise ProfileError(
            "COVERAGE_DOMAIN_TOTAL_MISMATCH",
            name,
            f"source_rows={source_rows}",
            f"dispositions={sum(dispositions.values())}",
        )
    rows = obj["rows"]
    if not isinstance(rows, list) or len(rows) != source_rows:
        raise ProfileError("COVERAGE_DOMAIN_ROW_COUNT_MISMATCH", name, f"rows={len(rows) if isinstance(rows, list) else 'invalid'}", f"source_rows={source_rows}")
    row_ids = set()
    row_statuses = Counter()
    for index, item in enumerate(rows):
        entry = _object(item, "COVERAGE_ROW_REQUIRED")
        _required(entry, ("table", "key", "status", "reason_code", "owner", "semantic_iri"), "COVERAGE_ROW_FIELD_MISSING")
        if set(entry) != {"table", "key", "status", "reason_code", "owner", "semantic_iri"}:
            raise ProfileError("COVERAGE_ROW_FIELD_UNKNOWN", name, str(index))
        if not all(isinstance(entry[field], str) and entry[field] for field in ("table", "key")):
            raise ProfileError("COVERAGE_ROW_IDENTITY_INVALID", name, str(index))
        if not all(isinstance(entry[field], str) for field in ("reason_code", "owner")):
            raise ProfileError("COVERAGE_ROW_RATIONALE_TYPE_INVALID", name, str(index))
        if entry["status"] not in STATUSES:
            raise ProfileError("COVERAGE_DISPOSITION_ENUM_INVALID", name, f"status={entry['status']}")
        if entry["semantic_iri"] is not None and not isinstance(entry["semantic_iri"], str):
            raise ProfileError("COVERAGE_ROW_SEMANTIC_IRI_INVALID", name, str(index))
        row_id = (entry["table"], entry["key"])
        if row_id in row_ids:
            raise ProfileError("COVERAGE_ROW_DUPLICATE", name, *row_id)
        row_ids.add(row_id)
        row_statuses[entry["status"]] += 1
    if any(row_statuses[status] != dispositions[status] for status in STATUSES):
        raise ProfileError("COVERAGE_DOMAIN_ROW_DISPOSITION_MISMATCH", name)
    semantic = _object(obj["semantic_counts"], "COVERAGE_SEMANTIC_COUNTS_REQUIRED")
    if set(semantic) != set(SEMANTIC_FIELDS):
        raise ProfileError("COVERAGE_SEMANTIC_COUNT_FIELDS_INVALID", name)
    semantic = {field: _count(semantic[field], f"domains.{name}.semantic_counts.{field}")
                for field in SEMANTIC_FIELDS}
    notation = _object(obj["notation_counts"], "COVERAGE_NOTATION_COUNTS_REQUIRED")
    notation = {key: _count(count, f"domains.{name}.notation_counts.{key}")
                for key, count in notation.items()}
    debt = obj["frontier_debt"]
    if not isinstance(debt, list):
        raise ProfileError("COVERAGE_FRONTIER_DEBT_REQUIRED", name)
    normalized_debt = []
    for index, item in enumerate(debt):
        entry = _object(item, "COVERAGE_FRONTIER_DEBT_ENTRY_REQUIRED")
        _required(entry, ("code", "count", "blocking"), "COVERAGE_FRONTIER_DEBT_FIELD_MISSING")
        if set(entry) != {"code", "count", "blocking"}:
            raise ProfileError("COVERAGE_FRONTIER_DEBT_FIELD_UNKNOWN", name, str(index))
        if not isinstance(entry["code"], str) or not entry["code"]:
            raise ProfileError("COVERAGE_FRONTIER_DEBT_CODE_INVALID", name, str(index))
        if not isinstance(entry["blocking"], bool):
            raise ProfileError("COVERAGE_FRONTIER_DEBT_BLOCKING_INVALID", name, str(index))
        normalized_debt.append(
            {"code": entry["code"], "count": _count(entry["count"], f"debt.{name}.{index}"),
             "blocking": entry["blocking"]}
        )
    return {
        "source_rows": source_rows,
        "dispositions": dispositions,
        "rows": rows,
        "semantic_counts": semantic,
        "notation_counts": dict(sorted(notation.items())),
        "frontier_debt": normalized_debt,
    }


def validate_coverage_receipt(value: dict) -> dict:
    receipt = _object(value, "COVERAGE_RECEIPT_REQUIRED")
    required = (
        "schema", "compiler", "inputs", "canonical_rdf", "domains", "totals",
        "frontier_debt_declared", "conflicts", "build_status",
    )
    _required(receipt, required, "COVERAGE_TOP_LEVEL_FIELD_MISSING")
    if set(receipt) != set(required):
        raise ProfileError("COVERAGE_TOP_LEVEL_FIELD_UNKNOWN", *sorted(set(receipt) - set(required)))
    if receipt["schema"] != SCHEMA_ID:
        raise ProfileError("COVERAGE_SCHEMA_UNSUPPORTED", repr(receipt["schema"]))
    compiler = _object(receipt["compiler"], "COVERAGE_COMPILER_REQUIRED")
    _required(compiler, ("version", "profile_version", "profile_sha256"), "COVERAGE_COMPILER_FIELD_MISSING")
    if set(compiler) != {"version", "profile_version", "profile_sha256"}:
        raise ProfileError("COVERAGE_COMPILER_FIELD_UNKNOWN")
    if not all(isinstance(compiler[field], str) and compiler[field]
               for field in ("version", "profile_version")):
        raise ProfileError("COVERAGE_COMPILER_IDENTITY_INVALID")
    _digest(compiler["profile_sha256"], "compiler.profile_sha256")
    inputs = receipt["inputs"]
    if not isinstance(inputs, list) or not inputs:
        raise ProfileError("COVERAGE_INPUTS_REQUIRED")
    seen = set()
    for item in inputs:
        entry = _object(item, "COVERAGE_INPUT_REQUIRED")
        _required(entry, ("domain", "artifact", "sha256"), "COVERAGE_INPUT_FIELD_MISSING")
        if set(entry) != {"domain", "artifact", "sha256"}:
            raise ProfileError("COVERAGE_INPUT_FIELD_UNKNOWN")
        key = (entry["domain"], entry["artifact"])
        if key in seen:
            raise ProfileError("COVERAGE_INPUT_DUPLICATE", *key)
        seen.add(key)
        if not all(isinstance(part, str) and part for part in key):
            raise ProfileError("COVERAGE_INPUT_IDENTITY_INVALID")
        _digest(entry["sha256"], f"inputs.{entry['domain']}.{entry['artifact']}")
    canonical = _object(receipt["canonical_rdf"], "COVERAGE_CANONICAL_RDF_REQUIRED")
    _required(canonical, ("sha256", "triple_count"), "COVERAGE_CANONICAL_RDF_FIELD_MISSING")
    if set(canonical) != {"sha256", "triple_count"}:
        raise ProfileError("COVERAGE_CANONICAL_RDF_FIELD_UNKNOWN")
    _digest(canonical["sha256"], "canonical_rdf.sha256")
    _count(canonical["triple_count"], "canonical_rdf.triple_count")
    domains_obj = _object(receipt["domains"], "COVERAGE_DOMAINS_REQUIRED")
    if not domains_obj:
        raise ProfileError("COVERAGE_DOMAINS_REQUIRED")
    domains = {name: _domain(name, item) for name, item in sorted(domains_obj.items())}
    totals = _object(receipt["totals"], "COVERAGE_TOTALS_REQUIRED")
    _required(totals, ("source_rows", "dispositions"), "COVERAGE_TOTAL_FIELD_MISSING")
    if set(totals) != {"source_rows", "dispositions"}:
        raise ProfileError("COVERAGE_TOTAL_FIELD_UNKNOWN")
    total_rows = _count(totals["source_rows"], "totals.source_rows")
    total_dispositions = _dispositions(totals["dispositions"], "totals.dispositions")
    expected_rows = sum(domain["source_rows"] for domain in domains.values())
    expected_dispositions = {
        status: sum(domain["dispositions"][status] for domain in domains.values())
        for status in STATUSES
    }
    if total_rows != expected_rows or total_dispositions != expected_dispositions:
        raise ProfileError(
            "COVERAGE_GLOBAL_TOTAL_MISMATCH",
            f"source_rows={total_rows}/{expected_rows}",
            *(f"{status}={total_dispositions[status]}/{expected_dispositions[status]}"
              for status in STATUSES),
        )
    if receipt["frontier_debt_declared"] is not True:
        raise ProfileError("COVERAGE_FRONTIER_DEBT_DECLARATION_REQUIRED")
    conflicts = _object(receipt["conflicts"], "COVERAGE_CONFLICTS_REQUIRED")
    _required(conflicts, ("blocking", "by_reason"), "COVERAGE_CONFLICT_FIELD_MISSING")
    if set(conflicts) != {"blocking", "by_reason"}:
        raise ProfileError("COVERAGE_CONFLICT_FIELD_UNKNOWN")
    _count(conflicts["blocking"], "conflicts.blocking")
    reasons = _object(conflicts["by_reason"], "COVERAGE_CONFLICT_REASONS_REQUIRED")
    for reason, count in reasons.items():
        if not isinstance(reason, str) or not reason:
            raise ProfileError("COVERAGE_CONFLICT_REASON_INVALID")
        _count(count, f"conflicts.by_reason.{reason}")
    if receipt["build_status"] not in BUILD_STATUSES:
        raise ProfileError("COVERAGE_BUILD_STATUS_INVALID", repr(receipt["build_status"]))
    return receipt


def coverage_receipt_json_bytes(value: dict) -> bytes:
    validate_coverage_receipt(value)
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(json.dumps({"status": "error", "code": "USAGE", "usage": "coverage_schema RECEIPT.json"}), file=sys.stderr)
        return 2
    try:
        receipt = json.loads(Path(args[0]).read_text(encoding="utf-8"))
        validate_coverage_receipt(receipt)
    except (OSError, json.JSONDecodeError, ProfileError) as error:
        code = error.code if isinstance(error, ProfileError) else type(error).__name__
        details = list(map(str, error.details)) if isinstance(error, ProfileError) else [str(error)]
        print(json.dumps({"status": "invalid", "code": code, "details": details}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({"status": "valid", "schema": SCHEMA_ID}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
