"""Finite countermodel checks for catalog-supplied, typed semantic laws.

This does not register laws or create semantic IDs. Admission belongs to the
canonical catalog; the caller supplies independently approved law metadata.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .core import Apply, Backend, Expression, TypedError, verify, expression_digest


@dataclass(frozen=True)
class LawContract:
    """A reference to a law admitted by the authoritative semantic catalog."""

    identity: str
    release: str
    source_claim: str
    input_type: str
    world_contract: str | None
    precondition: Callable[[Expression], bool]
    transform: Callable[[Expression], Expression]


@dataclass(frozen=True)
class LawCheck:
    law_identity: str
    release: str
    status: str
    scope: str
    evaluated: int
    original_sha256: str | None = None
    transformed_sha256: str | None = None
    original_result: str | bool | None = None
    transformed_result: str | bool | None = None


def check_finite_equivalence(
    law: LawContract, specimens: Iterable[Expression], *, source: Backend,
    independent: Backend, scope: str,
) -> LawCheck:
    """Falsify equivalence on a declared finite cohort, never claim universality.

    Precondition-false specimens do not count toward proof. An empty applicable
    cohort is UNKNOWN. Source disagreement is never converted into a law pass.
    """
    if not law.identity or not law.release or not law.source_claim or not scope:
        raise TypedError("LAW_MISSING_AUTHORITY_OR_SCOPE")
    checked = 0
    for original in specimens:
        if original.type_name != law.input_type:
            raise TypedError("LAW_INPUT_TYPE_MISMATCH")
        if original.world_contract != law.world_contract:
            raise TypedError("LAW_INPUT_WORLD_MISMATCH")
        if not law.precondition(original):
            continue
        transformed = law.transform(original)
        if (not isinstance(original, Apply) or
                not isinstance(transformed, Apply) or
                transformed.type_name != original.type_name or
                transformed.world_contract != original.world_contract):
            raise TypedError("LAW_INVALID_TRANSFORMATION")
        first = verify(original, source=source, independent=independent)
        second = verify(transformed, source=source, independent=independent)
        checked += 1
        if first.result != second.result or type(first.result) is not type(second.result):
            return LawCheck(law.identity, law.release, "COUNTEREXAMPLE", scope,
                            checked, expression_digest(original),
                            expression_digest(transformed), first.result,
                            second.result)
    return LawCheck(law.identity, law.release,
                    "VERIFIED_FINITE_SCOPE" if checked else "UNKNOWN_NO_APPLICABLE_CASES",
                    scope, checked)
