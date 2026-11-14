"""Apply GUI05 qualification's explicit per-process MLX resource budget."""
import os

if os.environ.get("BILQIS_GUI05_BOUNDED_TEST") == "1":
    import mlx.core as mx

    mx.set_memory_limit(1024**3)
    mx.set_cache_limit(0)
