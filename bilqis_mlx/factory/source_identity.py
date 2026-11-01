"""Resolve the live source owner at the Factory integration boundary."""
from __future__ import annotations
from .adapters import RegisteredSourceAdapter


def canonical_source_adapter(adapter: RegisteredSourceAdapter) -> RegisteredSourceAdapter:
    """Return the current source owner, never a caller-rebound registry record."""
    from ..source_adapters.school import live_source_registry
    return live_source_registry().require(
        adapter.descriptor.generator_id, adapter.descriptor.accepted_oracle_ids[0])
