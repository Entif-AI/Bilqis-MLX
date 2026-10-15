"""Complete checkpoint pointers, grade-linked votes and teacher-only soup weights.

The pointer map expresses distinct *grade entitlements*, not distinct copies of
weights. Never use this module to merge optimizer moments or manufacture a
synthetic trainable whole-student checkpoint.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Checkpoint:
    sha256: str
    filename: str
    optimizer_step: int
    model_and_native_adamw: bool

    def __post_init__(self):
        if (not re.fullmatch(r"[0-9a-f]{64}", self.sha256) or
                not self.filename or self.optimizer_step < 0 or
                not self.model_and_native_adamw):
            raise ValueError("INCOMPLETE_STUDENT_CHECKPOINT")


def vote_counts(grade_champions: dict[str, Checkpoint],
                *, grade_order: tuple[str, ...], active_grade: str) -> dict[str, int]:
    """One vote per prior mastered grade, independent of checkpoint deduping."""
    if active_grade not in grade_order:
        raise ValueError("UNKNOWN_ACTIVE_GRADE")
    earlier = set(grade_order[:grade_order.index(active_grade)])
    if any(g not in grade_order for g in grade_champions):
        raise ValueError("CHAMPION_POINTER_UNKNOWN_GRADE")
    return dict(sorted(Counter(cp.sha256 for grade, cp in grade_champions.items()
                               if grade in earlier).items()))


def soup_weights(grade_champions: dict[str, Checkpoint]) -> dict[str, int]:
    """Grade-pointer multiplicity becomes whole-school soup weight."""
    return dict(sorted(Counter(cp.sha256 for cp in grade_champions.values()).items()))


def repoint_earlier(grade_champions: dict[str, Checkpoint],
                    candidate: Checkpoint, *, previously_passed: tuple[str, ...],
                    fully_mastered_at_this_candidate: tuple[str, ...]
                    ) -> dict[str, Checkpoint]:
    """Only an actual same-candidate 100% pass can change an old grade pointer."""
    result = dict(grade_champions)
    for grade in previously_passed:
        if grade not in result:
            raise ValueError("CANNOT_REPOINT_UNGRADUATED_GRADE")
        if grade in fully_mastered_at_this_candidate:
            result[grade] = candidate
    return result
