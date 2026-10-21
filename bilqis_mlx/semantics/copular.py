"""A scoped formal realization of New Ithkuil -Č-, Stem 1/BSC.

Entities serve as opaque references in a declared total denotation map. Identity
compares their denotations. This contract does not realize Ithkuil morphology.
The operator must receive its own catalog identity before neural use.
"""
from __future__ import annotations

from dataclasses import dataclass

from .core import Apply, Literal, Operation, Signature, literal
from .functions import curry
from ..vocabulary_growth import _check_catalog


SYMBOL = "ithkuil.op.COPULAR_IDENTITY"
SEMANTIC_ID = "ithkuil:LEXSENSE-5286ade9db42c7/finite-reference-identity/v1"
WORLD = "bilqis.finite-reference-world/v1"
ENTITIES = tuple("ABCDE")


@dataclass(frozen=True)
class ReferentWorld:
    entities: tuple[str, ...]
    denotations: tuple[tuple[str, str], ...]

    def __post_init__(self):
        if (not isinstance(self.entities, tuple) or
                not 2 <= len(self.entities) <= len(ENTITIES) or
                len(set(self.entities)) != len(self.entities) or
                not set(self.entities) <= set(ENTITIES) or
                not isinstance(self.denotations, tuple) or
                len(self.denotations) != len(self.entities) or
                any(not isinstance(p, tuple) or len(p) != 2 or
                    any(v not in self.entities for v in p) for p in self.denotations) or
                {p[0] for p in self.denotations} != set(self.entities)):
            raise ValueError("COPULAR_WORLD_NOT_TOTAL_SINGLE_VALUED")


def bind_operation(graph: dict) -> Operation:
    """Resolve an explicit append-only identity; never allocate one here."""
    _check_catalog(graph)
    if SYMBOL not in graph["tokens"]:
        raise ValueError("COPULAR_TOKEN_NOT_ADMITTED")
    index = graph["tokens"].index(SYMBOL)
    node = graph["nodes"][index]
    if (node.get("semantic_id") != SEMANTIC_ID or node.get("arity") != 2 or
            node.get("signature") != "Entity*Entity->Boolean"):
        raise ValueError("COPULAR_TOKEN_CONTRACT_DRIFT")
    return Operation(index, SYMBOL, Signature(("Entity", "Entity"), "Boolean"),
                     graph["row_contract_sha256"][SYMBOL], WORLD)


def identify(operation: Operation, left: str, right: str) -> Apply:
    return curry(operation)(literal(left, "Entity", world_contract=WORLD),
                            literal(right, "Entity", world_contract=WORLD))


def references(expression: Apply) -> tuple[str, str]:
    if (not isinstance(expression, Apply) or
            expression.operator.symbol != SYMBOL or
            expression.operator.signature != Signature(("Entity", "Entity"), "Boolean") or
            expression.operator.world_contract != WORLD or
            any(not isinstance(arg, Literal) or arg.type_name != "Entity" or
                arg.world_contract != WORLD or arg.value not in ENTITIES
                for arg in expression.arguments)):
        raise ValueError("COPULAR_QUERY_OUTSIDE_SOURCE_SCOPE")
    return tuple(arg.value for arg in expression.arguments)


def evaluate(world: ReferentWorld, expression: Apply) -> bool:
    left, right = references(expression)
    denotations = dict(world.denotations)
    if left not in denotations or right not in denotations:
        raise ValueError("COPULAR_REFERENCE_UNDECLARED")
    return denotations[left] == denotations[right]
