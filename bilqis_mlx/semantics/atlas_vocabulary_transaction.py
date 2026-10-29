"""A02.2 detached B01 tensor-tree staging, before Factory admission authority.

The live Factory/checkpoint owner publishes a candidate only after independent
source, optimizer and retention admission. This module does not write a pointer.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Mapping

from ..errors import ErrorBus, SEMANTIC_FRAME
from ..runtime.model_topology_v2 import (
    ModelTopologySpecV2, bamf_serialization_arrays,
)
from .atlas_vocabulary import (
    CandidateState, VocabularyBankParent, VocabularyExtension,
    STAGED_ONLY, apply_vocabulary_extension,
)
from .atlas_vocabulary_resources import (
    DEFAULT_DISK_RESERVE_BYTES, DEFAULT_EXTRA_PLANNING_BYTES,
    VocabularyResourceEstimate, estimate_vocabulary_resources,
)

PREPARED_SCHEMA = "bilqis.atlas-vocabulary-full-candidate/v1"


def _invalid(reason: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<atlas-vocabulary-transaction>",
        span_start=0, span_end=0,
    )


@dataclass(frozen=True)
class FullVocabularyParent:
    bank_parent: VocabularyBankParent
    topology: ModelTopologySpecV2
    parameters: Mapping[str, object]
    optimizer_state: Mapping[str, object]
    observed_available_bytes: int
    reserve_bytes: int = DEFAULT_DISK_RESERVE_BYTES
    extra_planning_bytes: int = DEFAULT_EXTRA_PLANNING_BYTES


@dataclass(frozen=True)
class PreparedVocabularyCandidate:
    """Complete B01 tensor tree and source-bound bank delta, still unadmitted."""

    bank_candidate: CandidateState
    topology_digest: str
    extents_digest: str
    active_mask_sha256: str
    resource_estimate: VocabularyResourceEstimate
    parameters: Mapping[str, object]
    optimizer_state: Mapping[str, object]
    status: str = STAGED_ONLY
    schema_version: str = PREPARED_SCHEMA


def stage_full_vocabulary_extension(
    parent: FullVocabularyParent,
    plan: VocabularyExtension,
) -> PreparedVocabularyCandidate:
    """Stage the exact complete B01 parameter/AdamW tree for a later commit."""
    if (type(parent) is not FullVocabularyParent
            or type(parent.topology) is not ModelTopologySpecV2
            or not isinstance(parent.parameters, Mapping)
            or not isinstance(parent.optimizer_state, Mapping)):
        _invalid("BAMF_VOCABULARY_FULL_PARENT_INVALID")
    banks = parent.bank_parent
    if type(banks) is not VocabularyBankParent:
        _invalid("BAMF_VOCABULARY_FULL_PARENT_INVALID")
    extents = banks.prior.extents
    # B01 verifies every parameter name, shape, FP32 moment and optimizer
    # scalar before any allocation. The bank slice must be the exact same
    # objects, not a caller's separately reconstructed approximation.
    bamf_serialization_arrays(
        parent.topology, extents,
        parent.parameters, parent.optimizer_state)
    for bank in range(extents.semantic_bank_count):
        name = f"identity.bank.{bank}"
        if (banks.weights[bank] is not parent.parameters[name]
                or banks.moments_m[bank] is not parent.optimizer_state[name]["m"]
                or banks.moments_v[bank] is not parent.optimizer_state[name]["v"]):
            _invalid("BAMF_VOCABULARY_BANK_SLICE_DRIFT")
    estimate = estimate_vocabulary_resources(
        banks.prior, plan,
        observed_available_bytes=parent.observed_available_bytes,
        reserve_bytes=parent.reserve_bytes,
        extra_planning_bytes=parent.extra_planning_bytes)
    if not estimate.fits:
        _invalid("BAMF_VOCABULARY_DISK_STAGING_BUDGET_EXCEEDED")
    staged = apply_vocabulary_extension(banks, plan)
    parameters = dict(parent.parameters)
    optimizer_state = dict(parent.optimizer_state)
    for bank, weight in enumerate(staged.weights):
        name = f"identity.bank.{bank}"
        parameters[name] = weight
        optimizer_state[name] = {
            "m": staged.moments_m[bank],
            "v": staged.moments_v[bank],
        }
    bamf_serialization_arrays(
        parent.topology, staged.extents,
        parameters, optimizer_state)
    if (optimizer_state["step"] is not parent.optimizer_state["step"]
            or optimizer_state["learning_rate"]
            is not parent.optimizer_state["learning_rate"]):
        _invalid("BAMF_VOCABULARY_OPTIMIZER_SCALAR_DRIFT")
    return PreparedVocabularyCandidate(
        bank_candidate=staged,
        topology_digest=parent.topology.digest,
        extents_digest=staged.extents.digest,
        active_mask_sha256=hashlib.sha256(staged.active_mask).hexdigest(),
        resource_estimate=estimate,
        parameters=parameters,
        optimizer_state=optimizer_state,
    )
