"""Session-local evidence policy for the human BAMF trainer.

Learning-first mode is the ordinary development posture while throughput is being
re-established. Strict evidence remains available as an explicit opt-in and keeps
the heavier rehearsal/championship evidence work on the hot path.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar


_STRICT_MODE = ContextVar("bilqis_bamf_strict_mode", default=True)


def strict_mode_enabled() -> bool:
    return bool(_STRICT_MODE.get())


def strict_evidence_enabled() -> bool:
    """Compatibility alias for older callers that named only evidence ceremony."""
    return strict_mode_enabled()


@contextmanager
def evidence_mode(*, strict: bool):
    token = _STRICT_MODE.set(bool(strict))
    try:
        yield
    finally:
        _STRICT_MODE.reset(token)


__all__ = ("evidence_mode", "strict_mode_enabled", "strict_evidence_enabled")
