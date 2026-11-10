"""B02 generation-active semantic-row execution authority."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib

from lib.ithkuil.src.skos.publication import json_bytes

from bilqis_mlx.data_plane import SHA256_HEX_LENGTH
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2
from bilqis_mlx.semantics.atlas_features import AtlasFeatures


def _invalid(reason: str) -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID, reason=reason)


def _digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == SHA256_HEX_LENGTH
        and all(char in "0123456789abcdef" for char in value)
    )


_ACTIVE_SEMANTIC_ROWS_ISSUER = object()


@dataclass(frozen=True, init=False)
class BamfActiveSemanticRows:
    """Generation-bound numerical view of owner-issued active identity rows.

    The record transports numerical activity only. It grants no source admission,
    generation acceptance, or publication authority.
    """

    run_id: str
    generation: int
    extents_digest: str
    feature_digest: str
    semantic_release: str
    active_semantic_digest: str
    active_indices: tuple[int, ...]
    schema_version: str = "bilqis.mlx.b02-active-semantic-rows/v1"
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid("B02_ACTIVE_SEMANTIC_ROWS_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self) -> None:
        if (
            getattr(self, "_issuance", None) is not _ACTIVE_SEMANTIC_ROWS_ISSUER
            or not isinstance(self.run_id, str) or not self.run_id
            or type(self.generation) is not int or self.generation < 0
            or not all(_digest(value) for value in (
                self.extents_digest, self.feature_digest, self.semantic_release,
                self.active_semantic_digest,
            ))
            or type(self.active_indices) is not tuple or not self.active_indices
            or self.active_indices != tuple(sorted(set(self.active_indices)))
            or any(type(index) is not int or index < 0 for index in self.active_indices)
            or hashlib.sha256(json_bytes(list(self.active_indices))).hexdigest()
            != self.active_semantic_digest
            or self.schema_version != "bilqis.mlx.b02-active-semantic-rows/v1"
        ):
            _invalid("B02_ACTIVE_SEMANTIC_ROWS_INVALID")


def _issue_bamf_active_semantic_rows(
        run_id: str, generation: int, extents: GenerationExtents,
        features: AtlasFeatures, active_indices: tuple[int, ...]) -> BamfActiveSemanticRows:
    """Issue the numerical B02 view after an owner has established generation custody."""
    if (type(extents) is not GenerationExtents or type(features) is not AtlasFeatures
            or extents.factor_map_digest != features.digest):
        _invalid("B02_ACTIVE_SEMANTIC_ROWS_OWNER_INPUT_INVALID")
    record = object.__new__(BamfActiveSemanticRows)
    for name, value in (
        ("run_id", run_id), ("generation", generation),
        ("extents_digest", extents.digest), ("feature_digest", features.digest),
        ("semantic_release", features.semantic_release),
        ("active_semantic_digest", extents.active_semantic_digest),
        ("active_indices", active_indices),
        ("schema_version", "bilqis.mlx.b02-active-semantic-rows/v1"),
        ("_issuance", _ACTIVE_SEMANTIC_ROWS_ISSUER),
    ):
        object.__setattr__(record, name, value)
    record.__post_init__()
    return record


def bind_candidate_active_semantic_rows(candidate, authenticated) -> BamfActiveSemanticRows:
    """Bind retained generation-active rows to one authenticated lifecycle context."""
    from bilqis_mlx.learning.atlas_candidate import CandidateState as RetainedCandidateState
    from bilqis_mlx.runtime.bamf_bundle import (
        AuthenticatedCandidateFeatureContext, AuthenticatedGenerationFeatureContext,
        BamfBundleCandidate, CompleteStudent,
    )

    candidate_context = (
        type(candidate) is BamfBundleCandidate
        and type(authenticated) is AuthenticatedCandidateFeatureContext)
    accepted_context = (
        type(candidate) is CompleteStudent
        and type(authenticated) is AuthenticatedGenerationFeatureContext)
    if (not (candidate_context or accepted_context)
            or type(candidate.extents) is not GenerationExtents
            or type(candidate.retained_state) is not RetainedCandidateState
            or type(authenticated.features) is not AtlasFeatures):
        _invalid("B02_ACTIVE_SEMANTIC_ROWS_OWNER_INPUT_INVALID")
    candidate.retained_state.__post_init__()
    authenticated.__post_init__()
    if accepted_context and (
            authenticated.receipt.run_id != candidate.run_id
            or authenticated.receipt.generation != candidate.generation
            or authenticated.receipt.active_set_sha256
            != candidate.extents.active_semantic_digest):
        _invalid("B02_ACTIVE_SEMANTIC_ROWS_OWNER_DRIFT")
    indices = tuple(
        row.bank_index * ModelTopologySpecV2.semantic_bank_rows + row.row_index
        for row in candidate.retained_state.policy.row_ages
    )
    if (candidate.extents.factor_map_digest != authenticated.features.digest
            or candidate.semantic_abi.get("active_set_sha256")
            != candidate.extents.active_semantic_digest
            or any(index >= candidate.extents.semantic_bank_count
                   * ModelTopologySpecV2.semantic_bank_rows for index in indices)
            or any(index >= len(authenticated.snapshot.abi_entries)
                   or authenticated.snapshot.abi_entries[index].index != index
                   for index in indices)):
        _invalid("B02_ACTIVE_SEMANTIC_ROWS_OWNER_DRIFT")
    return _issue_bamf_active_semantic_rows(
        candidate.run_id, candidate.generation, candidate.extents,
        authenticated.features, indices)


__all__ = (
    "BamfActiveSemanticRows",
    "bind_candidate_active_semantic_rows",
)
