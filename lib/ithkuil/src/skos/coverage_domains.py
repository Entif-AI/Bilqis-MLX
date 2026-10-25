"""Domain adapters for the #68 whole-source coverage receipt."""
from __future__ import annotations

from collections import Counter
from typing import Iterable

from rdflib import Graph, Literal
from rdflib.namespace import SKOS

from .atomic import AtomicCompileResult
from .atomic_reconcile import AtomicReconciliation
from .canonical import canonicalize
from .coverage_schema import STATUSES
from .errors import ProfileError
from .identity import Identity, sense_from_source
from .lexicon_reconcile import LexiconReconciliation
from .mapping_corpus import MappingCorpusResult
from .preflight import CompilerClosure
from .residue_reconcile import ResidueReconciliation


ZERO_SEMANTICS = {
    "concepts": 0,
    "roots": 0,
    "senses": 0,
    "mappings": 0,
    "compositions": 0,
    "allomorphs": 0,
}


def _dispositions(rows: Iterable[dict]) -> dict[str, int]:
    counts = Counter(row["status"] for row in rows)
    return {status: counts[status] for status in STATUSES}


def _notation_counts(graph: Graph) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for value in graph.objects(None, SKOS.notation):
        if not isinstance(value, Literal) or value.datatype is None:
            raise ProfileError("COVERAGE_NOTATION_DATATYPE_MISSING", repr(value))
        counts[str(value.datatype)] += 1
    return dict(sorted(counts.items()))


def _domain(rows, semantic_counts, notation_counts, frontier_debt):
    rows = sorted(rows, key=lambda row: (row["table"], row["key"]))
    return {
        "source_rows": len(rows),
        "dispositions": _dispositions(rows),
        "rows": rows,
        "semantic_counts": semantic_counts,
        "notation_counts": notation_counts,
        "frontier_debt": sorted(
            frontier_debt,
            key=lambda item: (item["code"], item["blocking"], item["count"]),
        ),
    }


def atomic_domain(
    compiled: AtomicCompileResult,
    reconciliation: AtomicReconciliation,
) -> tuple[dict, dict]:
    if reconciliation.canonical_rdf_sha256 != canonicalize(compiled.graph).sha256:
        raise ProfileError("COVERAGE_ATOMIC_CANONICAL_MISMATCH")
    rows = [
        {
            "table": "morphemes_atomic",
            "key": outcome.atomic_id,
            "status": outcome.status,
            "reason_code": "+".join(outcome.reason_codes),
            "owner": "#49",
            "semantic_iri": outcome.semantic_iri or None,
        }
        for outcome in reconciliation.rows
    ]
    semantics = {
        **ZERO_SEMANTICS,
        "concepts": reconciliation.emitted_concept_count,
        "roots": reconciliation.emitted_root_count,
    }
    domain = _domain(rows, semantics, dict(reconciliation.notation_counts), ())
    source = {
        "domain": "atomic",
        "artifact": "morphemes_atomic-source",
        "sha256": reconciliation.atomic_source_sha256,
    }
    return domain, source


def lexicon_domain(
    closure: CompilerClosure,
    result: LexiconReconciliation,
) -> tuple[dict, dict]:
    receipt = result.receipt
    counts = receipt["counts"]
    held_roots = {
        item["root_id"]: tuple(item["reasons"])
        for item in receipt["debt"]["held_roots"]
    }
    held_senses = {
        item["source_sense_id"]: tuple(item["reasons"])
        for item in receipt["debt"]["held_senses"]
    }
    rows = []
    for row in closure.table("lexicon_roots").rows:
        key = row["lexicon_root_id"]
        held = held_roots.get(key)
        rows.append(
            {
                "table": "lexicon_roots",
                "key": key,
                "status": "HELD" if held else "EMITTED",
                "reason_code": "+".join(held) if held else "EMITTED_LEXICON_ROOT",
                "owner": "#55",
                "semantic_iri": Identity("root", (row["source_id"], key)).iri,
            }
        )
    for row in closure.table("lexicon_root_senses").rows:
        key = row["lexicon_sense_id"]
        held = held_senses.get(key)
        identity = sense_from_source("lexicon_root_senses", dict(row.values))
        rows.append(
            {
                "table": "lexicon_root_senses",
                "key": key,
                "status": "HELD" if held else "EMITTED",
                "reason_code": "+".join(held) if held else "EMITTED_LEXICON_SENSE",
                "owner": "#55",
                "semantic_iri": identity.iri,
            }
        )
    rows.extend(
        {
            "table": "lexicon_root_evidence",
            "key": row["lexicon_evidence_id"],
            "status": "IR_ONLY",
            "reason_code": "LEXICON_SOURCE_EVIDENCE_SUPPORT_IR_ONLY",
            "owner": "#55",
            "semantic_iri": None,
        }
        for row in closure.table("lexicon_root_evidence").rows
    )
    semantics = {
        **ZERO_SEMANTICS,
        "roots": counts["root_resources_emitted"],
        "senses": counts["sense_concepts_emitted"],
    }
    debt = []
    extraction_debt = Counter(
        row["evidence_kind"].upper()
        for row in closure.table("lexicon_root_evidence").rows
        if row["evidence_kind"].startswith("debt_")
    )
    debt.extend(
        {"code": "LEXICON_EXTRACTION_" + reason, "count": count, "blocking": False}
        for reason, count in sorted(extraction_debt.items())
    )
    zero_sense = len(receipt["debt"]["roots_with_zero_parsed_sense_ids"])
    if zero_sense:
        debt.append(
            {
                "code": "LEXICON_ROOTS_ZERO_PARSED_SENSES",
                "count": zero_sense,
                "blocking": False,
            }
        )
    outside = len(receipt["frontier"]["outside_closure"])
    if outside:
        debt.append(
            {
                "code": "LEXICON_OUTSIDE_TRACKED_FRONTIER",
                "count": outside,
                "blocking": False,
            }
        )
    domain = _domain(rows, semantics, _notation_counts(result.graph), debt)
    source = {
        "domain": "lexicon",
        "artifact": "lexicon-source",
        "sha256": receipt["source"]["lexicon_source_sha256"],
    }
    return domain, source


def residue_domain(result: ResidueReconciliation) -> tuple[dict, dict]:
    receipt = result.receipt
    rows = []
    known_tables = {
        "affix_degrees",
        "morpheme_compositions",
        "composition_components",
        "allomorph_rules",
    }
    for table, table_receipt in sorted(receipt["tables"].items()):
        if table not in known_tables:
            raise ProfileError("COVERAGE_RESIDUE_TABLE_UNKNOWN", table)
        emitted = set(table_receipt["emitted_ids"])
        held = {item["id"]: tuple(item["reasons"]) for item in table_receipt["held"]}
        ir_only = {item["id"]: item["reason"] for item in table_receipt["ir_only"]}
        all_ids = emitted | set(held) | set(ir_only)
        if len(all_ids) != table_receipt["source_count"]:
            raise ProfileError("COVERAGE_RESIDUE_ROW_COUNT_MISMATCH", table)
        for key in sorted(all_ids):
            if key in emitted:
                status, reason = "EMITTED", "EMITTED_RESIDUE_RDF"
            elif key in held:
                status, reason = "HELD", "+".join(held[key])
            else:
                status, reason = "IR_ONLY", ir_only[key]
            rows.append(
                {
                    "table": table,
                    "key": key,
                    "status": status,
                    "reason_code": reason,
                    "owner": "#61",
                    "semantic_iri": None,
                }
            )
    semantics = {
        **ZERO_SEMANTICS,
        "compositions": len(receipt["tables"]["morpheme_compositions"]["emitted_ids"]),
        "allomorphs": len(receipt["tables"]["allomorph_rules"]["emitted_ids"]),
    }
    domain = _domain(rows, semantics, _notation_counts(result.graph), ())
    source = {
        "domain": "residue",
        "artifact": "residue-source",
        "sha256": receipt["residue_source_sha256"],
    }
    return domain, source


def mapping_domain(result: MappingCorpusResult) -> tuple[dict, dict]:
    receipt = result.receipt
    rows = [
        {
            "table": entry["table"],
            "key": entry["key"],
            "status": entry["status"],
            "reason_code": entry["reason_code"],
            "owner": "#66",
            "semantic_iri": None,
        }
        for entry in receipt["entries"]
    ]
    semantics = {
        **ZERO_SEMANTICS,
        "mappings": receipt["dispositions"]["EMITTED"],
    }
    review = receipt["dispositions"]["HELD"] + receipt["dispositions"]["REJECTED"]
    debt = (
        [{"code": "MAPPING_SEMANTIC_REVIEW_REQUIRED", "count": review, "blocking": False}]
        if review
        else []
    )
    domain = _domain(rows, semantics, _notation_counts(result.graph), debt)
    source = {
        "domain": "mapping",
        "artifact": "mapping-source",
        "sha256": receipt["input_sha256"],
    }
    return domain, source
