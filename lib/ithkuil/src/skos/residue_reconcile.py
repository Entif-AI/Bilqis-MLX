"""Exact current-corpus reconciliation for linguistic RDF residue (#61)."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
from typing import Iterable, Mapping

from rdflib import Graph

from .affix_degree import project_affix_degrees
from .allomorph_rule import project_allomorph_rules
from .canonical import CanonicalRdf, canonicalize
from .composition import CompositionProfile, project_compositions
from .composition_components import project_composition_components
from .errors import ProfileError
from .extension_vocabulary import ExtensionVocabulary, validate_graph_vocabulary
from .preflight import CompilerClosure
from .publication import json_bytes


SCHEMA = "bilqis.skos.residue-reconciliation/v1"
TABLE_KEYS = {
    "affix_degrees": "degree_id",
    "morpheme_compositions": "composition_id",
    "composition_components": "component_id",
    "allomorph_rules": "allomorph_rule_id",
}


@dataclass(frozen=True)
class ResidueReconciliation:
    graph: Graph
    canonical: CanonicalRdf
    receipt: dict


def _dict_rows(rows: Iterable[Mapping[str, str]]) -> tuple[dict[str, str], ...]:
    return tuple(dict(row.items()) if hasattr(row, "items") else dict(row.values) for row in rows)


def _source_ids(rows, table: str) -> tuple[str, ...]:
    key = TABLE_KEYS[table]
    ids = tuple(row.get(key, "") for row in rows)
    if any(not value for value in ids):
        raise ProfileError("RESIDUE_BLANK_SOURCE_ID", table)
    duplicates = sorted(value for value, count in Counter(ids).items() if count > 1)
    if duplicates:
        raise ProfileError("RESIDUE_DUPLICATE_SOURCE_ID", table, *duplicates)
    return tuple(sorted(ids))


def validate_partition(
    source_ids: set[str], emitted: set[str], held: set[str], ir_only: set[str], *, table: str
) -> None:
    overlaps = (emitted & held) | (emitted & ir_only) | (held & ir_only)
    if overlaps:
        raise ProfileError("RESIDUE_MULTIPLE_DISPOSITIONS", table, *sorted(overlaps))
    accounted = emitted | held | ir_only
    missing = source_ids - accounted
    extra = accounted - source_ids
    if missing:
        raise ProfileError("RESIDUE_MISSING_DISPOSITION", table, *sorted(missing))
    if extra:
        raise ProfileError("RESIDUE_OUT_OF_SCOPE_DISPOSITION", table, *sorted(extra))


def _reasons(projection, id_attr: str, issue_id_attr: str) -> dict[str, set[str]]:
    reasons = defaultdict(set)
    for issue in projection.issues:
        values = getattr(issue, issue_id_attr)
        if isinstance(values, str):
            values = (values,)
        for value in values:
            reasons[value].add(issue.code)
    for value in getattr(projection, id_attr):
        if not reasons[value]:
            reasons[value].add("HELD_WITHOUT_DOMAIN_REASON")
    return reasons


def _table_source_digest(rows, key: str) -> str:
    ordered = sorted(rows, key=lambda row: row[key])
    return hashlib.sha256(json_bytes(ordered)).hexdigest()


def reconcile_residue(
    closure: CompilerClosure,
    *,
    degree_rows: Iterable[Mapping[str, str]],
    component_rows: Iterable[Mapping[str, str]],
    allomorph_rows: Iterable[Mapping[str, str]],
    composition_profile: CompositionProfile,
    vocabulary: ExtensionVocabulary,
    ir_only_reasons: Mapping[str, Mapping[str, str]] | None = None,
) -> ResidueReconciliation:
    """Compose #56-#60 and prove exactly one disposition for every current source row."""
    if not isinstance(closure, CompilerClosure):
        raise ProfileError("COMPILER_CLOSURE_REQUIRED", type(closure).__name__)
    degree_rows = _dict_rows(degree_rows)
    component_rows = _dict_rows(component_rows)
    allomorph_rows = _dict_rows(allomorph_rows)
    composition_rows = tuple(dict(row.values) for row in closure.table("morpheme_compositions").rows)
    source_rows = {
        "affix_degrees": degree_rows,
        "morpheme_compositions": composition_rows,
        "composition_components": component_rows,
        "allomorph_rules": allomorph_rows,
    }
    source_ids = {table: set(_source_ids(rows, table)) for table, rows in source_rows.items()}

    degrees = project_affix_degrees(closure, degree_rows)
    compositions = project_compositions(closure, composition_profile)
    components = project_composition_components(closure, component_rows, compositions)
    rules = project_allomorph_rules(closure, allomorph_rows)
    projections = {
        "affix_degrees": (degrees, "emitted_source_ids", "held_source_ids", "source_degree_ids"),
        "morpheme_compositions": (compositions, "emitted_ids", "held_ids", "composition_id"),
        "composition_components": (components, "emitted_ids", "held_ids", "component_ids"),
        "allomorph_rules": (rules, "emitted_ids", "held_ids", "rule_ids"),
    }
    explicit_ir = {table: dict(values) for table, values in (ir_only_reasons or {}).items()}
    unknown_ir_tables = set(explicit_ir) - set(TABLE_KEYS)
    if unknown_ir_tables:
        raise ProfileError("RESIDUE_IR_ONLY_TABLE_UNKNOWN", *sorted(unknown_ir_tables))

    tables = {}
    held_by_reason = Counter()
    for table, (projection, emitted_attr, held_attr, issue_attr) in projections.items():
        emitted = set(getattr(projection, emitted_attr))
        held = set(getattr(projection, held_attr))
        ir_map = explicit_ir.get(table, {})
        ir_only = set(ir_map)
        validate_partition(source_ids[table], emitted, held, ir_only, table=table)
        reasons = _reasons(projection, held_attr, issue_attr)
        for value in held:
            held_by_reason.update(reasons[value])
        tables[table] = {
            "source_count": len(source_ids[table]),
            "emitted_ids": sorted(emitted),
            "held": [
                {"id": value, "reasons": sorted(reasons[value])}
                for value in sorted(held)
            ],
            "ir_only": [
                {"id": value, "reason": ir_map[value]}
                for value in sorted(ir_only)
            ],
            "source_sha256": _table_source_digest(source_rows[table], TABLE_KEYS[table]),
        }

    graph = Graph()
    for projection in (degrees, compositions, components, rules):
        for triple in projection.graph:
            graph.add(triple)
    used_vocab = validate_graph_vocabulary(graph, vocabulary)
    canonical = canonicalize(graph)
    source_digest = hashlib.sha256(json_bytes({
        table: tables[table]["source_sha256"] for table in sorted(tables)
    })).hexdigest()
    counts = {
        "source_rows": sum(item["source_count"] for item in tables.values()),
        "emitted": sum(len(item["emitted_ids"]) for item in tables.values()),
        "held": sum(len(item["held"]) for item in tables.values()),
        "ir_only": sum(len(item["ir_only"]) for item in tables.values()),
    }
    body = {
        "schema": SCHEMA,
        "counts": counts,
        "tables": tables,
        "held_by_reason": dict(sorted(held_by_reason.items())),
        "used_extension_terms": sorted(used_vocab),
        "residue_source_sha256": source_digest,
        "canonical_rdf": canonical.metadata(),
    }
    receipt = {**body, "receipt_sha256": hashlib.sha256(json_bytes(body)).hexdigest()}
    return ResidueReconciliation(graph, canonical, receipt)


def reconciliation_json_bytes(result: ResidueReconciliation) -> bytes:
    if not isinstance(result, ResidueReconciliation):
        raise ProfileError("RESIDUE_RECONCILIATION_REQUIRED", type(result).__name__)
    return json_bytes(result.receipt)
