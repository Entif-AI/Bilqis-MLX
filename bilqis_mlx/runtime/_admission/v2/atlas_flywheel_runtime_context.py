"""Cold B13 runtime inputs for C07 v2 admission publication."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.atlas_lease_contracts import _invalid


@dataclass(frozen=True)
class AcceptedAtlasAdmissionRuntime:
    """Neural-inert accepted-custody inputs; never a live learner lane."""

    run_dir: Path
    checkpoint: Checkpoint
    graph: dict
    reserve_gib: float

    def __post_init__(self) -> None:
        if (not isinstance(self.run_dir, Path)
                or not isinstance(self.checkpoint, Checkpoint)
                or not isinstance(self.graph, dict)
                or not isinstance(self.reserve_gib, (int, float))
                or self.reserve_gib < 0):
            _invalid("BAMF_ATLAS_ACCEPTED_RUNTIME_INVALID")


def is_atlas_admission_runtime(value) -> bool:
    from bilqis_mlx.runtime.jit_adoption import _PreparedSuccessorRuntime
    return isinstance(value, (_PreparedSuccessorRuntime, AcceptedAtlasAdmissionRuntime))


def atlas_admission_checkpoint(runtime, current_release) -> Checkpoint:
    """Read the checkpoint without inventing a live SchoolState for cold custody."""
    if isinstance(runtime, AcceptedAtlasAdmissionRuntime):
        return runtime.checkpoint
    from bilqis_mlx.runtime.jit_adoption import _PreparedSuccessorRuntime
    if not isinstance(runtime, _PreparedSuccessorRuntime):
        _invalid("BAMF_ATLAS_ACCEPTED_RUNTIME_INVALID")
    from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
    from bilqis_mlx.runtime import state as runtime_state
    school = runtime_state._state_from_json(
        runtime.receipt["school"],
        schedule_program_from_executable_release(current_release),
    )
    return school.current_student
