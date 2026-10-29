"""Reconcile existing token identity and meaning fingerprints with pinned source.

Read-only compatibility adapter. No semantic IDs are allocated or admitted.
"""
from __future__ import annotations

from ..semantics.foundation.catalog import Catalog
from ..semantics.foundation.core import Operation, Signature, TypedError


def bind_source_catalog(tokens, source_graph: dict, symbols, *,
                        historical_graph_sha256: str) -> Catalog:
    if (not historical_graph_sha256 or not isinstance(source_graph, dict) or
            not isinstance(source_graph.get("tokens"), list) or
            not isinstance(source_graph.get("row_contract_sha256"), dict)):
        raise TypedError("COMPOSITION_INVALID_SOURCE_CATALOG")
    entries = tuple(tokens)
    by_symbol = {entry.symbol: entry for entry in entries}
    if len(by_symbol) != len(entries):
        raise TypedError("COMPOSITION_DUPLICATE_SOURCE_BINDING")
    requested = tuple(symbols)
    if len(set(requested)) != len(requested):
        raise TypedError("COMPOSITION_DUPLICATE_REQUESTED_SEMANTIC")
    result = []
    for symbol in requested:
        node = by_symbol.get(symbol)
        if node is None:
            raise TypedError("COMPOSITION_UNRESOLVED_SEMANTIC_ID")
        if (type(node.id) is not int or node.id < 0 or
                node.id >= len(source_graph["tokens"]) or
                source_graph["tokens"][node.id] != node.symbol):
            raise TypedError("COMPOSITION_SOURCE_TOKEN_IDENTITY_DRIFT")
        if (node.graph_sha256 != historical_graph_sha256 or
                source_graph["row_contract_sha256"].get(symbol) != node.contract_sha256):
            raise TypedError("COMPOSITION_SOURCE_MEANING_CONTRACT_DRIFT")
        try:
            signature = Signature.parse(node.signature)
            count = int(node.arity)
        except (ValueError, TypeError) as exc:
            raise TypedError("COMPOSITION_INVALID_SOURCE_SIGNATURE") from exc
        if count != len(signature.inputs):
            raise TypedError("COMPOSITION_SOURCE_ARITY_DRIFT")
        result.append(Operation(node.id, symbol, signature, node.contract_sha256))
    return Catalog(tuple(result))
