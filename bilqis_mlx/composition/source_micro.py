"""Typed adapter from the pinned finite-micro source AST to generic composition.

Source syntax is confined to this adapter. No capability/grade identity is
derived, allocated or declared here: token references resolve through Catalog.
"""
from __future__ import annotations

from .core import Apply, Catalog, Expression, TypedError, curry, literal


_ROOT_PREFIX = {
    "compare": ("micro.compare.", "operator"),
    "relation": ("micro.relation.", "name"),
    "apply": ("cogal.operator.", "operator"),
}


def from_micro_query(catalog: Catalog, query: dict, *,
                     world_contract: str = "micro",
                     depth: int = 0) -> Expression:
    """Parse only the known source syntax; unknown dialects require adapters."""
    if not isinstance(query, dict) or depth > 12:
        raise TypedError("COMPOSITION_MICRO_INVALID_AST")
    kind = query.get("kind")
    if kind == "entity":
        if set(query) != {"kind", "name"} or type(query["name"]) is not str:
            raise TypedError("COMPOSITION_MICRO_ENTITY_SHAPE")
        return literal(query["name"], "Entity", world_contract=world_contract)
    if kind == "literal":
        if set(query) != {"kind", "value"} or type(query["value"]) is not bool:
            raise TypedError("COMPOSITION_MICRO_LITERAL_SHAPE")
        return literal(query["value"], "Boolean", world_contract=world_contract)
    if kind not in _ROOT_PREFIX:
        raise TypedError("COMPOSITION_MICRO_UNSUPPORTED_SOURCE_NODE")
    prefix, key = _ROOT_PREFIX[kind]
    if set(query) != {"kind", key, "args"} or not isinstance(query["args"], list):
        raise TypedError("COMPOSITION_MICRO_OPERATOR_SHAPE")
    if not isinstance(query[key], str):
        raise TypedError("COMPOSITION_MICRO_OPERATOR_NAME_INVALID")
    operation = catalog.resolve_external_name(prefix + query[key])
    operands = tuple(from_micro_query(catalog, item, world_contract=world_contract,
                                      depth=depth + 1) for item in query["args"])
    result = curry(operation)(*operands)
    if not isinstance(result, Apply):
        raise TypedError("COMPOSITION_MICRO_INCOMPLETE_APPLICATION")
    return result
