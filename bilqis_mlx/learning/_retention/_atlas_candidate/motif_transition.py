"""B12-issued custody for one terminal B07 motif-allocation transition."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json

from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents

from .common import invalid, is_digest


MOTIF_TRANSITION_SCHEMA = "bilqis.mlx.b12-motif-allocation-transition/v1"
_ISSUER = object()


def _canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


@dataclass(frozen=True, init=False)
class CandidateMotifAllocationTransition:
    """Live proof that B12 materialized one source-qualified B07 proposal.

    The object is terminal for a CandidateTransaction: training must have
    happened first and no later optimizer step may run after this transition.
    """

    parent_manifest_sha256: str
    parent_extents_sha256: str
    candidate_extents: GenerationExtents
    parent_allocation_sha256: str
    candidate_allocation_sha256: str
    motif_candidate_sha256: str
    approved_context_sha256: str
    added_pages: int
    source_continuation: object = field(repr=False, compare=False)
    schema_version: str = MOTIF_TRANSITION_SCHEMA
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        invalid()

    def __post_init__(self):
        from bilqis_mlx.runtime.bamf_bundle.source_continuation import (
            _require_source_qualified_continuation,
        )

        if (getattr(self, "_issuance", None) is not _ISSUER
                or any(not is_digest(value) for value in (
                    self.parent_manifest_sha256, self.parent_extents_sha256,
                    self.parent_allocation_sha256, self.candidate_allocation_sha256,
                    self.motif_candidate_sha256, self.approved_context_sha256))
                or type(self.candidate_extents) is not GenerationExtents
                or type(self.added_pages) is not int or self.added_pages not in (0, 1)
                or self.schema_version != MOTIF_TRANSITION_SCHEMA):
            invalid()
        continuation = _require_source_qualified_continuation(self.source_continuation)
        approved = continuation.approved
        if (continuation.parent_manifest_sha256 != self.parent_manifest_sha256
                or continuation.parent_extents_sha256 != self.parent_extents_sha256
                or continuation.parent_allocation_sha256 != self.parent_allocation_sha256
                or approved.candidate.digest != self.motif_candidate_sha256
                or approved.approved_context_digest != self.approved_context_sha256):
            invalid()

    def to_record(self) -> dict:
        return {
            "schema": self.schema_version,
            "parent_manifest_sha256": self.parent_manifest_sha256,
            "parent_extents_sha256": self.parent_extents_sha256,
            "candidate_extents_sha256": self.candidate_extents.digest,
            "parent_allocation_sha256": self.parent_allocation_sha256,
            "candidate_allocation_sha256": self.candidate_allocation_sha256,
            "motif_candidate_sha256": self.motif_candidate_sha256,
            "approved_context_sha256": self.approved_context_sha256,
            "added_pages": self.added_pages,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical(self.to_record())).hexdigest()


def _issue_candidate_motif_allocation_transition(
        *, parent_manifest_sha256, parent_extents, candidate_extents,
        parent_allocation_sha256, candidate_allocation_sha256,
        motif_candidate_sha256, approved_context_sha256, added_pages,
        source_continuation,
) -> CandidateMotifAllocationTransition:
    if type(parent_extents) is not GenerationExtents:
        invalid()
    transition = object.__new__(CandidateMotifAllocationTransition)
    for name, value in (
            ("parent_manifest_sha256", parent_manifest_sha256),
            ("parent_extents_sha256", parent_extents.digest),
            ("candidate_extents", candidate_extents),
            ("parent_allocation_sha256", parent_allocation_sha256),
            ("candidate_allocation_sha256", candidate_allocation_sha256),
            ("motif_candidate_sha256", motif_candidate_sha256),
            ("approved_context_sha256", approved_context_sha256),
            ("added_pages", added_pages),
            ("source_continuation", source_continuation),
            ("schema_version", MOTIF_TRANSITION_SCHEMA), ("_issuance", _ISSUER)):
        object.__setattr__(transition, name, value)
    transition.__post_init__()
    return transition


def _require_candidate_motif_allocation_transition(value) -> None:
    if (type(value) is not CandidateMotifAllocationTransition
            or getattr(value, "_issuance", None) is not _ISSUER):
        invalid()
    value.__post_init__()
