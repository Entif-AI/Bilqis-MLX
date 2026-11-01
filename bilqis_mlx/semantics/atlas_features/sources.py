"""Source-role attestation and deterministic source-graph features."""
from __future__ import annotations
import hashlib
from pathlib import Path

from ..atlas_projection import FrozenAtlasSnapshot


from .common import GRAPH_DIM, GRAPH_HASH_START, GRAPH_HASH_WIDTH, GRAPH_SIGN_BYTE_INDEX, EDGE_TARGET_INDEX, _BROADER, _NARROWER, _ROOT_SENSE, _invalid, _utf8, _sorted_ids, _normalized_count

def _source_rule_categories(
    release: FrozenAtlasSnapshot,
    source_bindings: tuple[tuple[str, str], ...],
) -> tuple[str, ...]:
    """Prove schema IDs and roles against A03's pinned released source graph."""
    if not source_bindings:
        return ()
    from ...grade_a_probe import read_sources
    from ...live_grade_c import registry_graph
    from ..frame_adapters import (
        BOOLEAN_COMPOSITE_ADAPTER, BOOLEAN_CONNECTIVE_ADAPTER,
        BOOLEAN_IDENTIFICATION_ADAPTER, FINITE_NUMERIC_ADAPTER,
        MICRO_PREDICATE_ADAPTER, _schema_for_symbol,
    )
    from ..frame_schema import SourceSpan

    source_root = Path(__file__).resolve().parents[3] / "vendor/legacy-v16"
    micro_graph = read_sources(source_root)[2]
    numeric_graph = registry_graph()
    graphs = {
        MICRO_PREDICATE_ADAPTER: micro_graph,
        BOOLEAN_CONNECTIVE_ADAPTER: micro_graph,
        BOOLEAN_COMPOSITE_ADAPTER: micro_graph,
        BOOLEAN_IDENTIFICATION_ADAPTER: micro_graph,
        FINITE_NUMERIC_ADAPTER: numeric_graph,
    }
    entries = {
        "frame:" + entry.semantic_id: entry
        for entry in release.abi_entries if entry.active
    }
    roles: set[str] = set()
    for schema_id, adapter_id in source_bindings:
        entry = entries.get(schema_id)
        graph = graphs.get(adapter_id)
        if (entry is None or entry.symbol is None or graph is None
                or not 0 <= entry.index < len(graph["tokens"])
                or graph["tokens"][entry.index] != entry.symbol):
            _invalid("BAMF_FEATURE_SOURCE_SCHEMA_UNVERIFIED")
        source_schema, _ = _schema_for_symbol(
            release, graph, entry.symbol, "source:" + entry.symbol,
            adapter_id=adapter_id,
            span=SourceSpan(0, 1), scope="source-rule")
        if source_schema.schema_id != schema_id:
            _invalid("BAMF_FEATURE_SOURCE_SCHEMA_UNVERIFIED")
        roles.update(role.role_id for role in source_schema.roles)
    return _sorted_ids(tuple(roles))


def _graph_vector(
    identifier: str,
    type_ids: tuple[str, ...],
    source_forms: int,
    source_senses: int,
    unresolved: bool,
    relations: tuple[tuple[str, str, str], ...],
    types_by_id: dict[str, tuple[str, ...]],
) -> tuple[float, ...]:
    incoming = [edge for edge in relations
                if edge[EDGE_TARGET_INDEX] == identifier]
    outgoing = [edge for edge in relations if edge[0] == identifier]
    values = [0.0] * GRAPH_DIM
    counts = (
        len(incoming), len(outgoing),
        sum(edge[1] == _BROADER for edge in outgoing),
        sum(edge[1] == _NARROWER for edge in outgoing),
        len(type_ids), source_forms, source_senses,
    )
    for index, count in enumerate(counts):
        values[index] = _normalized_count(count)
    values[7] = 1.0 if unresolved else 0.0
    signatures = []
    for source, predicate, target in outgoing:
        for neighbor_type in types_by_id[target] or ("UNKNOWN",):
            signatures.append("out|" + predicate + "|" + neighbor_type)
    for source, predicate, target in incoming:
        for neighbor_type in types_by_id[source] or ("UNKNOWN",):
            signatures.append("in|" + predicate + "|" + neighbor_type)
    signatures.sort(key=_utf8)
    for signature in signatures:
        digest = hashlib.sha256(
            ("bamf.graph.v2|" + signature).encode("utf-8")).digest()
        channel = GRAPH_HASH_START + (
            int.from_bytes(digest[:8], "little") % GRAPH_HASH_WIDTH)
        sign = 1.0 if digest[GRAPH_SIGN_BYTE_INDEX] & 1 == 0 else -1.0
        values[channel] += sign / len(signatures)
    return tuple(values)



def _senses_by_root(source_concepts, relations):
    source_sense_targets = {
        identifier for identifier, concept in source_concepts.items()
        if concept.kind == "sense" and any(
            ref.table == "lexicon_root_senses"
            for ref in concept.source_rows)
    }
    senses_by_root: dict[str, set[str]] = {}
    for source_id, predicate, target_id in relations:
        if (predicate in (_ROOT_SENSE, _NARROWER)
                and target_id in source_sense_targets
                and source_id in source_concepts
                and source_concepts[source_id].kind == "root"):
            senses_by_root.setdefault(source_id, set()).add(target_id)
        if (predicate == _BROADER and source_id in source_sense_targets
                and target_id in source_concepts
                and source_concepts[target_id].kind == "root"):
            senses_by_root.setdefault(target_id, set()).add(source_id)
    return senses_by_root
