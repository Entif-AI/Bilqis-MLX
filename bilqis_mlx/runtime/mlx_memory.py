"""Explicit MLX memory policy for long-running Bilqis training sessions."""
from __future__ import annotations

from contextlib import contextmanager


POLICY = "bilqis.mlx.training-memory/no-free-buffer-cache-v1"


@contextmanager
def training_memory_policy(mx):
    """Disable MLX's free-buffer cache while the long-running trainer owns MLX.

    Bilqis deliberately varies lesson shapes and answer heads across optimizer
    steps.  MLX's default free-buffer pool retains released Metal allocations
    for reuse, which lets those heterogeneous working sets accumulate toward
    the framework's system-sized cache ceiling.  The causal model, optimizer
    state and live activations remain untouched; only already-freed buffers are
    returned instead of being retained by the allocator cache.
    """
    previous_cache_limit = mx.set_cache_limit(0)
    mx.clear_cache()
    try:
        yield {
            "policy": POLICY,
            "cache_limit_bytes": 0,
            "previous_cache_limit_bytes": previous_cache_limit,
        }
    finally:
        mx.clear_cache()
        mx.set_cache_limit(previous_cache_limit)
