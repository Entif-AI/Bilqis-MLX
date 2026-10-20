"""Stateless, typed diagnostic broker at the runtime/operator boundary.

Domain functions own their invariants. Diagnostics own machine identity,
localization keys, classification, and the prescribed next safe action.
The bus does not alter learner state or swallow the originating exception.
Legacy ValueError codes remain readable during incremental migration.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import NoReturn


class SemanticCoverageCode(str, Enum):
    PLAN_VERSION_MISMATCH = "SEMANTIC_COVERAGE_PLAN_VERSION_MISMATCH"
    INVALID_AUDIT_BUDGET = "SEMANTIC_COVERAGE_INVALID_AUDIT_BUDGET"


class GradeBCode(str, Enum):
    BALANCED_SAMPLE_REQUIRED = "GRADE_B_BALANCED_EVEN_SAMPLE_REQUIRED"


@dataclass(frozen=True)
class DiagnosticDefinition:
    code: SemanticCoverageCode | GradeBCode
    message_key: str
    disposition: str
    explanation: str
    next_action: str
    safe_check: str = ""


_DEFINITIONS = MappingProxyType({
    SemanticCoverageCode.PLAN_VERSION_MISMATCH: DiagnosticDefinition(
        SemanticCoverageCode.PLAN_VERSION_MISMATCH,
        "semantic_coverage.plan.version_mismatch",
        "PRESERVE_AND_DIAGNOSE",
        "The source-coverage plan's saved schema does not match the active reader.",
        "Regenerate or load the schema-compatible source coverage plan. "
        "Do not alter historical receipts or overwrite the schema field.",
    ),
    SemanticCoverageCode.INVALID_AUDIT_BUDGET: DiagnosticDefinition(
        SemanticCoverageCode.INVALID_AUDIT_BUDGET,
        "semantic_coverage.audit.invalid_budget",
        "CORRECT_INPUT_OR_STATE",
        "An audit resource or sampling parameter violates the declared policy.",
        "Inspect the reported field/rule. Choose a positive bounded round count and "
        "a valid balanced per-capability sample size. The current 32-round ceiling "
        "and two-per-outcome minimum are legacy policy, not proof of semantic coverage.",
    ),
    GradeBCode.BALANCED_SAMPLE_REQUIRED: DiagnosticDefinition(
        GradeBCode.BALANCED_SAMPLE_REQUIRED,
        "grade_b.sampling.balanced_sample_required",
        "CORRECT_INPUT_OR_STATE",
        "The requested number of Boolean specimens cannot satisfy the current "
        "two-class balancing policy.",
        "Choose a balanced integer count that can be divided evenly among the two answer "
        "classes, with the declared minimum per class. For complete operand-truth "
        "coverage, inspect the separate coverage requirements.",
    ),
})


def lookup_definition(
    code: SemanticCoverageCode | GradeBCode,
) -> DiagnosticDefinition:
    """Exhaustive registered contract lookup, never substring classification."""
    return _DEFINITIONS[code]


class DiagnosticError(ValueError):
    """Transport-compatible failure with typed identity and structured facts."""

    def __init__(
        self, code: SemanticCoverageCode | GradeBCode, *,
        context: dict[str, object],
    ):
        self.code = code
        self.definition = lookup_definition(code)
        self.context = MappingProxyType(dict(context))
        evidence = " ".join(f"{field}={value!r}"
                            for field, value in sorted(self.context.items()))
        super().__init__(code.value + (": " + evidence if evidence else ""))


class ErrorBus:
    """One raising boundary. Message rendering and side effects remain outside."""

    @staticmethod
    def Raise(
        code: SemanticCoverageCode | GradeBCode, **context: object,
    ) -> NoReturn:
        raise DiagnosticError(code, context=context)
