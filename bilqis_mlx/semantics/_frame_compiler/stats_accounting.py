"""Compiled-prefix sidecar accounting."""
from __future__ import annotations
from .. import frame_compiler as _facade

from ..frame_codec import PackDisposition
from .positions import PositionKind
from .batch import CompiledFrameBatch
from .stats import CompileStats


def _compile_stats(compiled: CompiledFrameBatch) -> CompileStats:
    closures = tuple(
        position.packed for position in compiled.positions
        if position.kind is PositionKind.CLOSURE)
    count = len(closures)
    shares = tuple(
        (disposition.name,
         sum(packed.disposition is disposition for packed in closures),
         count)
        for disposition in (
            PackDisposition.COMPACT,
            PackDisposition.EXTENDED,
            PackDisposition.ATOMIC))
    return CompileStats(
        len(compiled.positions) - count, count,
        len(compiled.positions), shares,
        sum(len(_facade._canonical_bytes(_facade.asdict(packed.sidecar)))
            for packed in closures))
