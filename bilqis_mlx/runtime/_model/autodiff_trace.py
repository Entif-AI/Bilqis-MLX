"""Process-local policy for deferring host-visible tensor validation in MLX traces."""
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar


_DEFER_HOST_VALIDATION = ContextVar("bamf_defer_host_tensor_validation", default=False)


def host_tensor_validation_enabled() -> bool:
    """Return whether validation may synchronize MLX tensors to Python now."""
    return not _DEFER_HOST_VALIDATION.get()


def mlx_autodiff_parameter_tree(parameters):
    """Expose immutable parameter mappings as an MLX-compatible shallow tree.

    ``AdamWStateTree`` freezes its parameter mapping with ``MappingProxyType``.
    MLX only recognizes concrete pytree containers at the transform boundary,
    so preserve the authoritative mapping object outside autodiff while giving
    the transform a plain dict containing the exact same tensor objects.
    """
    if type(parameters) is dict or not isinstance(parameters, Mapping):
        return parameters
    return dict(parameters)


@contextmanager
def defer_host_tensor_validation():
    """Keep structural checks, but move tensor-value validation past autodiff."""
    token = _DEFER_HOST_VALIDATION.set(True)
    try:
        yield
    finally:
        _DEFER_HOST_VALIDATION.reset(token)


__all__ = (
    "defer_host_tensor_validation",
    "host_tensor_validation_enabled",
    "mlx_autodiff_parameter_tree",
)
