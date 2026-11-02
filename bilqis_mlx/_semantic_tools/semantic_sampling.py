"""Pure sampling rules shared by source construction and source-coverage audits.

The existing two-per-outcome floor and 32-round audit ceiling are **historical
policy choices**, not proofs of semantic coverage or source-derived constants.
Keeping them as explicit inputs preserves compatibility without pretending
that they are mathematical necessities. Source coverage is measured separately.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, TypeVar


BOOLEAN_ANSWER_SET = frozenset((True, False))


class SamplingRule(str, Enum):
    INTEGER_REQUIRED = "INTEGER_REQUIRED"
    INSUFFICIENT_PER_OUTCOME = "INSUFFICIENT_PER_OUTCOME"
    NONUNIFORM_OUTCOME_ALLOCATION = "NONUNIFORM_OUTCOME_ALLOCATION"
    ROUND_BUDGET_OUT_OF_RANGE = "ROUND_BUDGET_OUT_OF_RANGE"
    INVALID_POLICY_CONFIGURATION = "INVALID_POLICY_CONFIGURATION"


@dataclass(frozen=True)
class SamplingViolation:
    field: str
    rule: SamplingRule
    observed: object
    expected: str


class InvalidSamplingPolicy(ValueError):
    """Typed contract exception for constructing an invalid sampling policy."""

    def __init__(self, violations: tuple[SamplingViolation, ...]):
        self.violations = violations
        super().__init__("; ".join(
            f"{issue.rule.value} field={issue.field} observed={issue.observed!r} "
            f"expected={issue.expected}"
            for issue in violations
        ))


@dataclass(frozen=True)
class BinaryBalancePolicy:
    """Two balanced answer classes; minimum repetitions remain configurable."""

    minimum_per_outcome: int = 2  # Legacy choice, not a coverage theorem.
    outcomes: tuple[bool, bool] = (True, False)

    def __post_init__(self) -> None:
        if (type(self.minimum_per_outcome) is not int or
                self.minimum_per_outcome < 1):
            raise InvalidSamplingPolicy((SamplingViolation(
                "minimum_per_outcome", SamplingRule.INVALID_POLICY_CONFIGURATION,
                self.minimum_per_outcome, "positive integer",
            ),))
        if (type(self.outcomes) is not tuple or
                len(self.outcomes) != len(BOOLEAN_ANSWER_SET) or
                set(self.outcomes) != BOOLEAN_ANSWER_SET or
                any(type(item) is not bool for item in self.outcomes)):
            raise InvalidSamplingPolicy((SamplingViolation(
                "outcomes", SamplingRule.INVALID_POLICY_CONFIGURATION,
                self.outcomes, "two distinct Boolean answer outcomes",
            ),))

    @property
    def minimum_total(self) -> int:
        return len(self.outcomes) * self.minimum_per_outcome


@dataclass(frozen=True)
class AuditPolicy:
    """The legacy resource ceiling is separate from semantic admissibility."""

    minimum_rounds: int = 1
    max_rounds: int = 32  # No source-backed rationale found for this ceiling.
    sample_policy: BinaryBalancePolicy = BinaryBalancePolicy()

    def __post_init__(self) -> None:
        if (type(self.minimum_rounds) is not int or self.minimum_rounds < 1 or
                type(self.max_rounds) is not int or
                self.max_rounds < self.minimum_rounds or
                not isinstance(self.sample_policy, BinaryBalancePolicy)):
            raise InvalidSamplingPolicy((SamplingViolation(
                "audit_policy", SamplingRule.INVALID_POLICY_CONFIGURATION,
                (self.minimum_rounds, self.max_rounds, self.sample_policy),
                "positive integer minimum, maximum >= minimum, and balanced sample policy",
            ),))


DEFAULT_BINARY_BALANCE = BinaryBalancePolicy()
LEGACY_AUDIT_POLICY = AuditPolicy()


def sample_count_violations(
    count: object, *, policy: BinaryBalancePolicy = DEFAULT_BINARY_BALANCE,
) -> tuple[SamplingViolation, ...]:
    """Return independently inspectable violations without raising or I/O."""
    if type(count) is not int:
        return (SamplingViolation("each", SamplingRule.INTEGER_REQUIRED, count, "int"),)
    issues = []
    if count < policy.minimum_total:
        issues.append(SamplingViolation(
            "each", SamplingRule.INSUFFICIENT_PER_OUTCOME, count,
            f"at least {policy.minimum_per_outcome} per outcome "
            f"({policy.minimum_total} total)",
        ))
    if count % len(policy.outcomes):
        issues.append(SamplingViolation(
            "each", SamplingRule.NONUNIFORM_OUTCOME_ALLOCATION, count,
            f"multiple of {len(policy.outcomes)} answer classes",
        ))
    return tuple(issues)


def audit_budget_violations(
    rounds: object, each: object, *, policy: AuditPolicy = LEGACY_AUDIT_POLICY,
) -> tuple[SamplingViolation, ...]:
    """Check resource and sample requirements independently; report all defects."""
    issues = []
    if type(rounds) is not int:
        issues.append(SamplingViolation(
            "max_rounds", SamplingRule.INTEGER_REQUIRED, rounds, "int",
        ))
    elif not policy.minimum_rounds <= rounds <= policy.max_rounds:
        issues.append(SamplingViolation(
            "max_rounds", SamplingRule.ROUND_BUDGET_OUT_OF_RANGE, rounds,
            f"{policy.minimum_rounds}..{policy.max_rounds} rounds",
        ))
    issues.extend(sample_count_violations(each, policy=policy.sample_policy))
    return tuple(issues)


def balanced_answer_targets(
    count: int, *, policy: BinaryBalancePolicy = DEFAULT_BINARY_BALANCE,
) -> tuple[bool, ...]:
    """Deterministic two-class targets; construction refuses unbalanced shapes."""
    violations = sample_count_violations(count, policy=policy)
    if violations:
        raise InvalidSamplingPolicy(violations)
    return tuple(policy.outcomes[index % len(policy.outcomes)]
                 for index in range(count))


Case = TypeVar("Case")


def missing_coverage_cases(
    required: Iterable[Case], observed: Iterable[Case],
) -> tuple[Case, ...]:
    """Actual semantic pattern coverage is distinct from balanced answer counts."""
    observed_set = set(observed)
    return tuple(case for case in required if case not in observed_set)
