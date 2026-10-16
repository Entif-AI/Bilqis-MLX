"""Independent, source-bound expression checking and proof receipts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..semantics.core import Apply, Expression, Literal, Operation, TypedError, expression_digest
from .outcomes import ProofStatus

class Backend(Protocol):
    identity: str

    def invoke(self, operation: Operation, values: tuple[str | bool, ...],
               world_contract: str | None) -> str | bool: ...


def _evaluate(expression: Expression, backend: Backend) -> str | bool:
    if isinstance(expression, Literal):
        return expression.value
    values = tuple(_evaluate(child, backend) for child in expression.arguments)
    return backend.invoke(expression.operator, values, expression.world_contract)


@dataclass(frozen=True)
class Proof:
    expression_sha256: str
    source_backend: str
    independent_backend: str
    result: str | bool
    world_contract: str | None
    status: ProofStatus = ProofStatus.VERIFIED


def verify(expression: Expression, *, source: Backend,
           independent: Backend) -> Proof:
    """Check two independently identified interpreters, never assume gold."""
    if (not isinstance(expression, Apply) or
            source.identity == independent.identity or
            not source.identity or not independent.identity):
        raise TypedError("COMPOSITION_INDEPENDENT_PROOF_REQUIRED")
    result = _evaluate(expression, source)
    other = _evaluate(expression, independent)
    if type(result) is not type(other) or result != other:
        raise TypedError("COMPOSITION_ORACLE_DISAGREEMENT")
    if expression.type_name == "Boolean" and type(result) is not bool:
        raise TypedError("COMPOSITION_ANSWER_TYPE_DRIFT")
    return Proof(expression_digest(expression), source.identity,
                 independent.identity, result, expression.world_contract)
