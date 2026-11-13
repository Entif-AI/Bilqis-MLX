"""Accepted-run bindings consumed by the C07 Atlas admission policy."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .atlas_admission import _invalid


@dataclass(frozen=True)
class PostAdmissionTotals:
    semantic_banks: int
    motif_pages: int
    total_semantic_identities: int
    memory_bytes: int
    disk_bytes: int

    def __post_init__(self):
        if any(type(value) is not int or value < 1 for value in asdict(self).values()):
            _invalid('BAMF_ATLAS_POST_ADMISSION_TOTALS_INVALID')


def require_native_semantic_binding(current, proposal):
    from .bamf_bundle import require_issued_a02_staged_vocabulary_extension

    native = require_issued_a02_staged_vocabulary_extension(current.native_staged)
    events = tuple(
        event for event in native.candidate.outbox
        if isinstance(event, dict) and event.get('event') == 'BAMF_A02_VOCABULARY_STAGED')
    if len(events) != 1:
        _invalid('BAMF_ATLAS_A02_SEMANTIC_BINDING_INVALID')
    plan = events[0].get('plan')
    allocations = plan.get('allocations') if isinstance(plan, dict) else None
    if not isinstance(allocations, tuple):
        _invalid('BAMF_ATLAS_A02_SEMANTIC_BINDING_INVALID')
    actual = tuple(
        item.get('semantic_id') for item in allocations if isinstance(item, dict))
    current_catalog = tuple(current.current_release.semantic_catalog)
    successor_catalog = tuple(proposal.staged.successor.semantic_catalog)
    if successor_catalog[:len(current_catalog)] != current_catalog:
        _invalid('BAMF_ATLAS_FACTORY_SEMANTIC_PREFIX_DRIFT')
    expected = successor_catalog[len(current_catalog):]
    if actual != expected or len(actual) != proposal.new_semantic_identities:
        _invalid('BAMF_ATLAS_A02_FACTORY_SEMANTIC_MISMATCH')
    return native


def native_post_admission_totals(native):
    from .bamf_bundle.records import canonical, sha
    from .model_topology_v2 import bamf_parameter_census
    from ..semantics.atlas.vocabulary_resources import FP32_WEIGHT_AND_ADAMW_BYTES

    events = tuple(
        event for event in native.candidate.outbox
        if isinstance(event, dict) and event.get('event') == 'BAMF_A02_VOCABULARY_STAGED')
    if len(events) != 1:
        _invalid('BAMF_ATLAS_A02_RESOURCE_BINDING_INVALID')
    plan = events[0].get('plan')
    resource = events[0].get('resource_estimate')
    active_indices = plan.get('active_indices') if isinstance(plan, dict) else None
    if (not isinstance(active_indices, tuple) or not isinstance(resource, dict)
            or sha(canonical(plan)) != native.receipt.plan_sha256
            or sha(canonical(resource)) != native.receipt.resource_estimate_sha256):
        _invalid('BAMF_ATLAS_A02_RESOURCE_BINDING_INVALID')
    candidate = native.candidate
    checkpoint_bytes = (
        bamf_parameter_census(candidate.topology, candidate.extents).total
        * FP32_WEIGHT_AND_ADAMW_BYTES)
    if (resource.get('next_bank_count') != candidate.extents.semantic_bank_count
            or resource.get('complete_checkpoint_bytes_lower_bound') != checkpoint_bytes):
        _invalid('BAMF_ATLAS_A02_RESOURCE_BINDING_INVALID')
    return PostAdmissionTotals(
        candidate.extents.semantic_bank_count,
        candidate.extents.motif_page_count,
        len(active_indices), checkpoint_bytes, checkpoint_bytes)


def require_accepted_delta_registry(current):
    if current.runtime is None:
        return
    from .bamf_bundle.admission import bind_accepted_execution_cache

    try:
        cache = bind_accepted_execution_cache(current.runtime.run_dir)
    except (AttributeError, TypeError, ValueError):
        _invalid('BAMF_ATLAS_ACCEPTED_DELTA_REGISTRY_REQUIRED')
    if (cache.source_authority_registry_sha256 is None
            or cache.source_authority_registry_sha256 != current.registry.digest):
        _invalid('BAMF_ATLAS_ACCEPTED_DELTA_REGISTRY_DRIFT')


def current_implementation_registries(current):
    if current.runtime is None:
        if current.source_registry is None or current.answer_registry is None:
            _invalid('BAMF_ATLAS_CURRENT_IMPLEMENTATION_REGISTRIES_REQUIRED')
        return current.source_registry, current.answer_registry
    from bilqis_mlx.factory.live_answers import live_answer_registry
    from bilqis_mlx.source_adapters.school import live_source_registry
    return live_source_registry(), live_answer_registry()
