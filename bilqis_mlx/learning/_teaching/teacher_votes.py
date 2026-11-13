"""Grade-linked votes with unique-checkpoint inference caching.

Teacher *decision policy* is deliberately not implemented here. The adaptive
teacher still decides strategy, depth, repetition, rehearsal and admission.
These functions guarantee each historical grade receives one independent vote
ENTITLEMENT, even if several grades point to one cached frozen model.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from bilqis_mlx.learning.champions import Checkpoint


@dataclass(frozen=True)
class GradeVote:
    grade: str
    checkpoint_sha256: str


def roster(champions: dict[str, Checkpoint],
           grade_order: tuple[str, ...], active_grade: str) -> tuple[GradeVote, ...]:
    if active_grade not in grade_order or any(g not in grade_order for g in champions):
        raise ValueError("INVALID_TEACHER_GRADE_ROSTER")
    return tuple(GradeVote(g,champions[g].sha256)
                 for g in grade_order[:grade_order.index(active_grade)]
                 if g in champions)


def unique_inference_targets(votes: tuple[GradeVote, ...]) -> tuple[str, ...]:
    """Run expensive inference once per unique model, not per pointer."""
    return tuple(sorted({vote.checkpoint_sha256 for vote in votes}))


def tally(votes: tuple[GradeVote, ...],
          checkpoint_ballots: dict[str, str]) -> dict[str, int]:
    """Count one ballot per grade, using one inference result per model hash."""
    if set(checkpoint_ballots) != set(unique_inference_targets(votes)):
        raise ValueError("TEACHER_BALLOTS_NOT_COMPLETE_OR_INCLUDE_UNREGISTERED")
    if any(not ballot for ballot in checkpoint_ballots.values()):
        raise ValueError("TEACHER_EMPTY_BALLOT")
    return dict(sorted(Counter(checkpoint_ballots[v.checkpoint_sha256]
                               for v in votes).items()))
