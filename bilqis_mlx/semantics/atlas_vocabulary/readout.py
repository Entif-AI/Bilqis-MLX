"""Source-qualified active-row readout from a detached bank candidate."""
from __future__ import annotations
from ..atlas_projection import BANK_SIZE
from ...runtime.model_topology_v2 import ModelTopologySpecV2
from .models import CandidateState, STAGED_ONLY, _invalid
from .staging import _mask

def staged_tied_logits(
    candidate: CandidateState,
    hidden: object,
) -> tuple[tuple[int, ...], object]:
    """Only active ABI rows compete, in global index order without modulo alias."""
    import mlx.core as mx

    if (type(candidate) is not CandidateState
            or candidate.status != STAGED_ONLY
            or not isinstance(hidden, mx.array)
            or hidden.dtype != mx.float32
            or hidden.shape != (ModelTopologySpecV2.width,)
            or len(candidate.weights) != candidate.extents.semantic_bank_count
            or tuple(index for index, _ in candidate.output_domain)
            != candidate.active_indices
            or candidate.active_mask != _mask(
                candidate.active_indices,
                candidate.extents.semantic_bank_count * BANK_SIZE)):
        _invalid("BAMF_VOCABULARY_READOUT_INVALID")
    logits = []
    for bank, weights in enumerate(candidate.weights):
        rows = tuple(
            index % BANK_SIZE for index in candidate.active_indices
            if index // BANK_SIZE == bank)
        if rows:
            logits.append(mx.take(
                weights, mx.array(rows, dtype=mx.int32), axis=0) @ hidden)
    if not logits:
        _invalid("BAMF_VOCABULARY_READOUT_EMPTY")
    output = mx.concatenate(logits)
    mx.eval(output)
    return candidate.active_indices, output
