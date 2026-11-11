"""Read-only A02 admission facts for signer-free C07 v2 verification."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.semantics.atlas_projection import (
    _canonical_bytes as _atlas_bytes,
    _digest as _atlas_sha256,
)

from .._vocabulary_admission_records import (
    A02StagedVocabularyExtension,
    A02VocabularyStagingReceipt,
    STAGED_EVENT,
    require_issued_a02_staged_vocabulary_extension,
)
from ..records import canonical, invalid, sha
from ..vocabulary_registry_export import _mirror_from_record, _resource_requirement


@dataclass(frozen=True)
class A02StagedAdmissionFactsV2:
    """Owner-derived v2 facts from one live, issued A02 staging handoff."""

    allocation_semantic_ids: tuple[str, ...]
    total_atlas_semantic_identities: int
    semantic_banks: int
    motif_pages: int
    checkpoint_bytes_lower_bound: int
    required_available_bytes_lower_bound: int


def accepted_active_semantic_ids(parent, snapshot) -> tuple[str, ...]:
    """Recover accepted active semantic IDs without invoking A02 mutation."""
    indices = tuple(sorted(
        row.bank_index * ModelTopologySpecV2.semantic_bank_rows + row.row_index
        for row in parent.retained_state.policy.row_ages))
    if (indices != tuple(sorted(set(indices)))
            or any(index >= parent.extents.semantic_bank_count
                   * ModelTopologySpecV2.semantic_bank_rows for index in indices)
            or _atlas_sha256(_atlas_bytes(list(indices)))
            != parent.extents.active_semantic_digest
            or parent.semantic_abi.get("active_set_sha256")
            != parent.extents.active_semantic_digest):
        invalid("BAMF_A02_PARENT_ACTIVE_SET_DRIFT")
    by_index = {entry.index: entry.semantic_id for entry in snapshot.abi_entries}
    if len(by_index) != len(snapshot.abi_entries):
        invalid("BAMF_A02_PARENT_ACTIVE_SET_DRIFT")
    try:
        return tuple(by_index[index] for index in indices)
    except KeyError:
        invalid("BAMF_A02_PARENT_ACTIVE_SET_DRIFT")


def read_issued_a02_staged_admission_facts_v2(
        staged: A02StagedVocabularyExtension) -> A02StagedAdmissionFactsV2:
    """Revalidate A02 staging evidence without granting C07 admission authority."""
    staged = require_issued_a02_staged_vocabulary_extension(staged)
    candidate = staged.candidate
    receipt = staged.receipt
    events = tuple(
        event for event in candidate.outbox
        if isinstance(event, dict) and event.get("event") == STAGED_EVENT)
    if len(events) != 1:
        invalid("BAMF_A02_V2_STAGED_EVIDENCE_INVALID")
    event = events[0]
    try:
        replayed_receipt = A02VocabularyStagingReceipt.from_record(
            event.get("staging_receipt"))
    except (TypeError, ValueError, KeyError):
        invalid("BAMF_A02_V2_STAGED_EVIDENCE_INVALID")
    plan = event.get("plan")
    if not isinstance(plan, Mapping):
        invalid("BAMF_A02_V2_STAGED_EVIDENCE_INVALID")
    try:
        mirror = _mirror_from_record(event.get("registry_mirror"))
    except (TypeError, ValueError, KeyError):
        invalid("BAMF_A02_V2_STAGED_EVIDENCE_INVALID")
    resource = _resource_requirement(
        event.get("resource_estimate"),
        expected_digest=receipt.resource_estimate_sha256,
        expected_bank_count=receipt.semantic_bank_count)
    allocations = tuple(plan.get("allocations", ()))
    active_indices = tuple(plan.get("active_indices", ()))
    if (replayed_receipt != receipt
            or sha(canonical(dict(plan))) != receipt.plan_sha256
            or mirror.digest != receipt.registry_mirror_sha256
            or plan.get("parent_generation_id") != receipt.parent_manifest_sha256
            or plan.get("source_allocation_digest") != receipt.source_allocation_sha256
            or plan.get("semantic_release") != mirror.semantic_release
            or plan.get("source_bundle_id") != mirror.source_bundle_id
            or plan.get("parent_generation_id") != mirror.predecessor_generation_id
            or plan.get("source_allocation_digest") != mirror.allocation_source_digest
            or active_indices != mirror.active_indices
            or plan.get("active_semantic_digest") != receipt.active_set_sha256
            or plan.get("bank_count") != receipt.semantic_bank_count
            or candidate.extents.digest != receipt.prepared_extents_sha256
            or candidate.extents.active_semantic_digest != receipt.active_set_sha256
            or candidate.extents.factor_map_digest != receipt.feature_sha256
            or candidate.extents.semantic_bank_count != receipt.semantic_bank_count
            or not allocations
            or len(allocations) != len(mirror.rows)
            or any(not isinstance(allocation, Mapping)
                   or not isinstance(allocation.get("semantic_id"), str)
                   or not allocation["semantic_id"]
                   or type(allocation.get("abi_index")) is not int
                   for allocation in allocations)
            or tuple(allocation["abi_index"] for allocation in allocations)
               != tuple(sorted(allocation["abi_index"] for allocation in allocations))
            or len({allocation["abi_index"] for allocation in allocations})
               != len(allocations)
            or any(
                (row.semantic_id, row.abi_index, row.bank, row.row, row.source_status)
                != (allocation.get("semantic_id"), allocation.get("abi_index"),
                    allocation.get("bank"), allocation.get("row"),
                    allocation.get("source_status"))
                for row, allocation in zip(mirror.rows, allocations))):
        invalid("BAMF_A02_V2_STAGED_EVIDENCE_INVALID")
    return A02StagedAdmissionFactsV2(
        allocation_semantic_ids=tuple(
            allocation["semantic_id"] for allocation in allocations),
        total_atlas_semantic_identities=len(active_indices),
        semantic_banks=candidate.extents.semantic_bank_count,
        motif_pages=candidate.extents.motif_page_count,
        checkpoint_bytes_lower_bound=resource[
            "complete_checkpoint_bytes_lower_bound"],
        required_available_bytes_lower_bound=resource[
            "required_available_bytes_lower_bound"],
    )
