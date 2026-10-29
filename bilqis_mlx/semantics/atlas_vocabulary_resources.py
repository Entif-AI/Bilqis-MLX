"""A02.3 source-derived Registry mirror and conservative bank resource estimate.

These are navigable projections, not a second semantic registry or a disk grant.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

from ..errors import ErrorBus, SEMANTIC_FRAME
from ..runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, bamf_parameter_census,
)
from ..vocabulary_growth import digest
from .atlas_snapshot import load_pinned_atlas_snapshot
from .atlas_vocabulary import (
    STAGED_ONLY, VocabularyExtension, VocabularyPrior,
    plan_vocabulary_extension,
)

RESOURCE_SCHEMA = "bilqis.atlas-vocabulary-resource-estimate/v1"
REGISTRY_DELTA_SCHEMA = "bilqis.atlas-vocabulary-registry-mirror-delta/v1"
GIB = 1024 ** 3
DEFAULT_DISK_RESERVE_BYTES = 100 * GIB
DEFAULT_EXTRA_PLANNING_BYTES = 30 * GIB
FP32_WEIGHT_AND_ADAMW_BYTES = 12


def _invalid(reason: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<atlas-vocabulary-resources>",
        span_start=0, span_end=0,
    )


@dataclass(frozen=True)
class VocabularyResourceEstimate:
    previous_bank_count: int
    next_bank_count: int
    added_bank_bytes: int
    complete_checkpoint_bytes_lower_bound: int
    disk_reserve_bytes: int
    extra_planning_bytes: int
    required_available_bytes_lower_bound: int
    observed_available_bytes: int
    fits: bool
    schema_version: str = RESOURCE_SCHEMA


@dataclass(frozen=True)
class RegistryMirrorRow:
    semantic_id: str
    abi_index: int
    bank: int
    row: int
    source_status: str
    description: str
    source_record_digest: str


@dataclass(frozen=True)
class RegistryMirrorDelta:
    semantic_release: str
    source_bundle_id: str
    predecessor_generation_id: str
    allocation_source_digest: str
    active_indices: tuple[int, ...]
    rows: tuple[RegistryMirrorRow, ...]
    status: str = STAGED_ONLY
    schema_version: str = REGISTRY_DELTA_SCHEMA

    @property
    def digest(self) -> str:
        return digest(asdict(self))


def estimate_vocabulary_resources(
    prior: VocabularyPrior,
    plan: VocabularyExtension,
    *,
    observed_available_bytes: int,
    reserve_bytes: int = DEFAULT_DISK_RESERVE_BYTES,
    extra_planning_bytes: int = DEFAULT_EXTRA_PLANNING_BYTES,
) -> VocabularyResourceEstimate:
    """Conservative lower bound for a complete staged FP32+AdamW bundle."""
    if (type(prior) is not VocabularyPrior
            or type(plan) is not VocabularyExtension
            or type(observed_available_bytes) is not int
            or type(reserve_bytes) is not int
            or type(extra_planning_bytes) is not int
            or min(observed_available_bytes, reserve_bytes, extra_planning_bytes) < 0
            or reserve_bytes < DEFAULT_DISK_RESERVE_BYTES
            or plan.parent_extents_digest != prior.extents.digest
            or plan.shape_policy_digest != ModelTopologySpecV2().shape_policy_digest
            or plan.bank_count < prior.extents.semantic_bank_count):
        _invalid("BAMF_VOCABULARY_RESOURCE_INPUT_INVALID")
    extents = GenerationExtents(
        plan.bank_count, prior.extents.motif_page_count,
        plan.active_semantic_digest,
        prior.extents.motif_key_map_digest,
        prior.extents.factor_map_digest,
    )
    census = bamf_parameter_census(ModelTopologySpecV2(), extents)
    checkpoint_bytes = census.total * FP32_WEIGHT_AND_ADAMW_BYTES
    added_bank_bytes = (
        (plan.bank_count - prior.extents.semantic_bank_count)
        * ModelTopologySpecV2.semantic_bank_rows
        * ModelTopologySpecV2.width
        * FP32_WEIGHT_AND_ADAMW_BYTES
    )
    required = reserve_bytes + extra_planning_bytes + checkpoint_bytes
    return VocabularyResourceEstimate(
        previous_bank_count=prior.extents.semantic_bank_count,
        next_bank_count=plan.bank_count,
        added_bank_bytes=added_bank_bytes,
        complete_checkpoint_bytes_lower_bound=checkpoint_bytes,
        disk_reserve_bytes=reserve_bytes,
        extra_planning_bytes=extra_planning_bytes,
        required_available_bytes_lower_bound=required,
        observed_available_bytes=observed_available_bytes,
        fits=observed_available_bytes >= required,
    )


def build_registry_mirror_delta(
    prior: VocabularyPrior,
    plan: VocabularyExtension,
) -> RegistryMirrorDelta:
    """Derive descriptions from A01, never from caller-supplied glosses."""
    if type(prior) is not VocabularyPrior or type(plan) is not VocabularyExtension:
        _invalid("BAMF_VOCABULARY_MIRROR_INPUT_INVALID")
    replay = plan_vocabulary_extension(
        prior, tuple(item.semantic_id for item in plan.allocations),
        ModelTopologySpecV2())
    if replay != plan:
        _invalid("BAMF_VOCABULARY_MIRROR_SOURCE_REPLAY_MISMATCH")
    snapshot = load_pinned_atlas_snapshot(prior.source_selection)
    concepts = {
        item.concept.semantic_id: item.concept for item in snapshot.concepts}
    formal = {
        name: binding for binding in snapshot.formal_domain_bindings
        for name in binding.semantic_ids
    }
    rows = []
    for allocation in plan.allocations:
        concept = concepts.get(allocation.semantic_id)
        if concept is not None:
            preferred = sorted((
                label for label in concept.labels if label.role == "pref"
            ), key=lambda label: ((label.language or "").encode("utf-8"),
                                  label.value.encode("utf-8")))
            description = preferred[0].value if preferred else ""
            source_digest = digest(asdict(concept))
        else:
            binding = formal.get(allocation.semantic_id)
            if binding is None:
                _invalid("BAMF_VOCABULARY_MIRROR_SOURCE_MISSING")
            description = ""
            source_digest = digest(asdict(binding))
        rows.append(RegistryMirrorRow(
            allocation.semantic_id, allocation.abi_index,
            allocation.bank, allocation.row, allocation.source_status,
            description, source_digest))
    return RegistryMirrorDelta(
        semantic_release=plan.semantic_release,
        source_bundle_id=plan.source_bundle_id,
        predecessor_generation_id=plan.parent_generation_id,
        allocation_source_digest=plan.source_allocation_digest,
        active_indices=plan.active_indices,
        rows=tuple(rows),
    )
