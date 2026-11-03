"""Stats for causal source-prefix compilation."""
from __future__ import annotations
from dataclasses import dataclass
from .contracts import _invalid


@dataclass(frozen=True)
class CompileStats:
    actual_atoms: int
    actual_frames: int
    neural_positions: int
    disposition_shares: tuple[tuple[str, int, int], ...]
    sidecar_bytes: int

    def __post_init__(self) -> None:
        if (any(type(value) is not int or value < 0
                for value in (
                    self.actual_atoms, self.actual_frames,
                    self.neural_positions, self.sidecar_bytes))
                or self.actual_atoms + self.actual_frames
                != self.neural_positions
                or not isinstance(self.disposition_shares, tuple)
                or tuple(item[0] for item in self.disposition_shares)
                != ("COMPACT", "EXTENDED", "ATOMIC")
                or any(type(count) is not int or count < 0
                       or type(total) is not int
                       or total != self.actual_frames
                       for _, count, total in self.disposition_shares)
                or sum(count for _, count, _ in self.disposition_shares)
                != self.actual_frames):
            _invalid("BAMF_PREFIX_STATS_INVALID")
