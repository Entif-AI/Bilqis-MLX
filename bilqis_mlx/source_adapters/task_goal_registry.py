"""Separately versioned C04 lowerers over immutable Factory source providers."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from .numeric_task_goal import lower_numeric_task_goal


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class RegisteredTaskGoalLowerer:
    provider_id: str
    provider_implementation_sha256: str
    lowerer_id: str
    implementation_sha256: str
    lower: object

    def __post_init__(self):
        if (not all(isinstance(value, str) and value for value in (
                self.provider_id, self.provider_implementation_sha256,
                self.lowerer_id, self.implementation_sha256))
                or len(self.provider_implementation_sha256) != 64
                or len(self.implementation_sha256) != 64
                or not callable(self.lower)):
            raise ValueError("BAMF_C04_TASK_LOWERER_INVALID")


def live_task_goal_lowerers():
    """Repository-owned interpretation adapters, separate from source-provider identity."""
    from bilqis_mlx.live_grade_c import provider_implementation_digest

    path = Path(__file__).resolve().parents[2] / "source_adapters/numeric_task_goal.py"
    numeric = RegisteredTaskGoalLowerer(
        "bilqis_mlx.numeric_curriculum.draw_numeric",
        provider_implementation_digest(),
        "bilqis.c04.numeric-task-goal/v1",
        _digest(path), lower_numeric_task_goal,
    )
    return (numeric,)


def require_task_goal_lowerer(provider_id: str, provider_sha256: str):
    matches = tuple(item for item in live_task_goal_lowerers()
                    if item.provider_id == provider_id
                    and item.provider_implementation_sha256 == provider_sha256)
    if len(matches) != 1:
        raise ValueError("BAMF_C04_SOURCE_TASK_LOWERER_REQUIRED")
    matches[0].__post_init__()
    return matches[0]


__all__ = (
    "RegisteredTaskGoalLowerer", "live_task_goal_lowerers",
    "require_task_goal_lowerer",
)
