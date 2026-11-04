"""Approved-only context projection and cache identity."""
from __future__ import annotations

from dataclasses import dataclass

from .._frame_schema.instances import AtomicFrame, FrameInstance
from .._frame_schema.roles import RoleOccurrence
from ..foundation.domains import contract_digest
from .admission import check_context_eligibility
from .authority import ContextEligibility, ContextPolicy, SourceFrontier, TaskScope
from .common import PROJECTION_SCHEMA, _digest, _invalid
from .evidence import _envelope_projection
from .results import ContextHold, EligibleContext

@dataclass(frozen=True)
class ApprovedContextProjection:
    """Immutable approved-only readout, not a bearer permission credential."""
    eligible: EligibleContext
    envelopes: tuple[ContextEligibility, ...]
    schema_version: str = PROJECTION_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.eligible, EligibleContext)
                or not isinstance(self.envelopes, tuple)
                or self.schema_version != PROJECTION_SCHEMA):
            _invalid("BAMF_CONTEXT_PROJECTION_INVALID")
        by_handle = {item.frame_handle: item for item in self.envelopes}
        if len(by_handle) != len(self.envelopes):
            _invalid("BAMF_CONTEXT_PROJECTION_DUPLICATE")
        if tuple(sorted(by_handle)) != tuple(
                item.frame_handle for item in self.eligible.frames):
            _invalid("BAMF_CONTEXT_PROJECTION_MEMBERSHIP_DRIFT")
        for approved in self.eligible.frames:
            source = by_handle[approved.frame_handle]
            if (source.source_handle != approved.source_handle
                    or source.frame.occurrence_id != approved.occurrence_id
                    or source.frame.content_digest != approved.content_digest
                    or tuple(member.source_handle for member in source.members)
                    != approved.member_handles
                    or _digest(_envelope_projection(source))
                    != approved.envelope_digest):
                _invalid("BAMF_CONTEXT_PROJECTION_EVIDENCE_DRIFT")

    @property
    def digest(self) -> str:
        return self.eligible.digest

    @property
    def attention_handles(self) -> tuple[tuple[str, str], ...]:
        """Only source-approved frame/member handles can become positions."""
        return tuple(
            (frame.frame_handle, member)
            for frame in self.eligible.frames
            for member in frame.member_handles
        )

    def frame(self, handle: str) -> FrameInstance | AtomicFrame:
        for envelope in self.envelopes:
            if envelope.frame_handle == handle:
                return envelope.frame
        _invalid("BAMF_CONTEXT_PROJECTION_HANDLE_NOT_APPROVED")

    def member(self, handle: str) -> RoleOccurrence | AtomicFrame:
        for envelope in self.envelopes:
            for member in envelope.members:
                if member.source_handle != handle:
                    continue
                if isinstance(envelope.frame, AtomicFrame):
                    return envelope.frame
                for binding in envelope.frame.bindings:
                    if binding.key == member.key:
                        return binding
        _invalid("BAMF_CONTEXT_PROJECTION_MEMBER_NOT_APPROVED")

    def cache_key(self, *immediate_dependencies: object) -> str:
        return contract_digest({
            "approved_context": self.digest,
            "immediate_dependencies": immediate_dependencies,
        })


def project_context(
    frames: tuple[ContextEligibility, ...],
    task_scope: TaskScope,
    source_frontier: SourceFrontier,
    policy: ContextPolicy,
) -> ApprovedContextProjection | ContextHold:
    """One eligibility gate for exact readout, attention and cache identity."""
    approved = check_context_eligibility(
        frames, task_scope, source_frontier, policy)
    if isinstance(approved, ContextHold):
        return approved
    return ApprovedContextProjection(
        approved, tuple(sorted(frames, key=lambda item: item.frame_handle)))

