"""Finite countermodel checks for unadmitted, typed semantic law candidates."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from ..semantics.foundation.catalog import Catalog
from ..semantics.foundation.core import Apply, Expression, TypedError, expression_digest
from ..semantics.foundation.laws import LawCandidate, LawErrorCode, SourceLocator
from .expressions import Backend, verify
from .outcomes import LawCheckStatus


@dataclass(frozen=True)
class LawCheck:
    subject_token_index: int
    subject_contract_sha256: str
    source: SourceLocator
    status: LawCheckStatus
    scope: str
    evaluated: int
    original_sha256: str | None = None
    transformed_sha256: str | None = None
    original_result: str | bool | None = None
    transformed_result: str | bool | None = None

    def __post_init__(self) -> None:
        is_counterexample = self.status is LawCheckStatus.COUNTEREXAMPLE
        evidence = (
            self.original_sha256, self.transformed_sha256,
            self.original_result, self.transformed_result,
        )
        if (type(self.subject_token_index) is not int or self.subject_token_index < 0 or
                not re.fullmatch(r"[0-9a-f]{64}", self.subject_contract_sha256) or
                not isinstance(self.source, SourceLocator) or
                not isinstance(self.status, LawCheckStatus) or
                type(self.evaluated) is not int or self.evaluated < 0 or
                not isinstance(self.scope, str) or not self.scope.strip() or
                (is_counterexample and (self.evaluated == 0 or
                                        not all(item is not None for item in evidence))) or
                (not is_counterexample and any(item is not None for item in evidence)) or
                (is_counterexample and (
                    type(self.original_result) is not type(self.transformed_result) or
                    self.original_result == self.transformed_result)) or
                (self.status is LawCheckStatus.VERIFIED_FINITE_SCOPE and
                 self.evaluated == 0) or
                (self.status is LawCheckStatus.UNKNOWN_NO_APPLICABLE_CASES and
                 self.evaluated != 0)):
            raise TypedError(LawErrorCode.INVALID_CHECK_RECEIPT.value)


def check_finite_equivalence(
    law: LawCandidate, specimens: Iterable[Expression], *, catalog: Catalog,
    source: Backend,
    independent: Backend, scope: str,
) -> LawCheck:
    """Falsify equivalence on a declared finite cohort, never claim universality.

    Precondition-false specimens do not count toward proof. An empty applicable
    cohort is UNKNOWN. Source disagreement is never converted into a law pass.
    """
    if not isinstance(law, LawCandidate) or not isinstance(scope, str) or not scope.strip():
        raise TypedError(LawErrorCode.MISSING_CANDIDATE_OR_SCOPE.value)
    if not isinstance(catalog, Catalog) or catalog.get(law.subject.token_index) != law.subject:
        raise TypedError(LawErrorCode.SUBJECT_NOT_CATALOG_BOUND.value)

    def check_binding(expression: Expression) -> None:
        if isinstance(expression, Apply):
            if catalog.get(expression.operator.token_index) != expression.operator:
                raise TypedError(LawErrorCode.EXPRESSION_NOT_CATALOG_BOUND.value)
            for argument in expression.arguments:
                check_binding(argument)

    checked = 0
    for original in specimens:
        if original.type_name != law.input_type:
            raise TypedError(LawErrorCode.INPUT_TYPE_MISMATCH.value)
        if original.world_contract != law.world_contract:
            raise TypedError(LawErrorCode.INPUT_WORLD_MISMATCH.value)
        if not law.precondition(original):
            continue
        check_binding(original)
        transformed = law.transform(original)
        if (not isinstance(original, Apply) or
                not isinstance(transformed, Apply) or
                transformed.type_name != original.type_name or
                transformed.world_contract != original.world_contract):
            raise TypedError(LawErrorCode.INVALID_TRANSFORMATION.value)
        check_binding(transformed)
        first = verify(original, source=source, independent=independent)
        second = verify(transformed, source=source, independent=independent)
        checked += 1
        if first.result != second.result or type(first.result) is not type(second.result):
            return LawCheck(law.subject.token_index, law.subject.contract_sha256,
                            law.source, LawCheckStatus.COUNTEREXAMPLE, scope,
                            checked, expression_digest(original),
                            expression_digest(transformed), first.result,
                            second.result)
    status = (LawCheckStatus.VERIFIED_FINITE_SCOPE if checked else
              LawCheckStatus.UNKNOWN_NO_APPLICABLE_CASES)
    return LawCheck(law.subject.token_index, law.subject.contract_sha256,
                    law.source, status, scope, checked)
