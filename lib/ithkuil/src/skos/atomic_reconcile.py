"""Atomic-domain source/RDF reconciliation artifact for issue #49."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json

from rdflib import Literal, URIRef
from rdflib.namespace import RDF, SKOS

from .atomic import AtomicCompileResult, AtomicRowOutcome
from .canonical import canonicalize
from .errors import ProfileError
from .preflight import CompilerClosure


@dataclass(frozen=True)
class AtomicReconciliation:
    atomic_source_sha256: str
    canonical_rdf_sha256: str
    canonical_triple_count: int
    source_row_count: int
    semantic_identity_count: int
    category_code_count: int
    multi_realization_identity_count: int
    emitted_resource_count: int
    emitted_concept_count: int
    emitted_root_count: int
    held_identity_count: int
    notation_counts: tuple[tuple[str, int], ...]
    held_identity_counts: tuple[tuple[str, int], ...]
    held_row_counts: tuple[tuple[str, int], ...]
    rows: tuple[AtomicRowOutcome, ...]

    @property
    def conformance_complete(self) -> bool:
        return (
            len(self.rows) == self.source_row_count
            and all(row.status in {"EMITTED", "HELD"} for row in self.rows)
            and self.semantic_identity_count == self.emitted_resource_count + self.held_identity_count
        )

    def as_dict(self) -> dict:
        return {
            "schema": "bilqis.skos.atomic-reconciliation/v1",
            "conformance_complete": self.conformance_complete,
            "source": {
                "atomic_rows": self.source_row_count,
                "semantic_identities": self.semantic_identity_count,
                "category_codes": self.category_code_count,
                "multi_realization_identities": self.multi_realization_identity_count,
                "sha256": self.atomic_source_sha256,
            },
            "rdf": {
                "canonical_sha256": self.canonical_rdf_sha256,
                "triple_count": self.canonical_triple_count,
                "emitted_resources": self.emitted_resource_count,
                "emitted_concepts": self.emitted_concept_count,
                "emitted_roots": self.emitted_root_count,
                "notation_counts_by_datatype": dict(self.notation_counts),
            },
            "held": {
                "identities": self.held_identity_count,
                "identity_counts_by_reason": dict(self.held_identity_counts),
                "row_counts_by_reason": dict(self.held_row_counts),
            },
            "rows": [
                {
                    "atomic_id": row.atomic_id,
                    "category_code": row.category_code,
                    "status": row.status,
                    "reason_codes": list(row.reason_codes),
                    "semantic_iri": row.semantic_iri,
                }
                for row in self.rows
            ],
        }


def atomic_source_digest(closure: CompilerClosure) -> str:
    """Digest exact atomic IR values independent of row/column ordering."""
    encoded = sorted(
        json.dumps(dict(row.values), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for row in closure.table("morphemes_atomic").rows
    )
    digest = hashlib.sha256()
    for row in encoded:
        digest.update(row.encode("utf-8") + b"\n")
    return digest.hexdigest()


def _validate_rows(closure: CompilerClosure, compiled: AtomicCompileResult) -> tuple[AtomicRowOutcome, ...]:
    source_ids = [row.get("atomic_id") for row in closure.table("morphemes_atomic").rows]
    outcome_ids = [row.atomic_id for row in compiled.row_outcomes]
    source_counts = Counter(source_ids)
    outcome_counts = Counter(outcome_ids)
    duplicates = tuple(sorted(key for key, count in outcome_counts.items() if count != 1))
    missing = tuple(sorted(set(source_ids) - set(outcome_ids)))
    extra = tuple(sorted(set(outcome_ids) - set(source_ids)))
    if duplicates or missing or extra or len(source_ids) != len(outcome_ids):
        raise ProfileError(
            "ATOMIC_RECONCILIATION_ROW_MISMATCH",
            *(f"missing={key}" for key in missing),
            *(f"extra={key}" for key in extra),
            *(f"duplicate={key}" for key in duplicates),
            f"source_rows={len(source_ids)}",
            f"outcome_rows={len(outcome_ids)}",
        )
    source_duplicates = tuple(sorted(key for key, count in source_counts.items() if count != 1))
    if source_duplicates:
        raise ProfileError(
            "ATOMIC_SOURCE_KEY_DUPLICATE",
            *(f"atomic_id={key}" for key in source_duplicates),
        )
    rejected = tuple(sorted(row.atomic_id for row in compiled.row_outcomes if row.status == "REJECTED"))
    if rejected:
        raise ProfileError(
            "ATOMIC_RECONCILIATION_REJECTED_ROW",
            *(f"atomic_id={key}" for key in rejected),
        )
    blank_identity = tuple(sorted(row.atomic_id for row in compiled.row_outcomes if not row.semantic_iri))
    if blank_identity:
        raise ProfileError(
            "ATOMIC_RECONCILIATION_IDENTITY_MISSING",
            *(f"atomic_id={key}" for key in blank_identity),
        )
    return tuple(sorted(compiled.row_outcomes))


def reconcile_atomic(closure: CompilerClosure, compiled: AtomicCompileResult) -> AtomicReconciliation:
    rows = _validate_rows(closure, compiled)
    by_identity: dict[str, list[AtomicRowOutcome]] = defaultdict(list)
    for row in rows:
        by_identity[row.semantic_iri].append(row)
    for iri, identity_rows in sorted(by_identity.items()):
        statuses = {row.status for row in identity_rows}
        if len(statuses) != 1:
            raise ProfileError(
                "ATOMIC_IDENTITY_ACCOUNTING_CONFLICT",
                f"semantic_iri={iri}",
                *(f"row={row.atomic_id}:{row.status}" for row in identity_rows),
            )

    emitted_iris = {resource.identity.iri for resource in compiled.build.emitted}
    row_emitted_iris = {iri for iri, values in by_identity.items() if values[0].status == "EMITTED"}
    if emitted_iris != row_emitted_iris:
        missing = sorted(row_emitted_iris - emitted_iris)
        extra = sorted(emitted_iris - row_emitted_iris)
        raise ProfileError(
            "ATOMIC_EMITTED_IDENTITY_MISMATCH",
            *(f"missing_from_build={iri}" for iri in missing),
            *(f"build_without_row={iri}" for iri in extra),
        )

    held_iris = {iri for iri, values in by_identity.items() if values[0].status == "HELD"}
    for iri in sorted(held_iris):
        node = URIRef(iri)
        if (
            any(compiled.graph.triples((node, None, None)))
            or any(compiled.graph.triples((None, SKOS.member, node)))
            or any(compiled.graph.triples((None, RDF.first, node)))
        ):
            raise ProfileError("ATOMIC_HELD_IDENTITY_IN_STRONG_GRAPH", f"semantic_iri={iri}")

    notation_counts: Counter[str] = Counter()
    for _, _, value in compiled.graph.triples((None, SKOS.notation, None)):
        if not isinstance(value, Literal) or value.datatype is None:
            raise ProfileError("ATOMIC_NOTATION_DATATYPE_MISSING", repr(value))
        notation_counts[str(value.datatype)] += 1

    held_rows: dict[str, set[str]] = defaultdict(set)
    held_identities: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if row.status != "HELD":
            continue
        for reason in row.reason_codes:
            held_rows[reason].add(row.atomic_id)
            held_identities[reason].add(row.semantic_iri)

    source_categories = {row.get("category_code") for row in closure.table("morphemes_atomic").rows}
    compiled_categories = {category.category_code for category in compiled.categories}
    if source_categories != compiled_categories:
        raise ProfileError(
            "ATOMIC_CATEGORY_ACCOUNTING_MISMATCH",
            *(f"missing={code}" for code in sorted(source_categories - compiled_categories)),
            *(f"extra={code}" for code in sorted(compiled_categories - source_categories)),
        )

    canonical = canonicalize(compiled.graph)
    return AtomicReconciliation(
        atomic_source_sha256=atomic_source_digest(closure),
        canonical_rdf_sha256=canonical.sha256,
        canonical_triple_count=canonical.triple_count,
        source_row_count=len(rows),
        semantic_identity_count=len(by_identity),
        category_code_count=len(source_categories),
        multi_realization_identity_count=sum(len(values) > 1 for values in by_identity.values()),
        emitted_resource_count=len(compiled.build.emitted),
        emitted_concept_count=sum(resource.role == "concept" for resource in compiled.build.emitted),
        emitted_root_count=sum(resource.role == "root" for resource in compiled.build.emitted),
        held_identity_count=len(held_iris),
        notation_counts=tuple(sorted(notation_counts.items())),
        held_identity_counts=tuple(sorted((reason, len(values)) for reason, values in held_identities.items())),
        held_row_counts=tuple(sorted((reason, len(values)) for reason, values in held_rows.items())),
        rows=rows,
    )


def atomic_reconciliation_json_bytes(result: AtomicReconciliation) -> bytes:
    payload = json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (payload + "\n").encode("utf-8")
