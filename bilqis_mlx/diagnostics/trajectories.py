"""Paired checkpoint score trajectories on one unchanged qualifying exam.

This evidence uses exam cohort identity and whole-student checkpoint custody;
it does not require per-instruction specimen identities or assign causality.
"""
from __future__ import annotations

from dataclasses import dataclass

from .observations import CapabilityObservation, ExamObservation


MIN_RETENTION_OBSERVATIONS = 3  # initial, intervening, and later measurement


@dataclass(frozen=True)
class CohortTrajectory:
    cohort_sha256: str
    scores_by_step: tuple[tuple[int, int, int], ...]

    @property
    def first_correct(self) -> int:
        return self.scores_by_step[0][1]

    @property
    def peak_correct(self) -> int:
        return max(score for _, score, _ in self.scores_by_step)

    @property
    def latest_correct(self) -> int:
        return self.scores_by_step[-1][1]

    @property
    def no_lasting_gain(self) -> bool:
        return self.latest_correct <= self.first_correct

    @property
    def regressed_from_peak(self) -> bool:
        return self.latest_correct < self.peak_correct


def latest_fixed_exam_trajectory(
    history: tuple[tuple[ExamObservation, CapabilityObservation], ...],
) -> CohortTrajectory | None:
    """Observe the latest *consecutive* comparable examinations of one cohort.

    A new grade attempt receives a new cohort and starts its own measurement
    series. Different sampled questions cannot establish paired improvement.
    """
    if not history:
        return None
    current = history[-1][0]
    suffix = []
    for obs, cap in reversed(history):
        if obs.cohort_sha256 != current.cohort_sha256:
            break
        suffix.append((obs.optimizer_step, cap.correct, cap.total))
    if len(suffix) < MIN_RETENTION_OBSERVATIONS:
        return None
    points = tuple(reversed(suffix))
    if len({total for _, _, total in points}) != 1:
        raise ValueError("DIAGNOSTIC_FIXED_TEST_ITEM_COUNT_DRIFT")
    return CohortTrajectory(current.cohort_sha256, points)
