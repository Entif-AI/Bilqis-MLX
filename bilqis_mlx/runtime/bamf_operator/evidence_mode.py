"""Session-local evidence policy for the human BAMF trainer.

Learning-first mode is the ordinary development posture while throughput is being
re-established. Strict evidence remains available as an explicit opt-in and keeps
the heavier rehearsal/championship evidence work on the hot path.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar


_STRICT_EVIDENCE = ContextVar("bilqis_bamf_strict_evidence", default=True)


def strict_evidence_enabled() -> bool:
    return bool(_STRICT_EVIDENCE.get())


@contextmanager
def evidence_mode(*, strict: bool):
    token = _STRICT_EVIDENCE.set(bool(strict))
    try:
        yield
    finally:
        _STRICT_EVIDENCE.reset(token)


__all__ = ("evidence_mode", "strict_evidence_enabled")
