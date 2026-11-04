"""Occurrence-aware frame-schema errors with source-owned authority."""
from __future__ import annotations

from ...errors import ErrorBus, SEMANTIC_FRAME
from .schema import SourceSpan


def _binding_fail(reason: str, source_span: SourceSpan, role_id: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason,
        span_start=source_span.start,
        span_end=source_span.end,
        role_id=role_id,
    )
