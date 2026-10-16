"""Reusable verification methods selected by types, never grade names.

Every returned proof comes from two independently identified interpreters.
The caller remains responsible for source authority and catalog admission.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from .core import (
    Apply, Backend, Operation, Proof, TypedError, curry, expression_digest,
    literal, verify,
)


@dataclass(frozen=True)
class BooleanCase:
    arguments: tuple[bool, ...]
    proof: Proof


@dataclass(frozen=True)
class BooleanCoverage:
    operator_token_index: int
    source_contract_sha256: str
    cases: tuple[BooleanCase, ...]
    expected_patterns: int
    covered_patterns: int
    status: str = "EXHAUSTIVE_FINITE_TRUTH_TABLE"


def exhaustive_boolean_cases(operation: Operation, *, source: Backend,
                             independent: Backend, max_arity: int = 8,
                             world_contract: str | None = None) -> BooleanCoverage:
    """Enumerate every Boolean argument vector with no hidden sampling.

    A coverage certificate applies only to this Boolean input domain; it is
    not a claim of legality in any other source world or language grammar.
    """
    signature = operation.signature
    if (signature.output != "Boolean" or
            any(name != "Boolean" for name in signature.inputs)):
        raise TypedError("COMPOSITION_METHOD_NOT_BOOLEAN")
    if (max_arity < 1 or len(signature.inputs) > max_arity):
        raise TypedError("COMPOSITION_METHOD_EXHAUSTIVE_BUDGET_EXCEEDED")
    cases = []
    for bits in product((False, True), repeat=len(signature.inputs)):
        expr = curry(operation)(*(
            literal(bit, "Boolean", world_contract=world_contract)
            for bit in bits))
        if not isinstance(expr, Apply):
            raise TypedError("COMPOSITION_METHOD_INCOMPLETE_EXPRESSION")
        cases.append(BooleanCase(bits, verify(
            expr, source=source, independent=independent)))
    count = 2 ** len(signature.inputs)
    if len(cases) != count or len({case.arguments for case in cases}) != count:
        raise TypedError("COMPOSITION_METHOD_UNDERCOVERED_TRUTH_PATTERNS")
    return BooleanCoverage(operation.token_index, operation.contract_sha256,
                           tuple(cases), count, len(cases))


def verify_constituents(expression: Apply, *, source: Backend,
                        independent: Backend) -> tuple[Proof, ...]:
    """Source-check every composite subexpression before the whole.

    This creates proof artifacts for independently scored constituents but
    never schedules teaching or claims the learner has mastered those parts.
    """
    if not isinstance(expression, Apply):
        raise TypedError("COMPOSITION_METHOD_REQUIRES_COMPOSED_EXPRESSION")
    proven = set()
    receipts = []

    def visit(node: Apply):
        for child in node.arguments:
            if isinstance(child, Apply):
                visit(child)
        identity = expression_digest(node)
        if identity not in proven:
            receipts.append(verify(node, source=source, independent=independent))
            proven.add(identity)

    visit(expression)
    return tuple(receipts)
