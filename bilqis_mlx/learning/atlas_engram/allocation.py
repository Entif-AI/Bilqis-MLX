"""Allocation for the existing atlas engram contract."""
from __future__ import annotations
from .contracts import INITIAL_MOTIF_CAPACITY, MOTIF_VECTOR_WIDTH

from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents
from bilqis_mlx.runtime.model_topology_v2 import Initializer
from bilqis_mlx.runtime.model_topology_v2 import MOTIF_PAGE_SHAPE
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.runtime.model_topology_v2 import expected_bamf_shapes
from bilqis_mlx.runtime.model_topology_v2 import initialize_bamf_row
from collections import Counter
from .contracts import (
    MotifFrameInput, MotifKey, MotifSlot, OBSERVED_USE_ARITY, VIEW_SCHEMA,
    _SHA, _invalid,
)
from .manifest import (
    CandidateMotifView, MotifAllocationPlan, MotifBudget, MotifManifest, MotifMatch,
    _plan_page_growth,
)
from .keys import (
    motif_keys,
)


def prepare_motifs(
    frames: tuple[MotifFrameInput, ...],
    parent_manifest: MotifManifest,
    budget: MotifBudget,
    *,
    prior_observed_uses: tuple[tuple[str, int], ...] = (),
    prior_pending: tuple[MotifKey, ...] = (),
) -> CandidateMotifView:
    """Plan structural-before-instance slots without mutating accepted state."""
    if (not isinstance(frames, tuple)
            or any(not isinstance(item, MotifFrameInput) for item in frames)
            or type(parent_manifest) is not MotifManifest
            or type(budget) is not MotifBudget
            or not isinstance(prior_observed_uses, tuple)
            or any(not isinstance(item, tuple) or len(item) != OBSERVED_USE_ARITY
                   or not isinstance(item[0], str) or not _SHA.fullmatch(item[0])
                   or type(item[1]) is not int or item[1] < 1
                   for item in prior_observed_uses)
            or prior_observed_uses != tuple(sorted(set(prior_observed_uses)))
            or len({item[0] for item in prior_observed_uses})
            != len(prior_observed_uses)
            or not isinstance(prior_pending, tuple)
            or any(type(key) is not MotifKey
                   or key.semantic_release != parent_manifest.semantic_release
                   for key in prior_pending)
            or len({key.digest for key in prior_pending}) != len(prior_pending)):
        _invalid("BAMF_MOTIF_PREPARATION_INVALID")
    pairs = tuple(motif_keys(item, parent_manifest.semantic_release)
                  for item in frames)
    observed = Counter(key for pair in pairs for key in pair)
    cumulative_uses = Counter(dict(prior_observed_uses))
    cumulative_uses.update({key.digest: count for key, count in observed.items()})
    existing = {slot.key: slot.slot_id for slot in parent_manifest.slots}
    missing_structural = {
        structural for exact, structural in pairs
        if exact not in existing and structural not in existing}
    missing_exact = {exact for exact, _ in pairs if exact not in existing}
    missing_structural.update(
        key for key in prior_pending
        if key.kind == "STRUCTURAL" and key not in existing)
    missing_exact.update(
        key for key in prior_pending
        if key.kind == "EXACT" and key not in existing)
    sort_key = lambda key: (-cumulative_uses[key.digest], key.digest)
    ordered = (
        *sorted(missing_structural, key=sort_key),
        *sorted(missing_exact, key=sort_key),
    )
    requested = min(budget.new_slot_limit, len(ordered))
    growth = _plan_page_growth(
        parent_manifest.capacity, len(parent_manifest.slots),
        requested, budget.page_growth_bytes)
    available = min(requested, growth.candidate_capacity - len(parent_manifest.slots))
    allocated = tuple(
        MotifSlot(len(parent_manifest.slots) + index, key)
        for index, key in enumerate(ordered[:available]))
    pending = tuple(ordered[available:])
    candidate = dict(existing)
    candidate.update((item.key, item.slot_id) for item in allocated)
    matches = []
    for source, (exact, structural) in zip(frames, pairs):
        if exact in candidate:
            kind, slot = "EXACT", candidate[exact]
        elif structural in candidate:
            kind, slot = "STRUCTURAL", candidate[structural]
        else:
            kind, slot = "FACTORIZED_FALLBACK", None
        matches.append(MotifMatch(
            source.frame.occurrence_id, exact.digest, structural.digest,
            kind, slot))
    return CandidateMotifView(
        tuple(matches),
        MotifAllocationPlan(
            parent_manifest.digest, allocated, pending,
            tuple(sorted(cumulative_uses.items()))),
        growth,
    )


def candidate_motif_manifest(
    parent: MotifManifest, candidate: CandidateMotifView,
) -> MotifManifest:
    """Construct a frozen candidate manifest, never publish the parent."""
    if (type(parent) is not MotifManifest
            or type(candidate) is not CandidateMotifView
            or candidate.schema_version != VIEW_SCHEMA
            or candidate.plan.parent_manifest_digest != parent.digest
            or candidate.page_growth.parent_capacity != parent.capacity
            or (candidate.page_growth.added_pages > 0
                and len(parent.slots) + len(candidate.plan.allocated)
                <= parent.capacity)
            or tuple(slot.slot_id for slot in candidate.plan.allocated) != tuple(
                range(len(parent.slots),
                      len(parent.slots) + len(candidate.plan.allocated)))):
        _invalid("BAMF_MOTIF_CANDIDATE_PARENT_MISMATCH")
    return MotifManifest(
        parent.semantic_release,
        parent.slots + candidate.plan.allocated,
        candidate.page_growth.candidate_capacity,
    )


def initialize_planned_motif_slot(
    candidate: CandidateMotifView, slot_id: int, *,
    run_seed: int, topology: ModelTopologySpecV2, extents: GenerationExtents,
):
    """Use B01's seeded row initializer, not a second motif parameter registry."""
    if (type(candidate) is not CandidateMotifView
            or type(slot_id) is not int
            or type(topology) is not ModelTopologySpecV2
            or type(extents) is not GenerationExtents
            or extents.motif_page_count != (
                candidate.page_growth.candidate_capacity // INITIAL_MOTIF_CAPACITY)):
        _invalid("BAMF_MOTIF_INITIALIZATION_AUTHORITY_INVALID")
    slot = next(
        (item for item in candidate.plan.allocated if item.slot_id == slot_id), None)
    if slot is None:
        _invalid("BAMF_MOTIF_INITIALIZATION_SLOT_NOT_PLANNED")
    page = slot_id // INITIAL_MOTIF_CAPACITY
    name = f"motif.page.{page}"
    parameter = next(
        (item for item in expected_bamf_shapes(topology, extents)
         if item.name == name), None)
    if (parameter is None or parameter.initializer is not Initializer.MOTIF_PAGE
            or parameter.shape != MOTIF_PAGE_SHAPE):
        _invalid("BAMF_MOTIF_INITIALIZATION_AUTHORITY_INVALID")
    return initialize_bamf_row(
        parameter, run_seed=run_seed, row_id=slot.key.digest)
