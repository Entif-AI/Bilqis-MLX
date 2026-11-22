"""Bounded process-live reuse for exact selected-source preparation products."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from bilqis_mlx.runtime.source_execution import source_content_digest


SOURCE_MATERIALIZATION_CACHE_CAPACITY = 4


def _invalid_cache():
    from bilqis_mlx.runtime.source_execution import _invalid_source_batch
    _invalid_source_batch("BAMF_PRIORITY_SOURCE_MATERIALIZATION_CACHE_INVALID")


def _cache_drift():
    from bilqis_mlx.runtime.source_execution import _invalid_source_batch
    _invalid_source_batch("BAMF_PRIORITY_SOURCE_MATERIALIZATION_CACHE_DRIFT")


def priority_source_materialization_identity(offer) -> tuple:
    """Bind reuse to accepted state plus exact immutable source lesson identity."""
    generation = offer._planning_generation
    authority = offer.source_authority
    return (
        "bilqis.bamf.priority-source-materialization-cache/v1",
        generation.accepted_manifest_sha256,
        generation.generation_binding,
        generation.acceptance_sha256,
        generation.acceptance_file_identity_sha256,
        generation.run_identity_sha256,
        generation.release_sha256,
        generation.correction_frontier_sha256,
        generation.feature_receipt_sha256,
        generation.parent_candidate_identity_sha256,
        offer.release_sha256,
        offer.capability_id,
        offer.source_seed,
        offer.source_each,
        offer.source_family_id,
        offer.source_binding_digest,
        offer._rows_sha256,
        authority.provider_id,
        authority.provider_implementation_sha256,
        authority.content_sha256,
        authority.episode_ids,
    )


@dataclass(frozen=True)
class PreparedPrioritySourceArtifacts:
    """Heavy immutable preparation products without visit-local correction owners."""

    identity: tuple
    manifest: object
    source_rows: tuple
    model_sources: tuple
    b11_configs: tuple
    prefixes: tuple

    def require_exact(self, offer):
        if (self.identity != priority_source_materialization_identity(offer)
                or any(type(value) is not tuple for value in (
                    self.source_rows, self.model_sources, self.b11_configs,
                    self.prefixes))
                or not self.source_rows
                or any(len(value) != len(self.source_rows) for value in (
                    self.model_sources, self.b11_configs, self.prefixes))
                or source_content_digest(tuple(item.row for item in self.source_rows))
                != offer.source_authority.content_sha256):
            _cache_drift()
        return self


def rebind_priority_source_rows(offer, source_context, authenticated, rows, artifacts):
    """Rebind cached source templates to the current process-live source owner."""
    from bilqis_mlx.factory.generation import runtime_adapter_for_release
    from bilqis_mlx.learning.source_atoms import SourceAtomRow
    from bilqis_mlx.runtime.b11_source_execution_authority import (
        _issue_prepared_b11_source_proof,
    )
    from bilqis_mlx.runtime.b11_source_owner_authority import require_row_owner
    from bilqis_mlx.source_adapters.atoms.authority import canonical_graph_for

    if len(rows) != len(artifacts.source_rows):
        _cache_drift()
    rebound = []
    for current_row, cached in zip(rows, artifacts.source_rows):
        if current_row != cached.row:
            _cache_drift()
        execution = source_context.release.execution_plan.capability_map[
            current_row["capability"]]
        current_owner = runtime_adapter_for_release(
            source_context.source_root, source_context.graph, source_context.release,
            source_context.source_registry, execution)
        current_graph = canonical_graph_for(
            current_row.get("generator"), source_context.source_root, row=current_row)
        if current_graph != cached.source_graph:
            _cache_drift()
        profile = (dict(execution.provider_parameters)
                   if execution.provider_parameters else None)
        source = SourceAtomRow(
            authenticated.selection, current_row, current_graph,
            Path(source_context.source_root), cached.source_seed, cached.source_each,
            source_context.release.curriculum, profile)
        resolved = require_row_owner(
            cached.source_adapter, source_context.source_registry, source, drift=True)
        if resolved != current_owner:
            _cache_drift()
        proof = _issue_prepared_b11_source_proof(
            source_context, rows, offer.source_authority, current_row,
            cached.source_witness, cached.formal_projection, cached.formal_frontier)
        rebound.append(replace(
            cached, row=current_row, source_adapter=current_owner,
            source_graph=current_graph, profile=profile, b11_proof=proof))
    selected = source_context.release.execution_plan.capability_map[offer.capability_id]
    adapter = runtime_adapter_for_release(
        source_context.source_root, source_context.graph, source_context.release,
        source_context.source_registry, selected)
    profile = (dict(selected.provider_parameters)
               if selected.provider_parameters else None)
    return adapter, profile, tuple(rebound)


@dataclass
class PrioritySourceMaterializationCache:
    """Small LRU-like cache; only completed exact preparations are retained."""

    capacity: int = SOURCE_MATERIALIZATION_CACHE_CAPACITY
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    _items: dict[tuple, PreparedPrioritySourceArtifacts] = field(
        default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        if type(self.capacity) is not int or self.capacity < 1:
            _invalid_cache()

    def get(self, identity: tuple):
        item = self._items.pop(identity, None)
        if item is None:
            self.misses += 1
            return None
        self._items[identity] = item
        self.hits += 1
        return item

    def put(self, item: PreparedPrioritySourceArtifacts) -> None:
        if type(item) is not PreparedPrioritySourceArtifacts:
            _invalid_cache()
        self._items.pop(item.identity, None)
        while len(self._items) >= self.capacity:
            self._items.pop(next(iter(self._items)))
            self.evictions += 1
        self._items[item.identity] = item

    def metrics(self) -> dict[str, int]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "entries": len(self._items),
        }


__all__ = (
    "PreparedPrioritySourceArtifacts", "PrioritySourceMaterializationCache",
    "SOURCE_MATERIALIZATION_CACHE_CAPACITY", "priority_source_materialization_identity",
    "rebind_priority_source_rows",
)
