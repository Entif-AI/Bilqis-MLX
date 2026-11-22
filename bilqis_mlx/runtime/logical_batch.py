"""BAMF owner for logical optimizer-batch sizing versus source admissibility."""
from __future__ import annotations

from dataclasses import dataclass

from bilqis_mlx.semantic_sampling import (
    BinaryBalancePolicy,
    DEFAULT_BINARY_BALANCE,
    sample_count_violations,
)


@dataclass(frozen=True)
class BamfLogicalBatchContract:
    """Declare one optimizer objective without promoting a sampling floor to policy."""

    target_rows: int = 32
    source_balance: BinaryBalancePolicy = DEFAULT_BINARY_BALANCE

    def __post_init__(self) -> None:
        violations = sample_count_violations(
            self.target_rows, policy=self.source_balance)
        if violations:
            raise ValueError("BAMF_LOGICAL_BATCH_INVALID")

    @property
    def source_minimum_rows(self) -> int:
        return self.source_balance.minimum_total

    @property
    def direct_source_rows(self) -> int:
        """Current Foundation composition fills the logical target with direct rows."""
        return self.target_rows


__all__ = ("BamfLogicalBatchContract",)
