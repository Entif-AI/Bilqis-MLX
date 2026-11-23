"""Qualification helpers for BAMF accelerator work-unit experiments.

Issue #1578 deliberately separates physical C08 execution geometry from the
logical optimizer batch.  These helpers encode that distinction for witness
and test code without changing the production batch-size default.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from bilqis_mlx.errors import ErrorBus, SCHOOL


DEFAULT_LOGICAL_BATCH_SIZE = 32
PHYSICAL_CAPS = (8, 16, 32)
LOGICAL_BATCH_EXPERIMENT_SIZES = (8, 16, 24, 32)
DEFAULT_EQUAL_ROW_BUDGET = 96
C08_EQUIVALENCE_ATOL = 1e-6


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_RESOURCES.INVALID, reason=reason)


@dataclass(frozen=True)
class PhysicalWorkUnitQualification:
    logical_batch_size: int
    rows_per_launch: int
    status: str
    learning_policy_change: bool


@dataclass(frozen=True)
class EqualBudgetArm:
    logical_batch_size: int
    optimizer_steps: int
    row_presentations: int
    learning_policy_experiment: bool


def classify_physical_row_work_unit(
    *,
    logical_batch_size: int,
    rows_per_launch: int,
) -> PhysicalWorkUnitQualification:
    """Classify row-count geometry without silently changing learning semantics."""
    if type(logical_batch_size) is not int or logical_batch_size < 1:
        _invalid("BAMF_C08_LOGICAL_BATCH_SIZE_INVALID")
    if type(rows_per_launch) is not int or rows_per_launch < 1:
        _invalid("BAMF_C08_ROWS_PER_LAUNCH_INVALID")
    if rows_per_launch > logical_batch_size:
        return PhysicalWorkUnitQualification(
            logical_batch_size,
            rows_per_launch,
            "SEMANTIC_CHANGE_REQUIRED",
            True,
        )
    return PhysicalWorkUnitQualification(
        logical_batch_size,
        rows_per_launch,
        "SEMANTICS_PRESERVING",
        False,
    )


def equal_row_budget_schedule(
    *,
    row_budget: int = DEFAULT_EQUAL_ROW_BUDGET,
    batch_sizes: tuple[int, ...] = LOGICAL_BATCH_EXPERIMENT_SIZES,
) -> tuple[EqualBudgetArm, ...]:
    """Build an explicit equal-row-presentation learning-policy experiment."""
    if type(row_budget) is not int or row_budget < 1:
        _invalid("BAMF_C08_EQUAL_ROW_BUDGET_INVALID")
    if (
        not isinstance(batch_sizes, tuple)
        or not batch_sizes
        or any(type(size) is not int or size < 1 for size in batch_sizes)
    ):
        _invalid("BAMF_C08_LOGICAL_BATCH_SIZES_INVALID")
    if any(row_budget % size for size in batch_sizes):
        _invalid("BAMF_C08_EQUAL_ROW_BUDGET_NOT_DIVISIBLE")
    return tuple(
        EqualBudgetArm(
            logical_batch_size=size,
            optimizer_steps=row_budget // size,
            row_presentations=row_budget,
            learning_policy_experiment=(size != DEFAULT_LOGICAL_BATCH_SIZE),
        )
        for size in batch_sizes
    )


def physical_result_contract_equivalent(
    results: tuple[dict, ...] | list[dict],
    *,
    logical_batch_size: int = DEFAULT_LOGICAL_BATCH_SIZE,
    atol: float = C08_EQUIVALENCE_ATOL,
) -> bool:
    """Check the bounded witness invariants without demanding bitwise FP32 identity."""
    if not results:
        return False
    baseline = results[-1]
    try:
        baseline_step = int(baseline["optimizer_step"])
        baseline_loss = float(baseline["loss_total"])
    except (KeyError, TypeError, ValueError):
        return False
    return all(
        int(result.get("logical_batch_size", -1)) == logical_batch_size
        and int(result.get("optimizer_step", -1)) == baseline_step
        and math.isclose(
            float(result.get("loss_total")),
            baseline_loss,
            rel_tol=0.0,
            abs_tol=atol,
        )
        for result in results
    )
