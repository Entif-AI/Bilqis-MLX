"""Explicit MLX memory policy for long-running Bilqis training sessions."""
from __future__ import annotations

from contextlib import contextmanager

from bilqis_mlx.runtime.memory_safety import TrainerMemoryPolicy


POLICY = "bilqis.mlx.training-memory/governed-v2"


@contextmanager
def training_memory_policy(mx, *, ceiling_bytes=None):
    """Apply secondary MLX limits while the external governor owns hard containment.

    Bilqis deliberately varies lesson shapes and answer heads across optimizer
    steps.  MLX's default free-buffer pool retains released Metal allocations
    for reuse, which lets those heterogeneous working sets accumulate toward
    the framework's system-sized cache ceiling. The MLX memory limit remains a
    graph-evaluation guideline and the wired limit applies only to wired MLX
    memory. Deh Guhbohnayhituh remains the authoritative process-footprint
    ceiling outside this process.
    """
    configured = TrainerMemoryPolicy.from_environment()
    selected_ceiling = configured.ceiling_bytes if ceiling_bytes is None else int(ceiling_bytes)
    previous_memory_limit = None
    previous_wired_limit = None
    set_memory_limit = getattr(mx, "set_memory_limit", None)
    set_wired_limit = getattr(mx, "set_wired_limit", None)
    if callable(set_memory_limit):
        previous_memory_limit = set_memory_limit(selected_ceiling)
    if callable(set_wired_limit):
        previous_wired_limit = set_wired_limit(selected_ceiling)
    previous_cache_limit = mx.set_cache_limit(0)
    mx.clear_cache()
    try:
        yield {
            "policy": POLICY,
            "memory_ceiling_bytes": selected_ceiling,
            "cache_limit_bytes": 0,
            "previous_cache_limit_bytes": previous_cache_limit,
            "previous_memory_limit_bytes": previous_memory_limit,
            "previous_wired_limit_bytes": previous_wired_limit,
        }
    finally:
        mx.clear_cache()
        mx.set_cache_limit(previous_cache_limit)
        if callable(set_wired_limit) and previous_wired_limit is not None:
            set_wired_limit(previous_wired_limit)
        if callable(set_memory_limit) and previous_memory_limit is not None:
            set_memory_limit(previous_memory_limit)
