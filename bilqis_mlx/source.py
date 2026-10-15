"""Immutable pointers to the prior complete native FP32 checkpoint.

Nothing here loads, copies or mutates the historical checkpoint.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceCheckpoint:
    basename: str
    sha256: str
    old_rubric_correct: int
    old_rubric_total: int
    optimizer_step: int


AUDITED_PARENT = SourceCheckpoint(
    basename="student-116760-7e9af4651f28.pt",
    sha256="646d8590cf8fddb7b3c412ecead4ac185a0578f93baadf24e05f92dd15068a78",
    old_rubric_correct=1052,
    old_rubric_total=1150,
    optimizer_step=116760,
)
