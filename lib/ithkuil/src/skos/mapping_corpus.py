"""Compose raw mapping policy, reviewed emission and row reconciliation (#66)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from rdflib import Graph

from .errors import ProfileError
from .mapping_admission import PolicyTable, decide_row, load_policy
from .mapping_emit import MappingEmission, MappingIssue, OUTCOME_PREDICATES, ReviewedMappingRow
from .mapping_reconcile import reconcile_mapping_records
from .mapping_rows import MappingSourceRow, load_mapping_rows, mapping_held_record, preserve_nonadmitted
from .mapping_validate import validate_mapping_batch


@dataclass(frozen=True)
class MappingCorpusResult:
    graph: Graph
    receipt: dict


def compile_mapping_rows(
    rows: Iterable[MappingSourceRow], *, policy: PolicyTable,
    endpoint_graph: Graph | None = None, reviewed_rows: Iterable[ReviewedMappingRow] = (),
) -> MappingCorpusResult:
    """Only an emitting raw policy row with a matching reviewed claim can emit."""
    source_rows = tuple(sorted(rows, key=lambda row: row.record_ref))
    reviews = tuple(reviewed_rows)
    review_index = {row.record_ref: row for row in reviews}
    if len(review_index) != len(reviews):
        raise ProfileError("DUPLICATE_MAPPING_REVIEW_ID")
    source_index = {row.record_ref: row for row in source_rows}
    if len(source_index) != len(source_rows):
        raise ProfileError("DUPLICATE_MAPPING_SOURCE_ID")
    if set(review_index) - set(source_index):
        raise ProfileError("MAPPING_REVIEW_UNKNOWN_SOURCE", *(ref.key for ref in sorted(set(review_index)-set(source_index))))
    held, candidates, issues = [], [], []
    for row in source_rows:
        ref = row.record_ref
        try:
            decision = decide_row(row.record_kind, row.values, policy)
        except ProfileError as error:
            held.append(mapping_held_record(row, "UNSUPPORTED", error.code))
            continue
        if not decision.emitting:
            if ref in review_index:
                raise ProfileError("MAPPING_REVIEW_CANNOT_OVERRIDE_POLICY", ref.table, ref.key)
            held.extend(preserve_nonadmitted((row,), policy))
            continue
        review = review_index.get(ref)
        problem = None
        if review is None:
            problem = "MAPPING_REVIEW_EVIDENCE_REQUIRED"
        elif OUTCOME_PREDICATES.get(decision.outcome) != review.claim.predicate:
            problem = "MAPPING_POLICY_PREDICATE_MISMATCH"
        elif review.claim.source_ref not in {ref.key, f"{ref.table}:{ref.key}"}:
            problem = "MAPPING_REVIEW_SOURCE_BINDING_MISMATCH"
        elif row.values.get("target_id") != review.claim.target_iri:
            problem = "MAPPING_REVIEW_TARGET_BINDING_MISMATCH"
        elif row.values.get("bilqis_pasigraphy_identity", row.values.get("source_iri")) != review.claim.source_iri:
            problem = "MAPPING_REVIEW_SOURCE_ENDPOINT_MISMATCH"
        if problem:
            held.append(mapping_held_record(row, "UNSUPPORTED", problem))
            issues.append(MappingIssue(problem, (ref,), ()))
        else:
            candidates.append(review)
    emitted = validate_mapping_batch(candidates, endpoint_graph if endpoint_graph is not None else Graph(), policy)
    issues.extend(emitted.issues)
    raw_unsupported = any(record.entry.status == "UNSUPPORTED" for record in held)
    if issues or raw_unsupported:
        for row in candidates:
            codes = sorted({issue.code for issue in issues if row.record_ref in issue.record_refs})
            held.append(mapping_held_record(source_index[row.record_ref], "UNSUPPORTED",
                                            codes[0] if codes else "MAPPING_BATCH_INCOMPLETE"))
        emitted = MappingEmission(Graph(), (), (), tuple(sorted(set(issues))), ())
    else:
        for ref in emitted.held_records:
            held.append(mapping_held_record(source_index[ref], "HELD", "MAPPING_REVIEW_NOT_ADMITTED"))
    receipt = reconcile_mapping_records(source_rows, tuple(held), emitted, policy)
    return MappingCorpusResult(emitted.graph, receipt)


def compile_mapping_corpus(
    input_root: str | Path, *, policy: PolicyTable | None = None,
    endpoint_graph: Graph | None = None, reviewed_rows: Iterable[ReviewedMappingRow] = (),
) -> MappingCorpusResult:
    return compile_mapping_rows(load_mapping_rows(input_root), policy=policy or load_policy(),
                                endpoint_graph=endpoint_graph, reviewed_rows=reviewed_rows)
