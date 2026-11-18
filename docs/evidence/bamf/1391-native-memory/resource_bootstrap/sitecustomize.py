"""Apply a bounded MLX policy to every Python child of this test-only run."""
import atexit
import mlx.core as mx
from bilqis_mlx.runtime.mlx_memory import training_memory_policy

mx.set_memory_limit(8 * 1024 ** 3)
_policy = training_memory_policy(mx)
_policy.__enter__()
atexit.register(_policy.__exit__, None, None, None)
