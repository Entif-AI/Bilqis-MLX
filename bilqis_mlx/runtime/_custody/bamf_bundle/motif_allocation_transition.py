"""B13-issued generation transition for one accepted B07 allocation change."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from bilqis_mlx.data_plane import SHA256_HEX_LENGTH
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning._atlas_candidate.motif_transition import (
    CandidateMotifAllocationTransition,
    _require_candidate_motif_allocation_transition,
)


MOTIF_ALLOCATION_TRANSITION_SCHEMA = "bilqis.mlx.bamf-generation-transition/v3"
MOTIF_ALLOCATION_KIND = "MOTIF_ALLOCATION"
_DIGEST_FIELDS = (
    "b12_transition_sha256", "parent_extents_sha256", "candidate_extents_sha256",
    "parent_allocation_sha256", "candidate_allocation_sha256",
    "motif_candidate_sha256", "approved_context_sha256",
    "candidate_identity_sha256",
)
_FIELDS = ("schema", "kind", "invalidate_derived_caches", "added_pages") + _DIGEST_FIELDS
_ISSUER = object()


def _invalid():
    ErrorBus.Raise(
        SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID,
        reason="BAMF_GENERATION_TRANSITION_INVALID")


def _hex(value):
    return (type(value) is str and len(value) == SHA256_HEX_LENGTH
            and all(char in "0123456789abcdef" for char in value))


@dataclass(frozen=True, init=False)
class MotifAllocationTransition(Mapping):
    b12_transition_sha256: str
    parent_extents_sha256: str
    candidate_extents_sha256: str
    parent_allocation_sha256: str
    candidate_allocation_sha256: str
    motif_candidate_sha256: str
    approved_context_sha256: str
    candidate_identity_sha256: str
    added_pages: int
    schema: str = MOTIF_ALLOCATION_TRANSITION_SCHEMA
    kind: str = MOTIF_ALLOCATION_KIND
    invalidate_derived_caches: bool = True
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid()

    def __post_init__(self):
        if getattr(self, "_issuance", None) is not _ISSUER:
            _invalid()
        validate_motif_allocation_transition(self)

    def __iter__(self):
        return iter(_FIELDS)

    def __len__(self):
        return len(_FIELDS)

    def __getitem__(self, key):
        if key not in _FIELDS:
            raise KeyError(key)
        return getattr(self, key)


def is_motif_allocation_transition(value) -> bool:
    return (isinstance(value, Mapping)
            and value.get("schema") == MOTIF_ALLOCATION_TRANSITION_SCHEMA
            and value.get("kind") == MOTIF_ALLOCATION_KIND)


def validate_motif_allocation_transition(value) -> None:
    if (not isinstance(value, Mapping) or set(value) != set(_FIELDS)
            or value.get("schema") != MOTIF_ALLOCATION_TRANSITION_SCHEMA
            or value.get("kind") != MOTIF_ALLOCATION_KIND
            or value.get("invalidate_derived_caches") is not True
            or type(value.get("added_pages")) is not int
            or value.get("added_pages") not in (0, 1)
            or any(not _hex(value.get(name)) for name in _DIGEST_FIELDS)):
        _invalid()


def require_issued_motif_allocation_transition(value) -> None:
    if (type(value) is not MotifAllocationTransition
            or getattr(value, "_issuance", None) is not _ISSUER):
        _invalid()
    value.__post_init__()


def _issue_motif_allocation_transition(
        b12: CandidateMotifAllocationTransition, *, candidate_identity_sha256: str,
) -> MotifAllocationTransition:
    _require_candidate_motif_allocation_transition(b12)
    transition = object.__new__(MotifAllocationTransition)
    values = {
        "b12_transition_sha256": b12.digest,
        "parent_extents_sha256": b12.parent_extents_sha256,
        "candidate_extents_sha256": b12.candidate_extents.digest,
        "parent_allocation_sha256": b12.parent_allocation_sha256,
        "candidate_allocation_sha256": b12.candidate_allocation_sha256,
        "motif_candidate_sha256": b12.motif_candidate_sha256,
        "approved_context_sha256": b12.approved_context_sha256,
        "candidate_identity_sha256": candidate_identity_sha256,
        "added_pages": b12.added_pages,
        "schema": MOTIF_ALLOCATION_TRANSITION_SCHEMA,
        "kind": MOTIF_ALLOCATION_KIND,
        "invalidate_derived_caches": True,
        "_issuance": _ISSUER,
    }
    for name, value in values.items():
        object.__setattr__(transition, name, value)
    transition.__post_init__()
    return transition
