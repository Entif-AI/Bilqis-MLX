"""Atlas projection coverage ownership; canonical algorithms preserved."""
from __future__ import annotations
from .common import _fail
from .concepts import CorpusCoverageRow


def _coverage_record(row: dict, domain: str, *, concept_ids: set[str],
                     active_ids: set[str]) -> CorpusCoverageRow:
    semantic_id = row.get("semantic_iri")
    semantic_id = semantic_id if isinstance(semantic_id, str) and semantic_id else None
    status = row["status"]
    if status in {"HELD", "REJECTED", "UNSUPPORTED"}:
        source_disposition = "SOURCE_HELD"
        implementation_status = "NOT_APPLICABLE"
        teaching_candidate = False
        teaching_reason = row["reason_code"]
    elif status == "IR_ONLY":
        source_disposition = "SOURCE_IR_ONLY"
        implementation_status = "NOT_APPLICABLE"
        teaching_candidate = False
        teaching_reason = row["reason_code"]
    elif semantic_id in concept_ids:
        source_disposition = "SOURCE_ELIGIBLE"
        if semantic_id in active_ids:
            implementation_status = "ADMITTED"
            teaching_candidate = True
            teaching_reason = "PRIOR_ACCEPTED_ABI"
        else:
            implementation_status = "IMPLEMENTATION_UNCOVERED"
            teaching_candidate = False
            teaching_reason = "IMPLEMENTATION_UNCOVERED"
    else:
        source_disposition = "SOURCE_EMITTED_NON_CONCEPT"
        implementation_status = "NOT_APPLICABLE"
        teaching_candidate = False
        teaching_reason = row["reason_code"]
    return CorpusCoverageRow(
        domain=domain,
        table=row["table"],
        key=row["key"],
        semantic_id=semantic_id,
        source_disposition=source_disposition,
        implementation_status=implementation_status,
        teaching_candidate=teaching_candidate,
        reason_code=row["reason_code"],
        teaching_reason=teaching_reason,
        owner=row.get("owner", ""),
    )

def _validate_source_census(coverage: dict, source_rows: object) -> tuple[tuple[str, str, str], ...]:
    if not isinstance(source_rows, list) or any(
            not isinstance(item, dict) or set(item) != {"domain", "table", "key"}
            or any(not isinstance(item[field], str) or not item[field]
                   for field in ("domain", "table", "key")) for item in source_rows):
        _fail("ATLAS_SOURCE_CENSUS_INVALID")
    independent = tuple(
        (item["domain"], item["table"], item["key"]) for item in source_rows)
    if len(independent) != len(set(independent)):
        _fail("ATLAS_SOURCE_CENSUS_DUPLICATE")

    covered = []
    try:
        for domain, receipt in coverage["domains"].items():
            for row in receipt["rows"]:
                covered.append((domain, row["table"], row["key"]))
    except (KeyError, TypeError, AttributeError) as error:
        _fail("ATLAS_COVERAGE_CENSUS_INVALID:" + type(error).__name__)
    covered_tuple = tuple(covered)
    if len(covered_tuple) != len(set(covered_tuple)):
        _fail("ATLAS_COVERAGE_CENSUS_DUPLICATE")
    if (len(independent) != coverage["totals"]["source_rows"]
            or len(covered_tuple) != coverage["totals"]["source_rows"]):
        _fail("ATLAS_SOURCE_CENSUS_COUNT_MISMATCH")
    if set(independent) != set(covered_tuple):
        _fail("ATLAS_SOURCE_CENSUS_IDENTITY_MISMATCH")
    return independent
