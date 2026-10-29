"""Source-bound context admission before packing, attention or motif lookup."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re

from ..errors import ErrorBus, SEMANTIC_FRAME
from .domains import contract_digest
from .frame_schema import AtomicFrame, FrameInstance, RoleOccurrence


ELIGIBILITY_SCHEMA = "bilqis.context-eligibility/v1"
MEMBER_SCHEMA = "bilqis.context-member/v1"
GRANT_SCHEMA = "bilqis.context-source-grant/v1"
FRONTIER_SCHEMA = "bilqis.context-source-frontier/v1"
TASK_SCHEMA = "bilqis.context-task-scope/v1"
POLICY_SCHEMA = "bilqis.context-policy/v1"
APPROVED_FRAME_SCHEMA = "bilqis.context-approved-frame/v1"
ELIGIBLE_CONTEXT_SCHEMA = "bilqis.eligible-context/v1"
CONTEXT_HOLD_SCHEMA = "bilqis.context-hold/v1"
PROJECTION_SCHEMA = "bilqis.context-approved-projection/v1"
C09_INVALIDATION_SCHEMA = "bilqis.c09-context-invalidation/v1"
CONTEXT_TRANSITION_SCHEMA = "bilqis.context-transition/v1"
PUBLIC_FORMAL = "PUBLIC_FORMAL"
MAX_CONTEXT_HOLD_DIAGNOSTICS = 16
JOIN_PAIR_ARITY = 2
MIN_JOIN_SET_ARITY = 3
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<context>", span_start=0, span_end=0,
    )


def _digest(value: object) -> str:
    return hashlib.sha256(
        (json.dumps(value, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    ).hexdigest()


def _name(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _epoch(value: object) -> bool:
    return type(value) is int and value >= 0


def _names(value: object) -> bool:
    return (isinstance(value, tuple)
            and all(_name(item) for item in value)
            and value == tuple(sorted(set(value))))


def frame_evidence_digest(frame: FrameInstance | AtomicFrame) -> str:
    """Canonical source evidence identity, including lineage and all bindings."""
    if not isinstance(frame, (FrameInstance, AtomicFrame)):
        _invalid("BAMF_CONTEXT_FRAME_EVIDENCE_INVALID")
    return _digest({"kind": "frame", "frame": asdict(frame)})


def member_evidence_digest(
    frame: FrameInstance | AtomicFrame, member: ContextMember,
) -> str:
    """Bind a member handle to one exact source occurrence and visibility."""
    if not isinstance(frame, (FrameInstance, AtomicFrame)):
        _invalid("BAMF_CONTEXT_MEMBER_EVIDENCE_INVALID")
    if not isinstance(member, ContextMember):
        _invalid("BAMF_CONTEXT_MEMBER_EVIDENCE_INVALID")
    if isinstance(frame, AtomicFrame):
        if member.key != ("<atomic>", 0):
            _invalid("BAMF_CONTEXT_MEMBER_EVIDENCE_INVALID")
        evidence = {"kind": "atomic-member", "frame": asdict(frame)}
    else:
        binding = next(
            (binding for binding in frame.bindings if binding.key == member.key),
            None,
        )
        if binding is None:
            _invalid("BAMF_CONTEXT_MEMBER_EVIDENCE_INVALID")
        evidence = {
            "kind": "member",
            "frame_occurrence_id": frame.occurrence_id,
            "binding": asdict(binding),
        }
    return _digest({**evidence, "visible_at_prefix": member.visible_at_prefix})


@dataclass(frozen=True)
class ContextMember:
    role_id: str
    occurrence_index: int
    source_handle: str
    visible_at_prefix: int
    schema_version: str = MEMBER_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.role_id) or not _epoch(self.occurrence_index)
                or not _name(self.source_handle)
                or not _epoch(self.visible_at_prefix)
                or self.schema_version != MEMBER_SCHEMA):
            _invalid("BAMF_CONTEXT_MEMBER_INVALID")

    @property
    def key(self) -> tuple[str, int]:
        return self.role_id, self.occurrence_index


@dataclass(frozen=True)
class ContextEligibility:
    frame_handle: str
    frame: FrameInstance | AtomicFrame
    source_handle: str
    members: tuple[ContextMember, ...]
    principal_id: str
    tenant_id: str
    purpose: str | None
    source_regime: str
    semantic_release: str
    jurisdiction: str
    scope: str
    join_class: str
    policy_epoch: int
    rights_epoch: int
    correction_generation: int
    observed_at: int
    effective_from: int
    effective_until: int | None
    causal_prefix_end: int
    schema_version: str = ELIGIBILITY_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.frame_handle)
                or not isinstance(self.frame, (FrameInstance, AtomicFrame))
                or not _name(self.source_handle)
                or not isinstance(self.members, tuple)
                or any(not isinstance(item, ContextMember) for item in self.members)
                or not _name(self.principal_id) or not _name(self.tenant_id)
                or (self.purpose is not None and not isinstance(self.purpose, str))
                or not _name(self.source_regime)
                or not isinstance(self.semantic_release, str)
                or not _SHA256.fullmatch(self.semantic_release)
                or not all(_name(item) for item in (
                    self.jurisdiction, self.scope, self.join_class))
                or not all(_epoch(item) for item in (
                    self.policy_epoch, self.rights_epoch,
                    self.correction_generation, self.observed_at,
                    self.effective_from, self.causal_prefix_end))
                or (self.effective_until is not None
                    and (not _epoch(self.effective_until)
                         or self.effective_until <= self.effective_from))
                or self.schema_version != ELIGIBILITY_SCHEMA):
            _invalid("BAMF_CONTEXT_ELIGIBILITY_INVALID")


@dataclass(frozen=True)
class SourceGrant:
    source_handle: str
    principal_id: str
    tenant_id: str
    source_regime: str
    semantic_release: str
    evidence_digest: str
    permitted_purposes: tuple[str, ...]
    permitted_jurisdictions: tuple[str, ...]
    permitted_scopes: tuple[str, ...]
    rights_epoch: int
    correction_generation: int
    observed_at: int
    effective_from: int
    effective_until: int | None = None
    revoked: bool = False
    schema_version: str = GRANT_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_name(item) for item in (
                    self.source_handle, self.principal_id,
                    self.tenant_id, self.source_regime))
                or not all(_names(item) and bool(item) for item in (
                    self.permitted_purposes, self.permitted_jurisdictions,
                    self.permitted_scopes))
                or not all(isinstance(item, str) and _SHA256.fullmatch(item)
                           for item in (self.semantic_release, self.evidence_digest))
                or not all(_epoch(item) for item in (
                    self.rights_epoch, self.correction_generation,
                    self.observed_at, self.effective_from))
                or (self.effective_until is not None
                    and (not _epoch(self.effective_until)
                         or self.effective_until <= self.effective_from))
                or type(self.revoked) is not bool
                or self.schema_version != GRANT_SCHEMA):
            _invalid("BAMF_CONTEXT_SOURCE_GRANT_INVALID")


@dataclass(frozen=True)
class SourceFrontier:
    rights_epoch: int
    correction_generation: int
    grants: tuple[SourceGrant, ...]
    schema_version: str = FRONTIER_SCHEMA

    def __post_init__(self) -> None:
        if (not _epoch(self.rights_epoch)
                or not _epoch(self.correction_generation)
                or not isinstance(self.grants, tuple)
                or any(not isinstance(item, SourceGrant) for item in self.grants)
                or tuple(item.source_handle for item in self.grants)
                != tuple(sorted({item.source_handle for item in self.grants}))
                or self.schema_version != FRONTIER_SCHEMA):
            _invalid("BAMF_CONTEXT_SOURCE_FRONTIER_INVALID")


@dataclass(frozen=True)
class TaskScope:
    principal_id: str
    tenant_id: str
    purpose: str | None
    semantic_release: str
    jurisdiction: str
    scope: str
    observed_frontier: int
    effective_time: int
    causal_prefix_end: int
    schema_version: str = TASK_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_name(item) for item in (
                    self.principal_id, self.tenant_id,
                    self.jurisdiction, self.scope))
                or (self.purpose is not None and not isinstance(self.purpose, str))
                or not isinstance(self.semantic_release, str)
                or not _SHA256.fullmatch(self.semantic_release)
                or not all(_epoch(item) for item in (
                    self.observed_frontier, self.effective_time,
                    self.causal_prefix_end))
                or self.schema_version != TASK_SCHEMA):
            _invalid("BAMF_CONTEXT_TASK_INVALID")


@dataclass(frozen=True)
class ContextPolicy:
    policy_id: str
    policy_epoch: int
    rights_epoch: int
    allowed_purposes: tuple[str, ...]
    allowed_regimes: tuple[str, ...]
    allowed_jurisdictions: tuple[str, ...]
    allowed_scopes: tuple[str, ...]
    allowed_join_classes: tuple[str, ...]
    allowed_join_pairs: tuple[tuple[str, str], ...]
    allowed_join_sets: tuple[tuple[str, ...], ...]
    schema_version: str = POLICY_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.policy_id)
                or not _epoch(self.policy_epoch) or not _epoch(self.rights_epoch)
                or not all(_names(item) for item in (
                    self.allowed_purposes, self.allowed_regimes,
                    self.allowed_jurisdictions, self.allowed_scopes,
                    self.allowed_join_classes))
                or not isinstance(self.allowed_join_pairs, tuple)
                or any(not isinstance(item, tuple) or len(item) != JOIN_PAIR_ARITY
                       or not all(_name(value) for value in item)
                       or item != tuple(sorted(item))
                       for item in self.allowed_join_pairs)
                or self.allowed_join_pairs != tuple(sorted(set(self.allowed_join_pairs)))
                or not isinstance(self.allowed_join_sets, tuple)
                or any(not isinstance(item, tuple) or len(item) < MIN_JOIN_SET_ARITY
                       or not all(_name(value) for value in item)
                       or item != tuple(sorted(item))
                       for item in self.allowed_join_sets)
                or self.allowed_join_sets != tuple(sorted(set(self.allowed_join_sets)))
                or self.schema_version != POLICY_SCHEMA):
            _invalid("BAMF_CONTEXT_POLICY_INVALID")


@dataclass(frozen=True)
class ApprovedFrame:
    frame_handle: str
    source_handle: str
    member_handles: tuple[str, ...]
    occurrence_id: str
    content_digest: str
    join_class: str
    envelope_digest: str
    schema_version: str = APPROVED_FRAME_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_name(item) for item in (
                    self.frame_handle, self.source_handle, self.join_class))
                or not isinstance(self.member_handles, tuple)
                or any(not _name(item) for item in self.member_handles)
                or not all(isinstance(item, str) and _SHA256.fullmatch(item)
                           for item in (
                               self.occurrence_id, self.content_digest,
                               self.envelope_digest))
                or self.schema_version != APPROVED_FRAME_SCHEMA):
            _invalid("BAMF_CONTEXT_APPROVED_FRAME_INVALID")


@dataclass(frozen=True)
class EligibleContext:
    frames: tuple[ApprovedFrame, ...]
    allowed_join_classes: tuple[str, ...]
    digest: str
    schema_version: str = ELIGIBLE_CONTEXT_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.frames, tuple) or not self.frames
                or any(not isinstance(item, ApprovedFrame) for item in self.frames)
                or tuple(item.frame_handle for item in self.frames)
                != tuple(sorted({item.frame_handle for item in self.frames}))
                or not _names(self.allowed_join_classes)
                or not isinstance(self.digest, str)
                or not _SHA256.fullmatch(self.digest)
                or self.schema_version != ELIGIBLE_CONTEXT_SCHEMA):
            _invalid("BAMF_CONTEXT_APPROVED_VIEW_INVALID")


@dataclass(frozen=True)
class ContextHold:
    reason_codes: tuple[str, ...]
    source_handles: tuple[str, ...]
    diagnostics: tuple[tuple[str, str], ...]
    schema_version: str = CONTEXT_HOLD_SCHEMA

    def __post_init__(self) -> None:
        if (not _names(self.reason_codes) or not self.reason_codes
                or not _names(self.source_handles)
                or not isinstance(self.diagnostics, tuple)
                or len(self.diagnostics) > MAX_CONTEXT_HOLD_DIAGNOSTICS
                or any(not isinstance(item, tuple) or len(item) != JOIN_PAIR_ARITY
                       or not all(_name(value) for value in item)
                       for item in self.diagnostics)
                or self.diagnostics != tuple(sorted(set(self.diagnostics)))
                or self.schema_version != CONTEXT_HOLD_SCHEMA):
            _invalid("BAMF_CONTEXT_HOLD_INVALID")


def _envelope_projection(item: ContextEligibility) -> dict:
    """Hash policy-relevant metadata without embedding the source frame."""
    return {
        "frame_handle": item.frame_handle,
        "occurrence_id": item.frame.occurrence_id,
        "content_digest": item.frame.content_digest,
        "source_handle": item.source_handle,
        "members": [asdict(member) for member in item.members],
        "principal_id": item.principal_id,
        "tenant_id": item.tenant_id,
        "purpose": item.purpose,
        "source_regime": item.source_regime,
        "semantic_release": item.semantic_release,
        "jurisdiction": item.jurisdiction,
        "scope": item.scope,
        "join_class": item.join_class,
        "policy_epoch": item.policy_epoch,
        "rights_epoch": item.rights_epoch,
        "correction_generation": item.correction_generation,
        "observed_at": item.observed_at,
        "effective_from": item.effective_from,
        "effective_until": item.effective_until,
        "causal_prefix_end": item.causal_prefix_end,
        "schema_version": item.schema_version,
    }


def _frame_release_matches(item: ContextEligibility) -> bool:
    if item.semantic_release == "":
        return False
    if isinstance(item.frame, AtomicFrame):
        return True
    for binding in item.frame.bindings:
        concepts = ((binding.concept,) if binding.concept is not None
                    else binding.alternatives)
        if any(concept.semantic_release != item.semantic_release
               for concept in concepts):
            return False
    return True


def check_context_eligibility(
    frames: tuple[ContextEligibility, ...],
    task_scope: TaskScope,
    source_frontier: SourceFrontier,
    policy: ContextPolicy,
) -> EligibleContext | ContextHold:
    """Admit the whole proposed context, or return handles-only hold reasons.

    Individual grants are necessary but insufficient. Every pair and the
    entire multi-frame join must be explicitly permitted before a handle is
    exposed to a solver, cache, neural position or motif reader.
    """
    if (not isinstance(frames, tuple)
            or any(not isinstance(item, ContextEligibility) for item in frames)
            or not isinstance(task_scope, TaskScope)
            or not isinstance(source_frontier, SourceFrontier)
            or not isinstance(policy, ContextPolicy)):
        _invalid("BAMF_CONTEXT_ARGUMENT_INVALID")

    if not frames:
        return ContextHold(("BAMF_CONTEXT_EMPTY",), (), ())

    reasons: set[str] = set()
    blocked: set[str] = set()
    diagnostics: set[tuple[str, str]] = set()

    def hold(reason: str, handle: str) -> None:
        reasons.add(reason)
        blocked.add(handle)
        diagnostics.add((reason, handle))

    grants = {grant.source_handle: grant for grant in source_frontier.grants}
    used_handles: set[str] = set()
    if task_scope.purpose is None or not task_scope.purpose:
        hold("BAMF_CONTEXT_PURPOSE_UNRESOLVED", frames[0].source_handle)
    elif task_scope.purpose not in policy.allowed_purposes:
        hold("BAMF_CONTEXT_PURPOSE_FORBIDDEN", frames[0].source_handle)
    if (task_scope.jurisdiction not in policy.allowed_jurisdictions
            or task_scope.scope not in policy.allowed_scopes):
        hold("BAMF_CONTEXT_SCOPE_FORBIDDEN", frames[0].source_handle)
    if source_frontier.rights_epoch != policy.rights_epoch:
        hold("BAMF_CONTEXT_RIGHTS_EPOCH_MISMATCH", frames[0].source_handle)
    if len({item.frame_handle for item in frames}) != len(frames):
        hold("BAMF_CONTEXT_FRAME_DUPLICATE", frames[0].source_handle)

    for item in frames:
        handle = item.source_handle
        if (item.semantic_release != task_scope.semantic_release
                or not _frame_release_matches(item)):
            hold("BAMF_CONTEXT_RELEASE_MISMATCH", handle)
        if (item.principal_id != task_scope.principal_id
                or item.tenant_id != task_scope.tenant_id
                or item.jurisdiction != task_scope.jurisdiction
                or item.scope != task_scope.scope):
            hold("BAMF_CONTEXT_SCOPE_FORBIDDEN", handle)
        if item.purpose is None or not item.purpose:
            hold("BAMF_CONTEXT_PURPOSE_UNRESOLVED", handle)
        elif item.purpose != task_scope.purpose:
            hold("BAMF_CONTEXT_PURPOSE_FORBIDDEN", handle)
        if item.source_regime not in policy.allowed_regimes:
            hold("BAMF_CONTEXT_SOURCE_REGIME_FORBIDDEN", handle)
        if item.join_class not in policy.allowed_join_classes:
            hold("BAMF_CONTEXT_FORBIDDEN_JOIN", handle)
        if item.policy_epoch != policy.policy_epoch:
            hold("BAMF_CONTEXT_POLICY_EPOCH_MISMATCH", handle)
        if item.rights_epoch != source_frontier.rights_epoch:
            hold("BAMF_CONTEXT_RIGHTS_EPOCH_MISMATCH", handle)
        if item.correction_generation != source_frontier.correction_generation:
            hold("BAMF_CONTEXT_CORRECTION_STALE", handle)
        if (item.observed_at > task_scope.observed_frontier
                or item.effective_from > task_scope.effective_time
                or (item.effective_until is not None
                    and task_scope.effective_time >= item.effective_until)):
            hold("BAMF_CONTEXT_TEMPORAL_MISMATCH", handle)
        if (item.frame.source_span.end > task_scope.causal_prefix_end
                or item.frame.causal_prefix_end > task_scope.causal_prefix_end
                or item.causal_prefix_end > task_scope.causal_prefix_end):
            hold("BAMF_CONTEXT_INVISIBLE_PREFIX", handle)

        expected = (
            tuple(binding.key for binding in item.frame.bindings)
            if isinstance(item.frame, FrameInstance) else (("<atomic>", 0),)
        )
        if tuple(member.key for member in item.members) != expected:
            hold("BAMF_CONTEXT_MEMBER_MISMATCH", handle)
        expected_evidence = {handle: frame_evidence_digest(item.frame)}
        for member in item.members:
            if member.key in expected:
                if member.source_handle in expected_evidence:
                    hold("BAMF_CONTEXT_HANDLE_REUSED", member.source_handle)
                else:
                    expected_evidence[member.source_handle] = member_evidence_digest(
                        item.frame, member)
            if member.visible_at_prefix > task_scope.causal_prefix_end:
                hold("BAMF_CONTEXT_INVISIBLE_PREFIX", member.source_handle)
        for source_handle in (handle, *(member.source_handle for member in item.members)):
            used_handles.add(source_handle)
            grant = grants.get(source_handle)
            if grant is None:
                hold("BAMF_CONTEXT_SOURCE_UNKNOWN", source_handle)
                continue
            if grant.evidence_digest != expected_evidence.get(source_handle):
                hold("BAMF_CONTEXT_EVIDENCE_MISMATCH", source_handle)
            if grant.semantic_release != item.semantic_release:
                hold("BAMF_CONTEXT_RELEASE_MISMATCH", source_handle)
            if grant.revoked:
                hold("BAMF_CONTEXT_SOURCE_REVOKED", source_handle)
            if (grant.principal_id != task_scope.principal_id
                    or grant.tenant_id != task_scope.tenant_id
                    or task_scope.jurisdiction not in grant.permitted_jurisdictions
                    or task_scope.scope not in grant.permitted_scopes):
                hold("BAMF_CONTEXT_SCOPE_FORBIDDEN", source_handle)
            if (task_scope.purpose is None
                    or task_scope.purpose not in grant.permitted_purposes):
                hold("BAMF_CONTEXT_PURPOSE_FORBIDDEN", source_handle)
            if grant.source_regime != item.source_regime:
                hold("BAMF_CONTEXT_SOURCE_REGIME_FORBIDDEN", source_handle)
            if grant.rights_epoch != source_frontier.rights_epoch:
                hold("BAMF_CONTEXT_RIGHTS_EPOCH_MISMATCH", source_handle)
            if grant.correction_generation != source_frontier.correction_generation:
                hold("BAMF_CONTEXT_CORRECTION_STALE", source_handle)
            if (grant.observed_at > task_scope.observed_frontier
                    or grant.effective_from > task_scope.effective_time
                    or (grant.effective_until is not None
                        and task_scope.effective_time >= grant.effective_until)):
                hold("BAMF_CONTEXT_TEMPORAL_MISMATCH", source_handle)

    join_classes = tuple(sorted({item.join_class for item in frames}))
    if len(frames) > 1:
        for index, left in enumerate(frames):
            for right in frames[index + 1:]:
                pair = tuple(sorted((left.join_class, right.join_class)))
                if pair not in policy.allowed_join_pairs:
                    hold("BAMF_CONTEXT_FORBIDDEN_JOIN", left.source_handle)
                    hold("BAMF_CONTEXT_FORBIDDEN_JOIN", right.source_handle)
    join_multiset = tuple(sorted(item.join_class for item in frames))
    if len(frames) > JOIN_PAIR_ARITY and join_multiset not in policy.allowed_join_sets:
        for item in frames:
            hold("BAMF_CONTEXT_FORBIDDEN_JOIN", item.source_handle)

    if reasons:
        return ContextHold(
            reason_codes=tuple(sorted(reasons)),
            source_handles=tuple(sorted(blocked)),
            diagnostics=tuple(sorted(diagnostics))[:MAX_CONTEXT_HOLD_DIAGNOSTICS],
        )

    approved = tuple(sorted((
        ApprovedFrame(
            frame_handle=item.frame_handle,
            source_handle=item.source_handle,
            member_handles=tuple(member.source_handle for member in item.members),
            occurrence_id=item.frame.occurrence_id,
            content_digest=item.frame.content_digest,
            join_class=item.join_class,
            envelope_digest=_digest(_envelope_projection(item)),
        )
        for item in frames
    ), key=lambda item: item.frame_handle))
    return EligibleContext(
        frames=approved,
        allowed_join_classes=join_classes,
        digest=_digest({
            "schema_version": ELIGIBLE_CONTEXT_SCHEMA,
            "task": asdict(task_scope),
            "policy": asdict(policy),
            "source_frontier": {
                "schema_version": source_frontier.schema_version,
                "rights_epoch": source_frontier.rights_epoch,
                "correction_generation": source_frontier.correction_generation,
                "grants": [
                    asdict(grants[handle]) for handle in sorted(used_handles)
                ],
            },
            "approved": [asdict(item) for item in approved],
            "allowed_join_classes": join_classes,
        }),
    )


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


@dataclass(frozen=True)
class C09ContextInvalidation:
    """Local invalidation receipt; downstream C09 owns durable outbox delivery."""
    old_context_digest: str
    new_context_digest: str | None
    reason_codes: tuple[str, ...]
    principal_id: str
    tenant_id: str
    scope: str
    semantic_release: str
    policy_epoch: int
    rights_epoch: int
    correction_generation: int
    causal_prefix_end: int
    invalidated_handles: tuple[str, ...]
    schema_version: str = C09_INVALIDATION_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.old_context_digest, str)
                or not _SHA256.fullmatch(self.old_context_digest)
                or (self.new_context_digest is not None
                    and (not isinstance(self.new_context_digest, str)
                         or not _SHA256.fullmatch(self.new_context_digest)
                         or self.new_context_digest == self.old_context_digest))
                or not _names(self.reason_codes) or not self.reason_codes
                or not all(_name(item) for item in (
                    self.principal_id, self.tenant_id, self.scope))
                or not isinstance(self.semantic_release, str)
                or not _SHA256.fullmatch(self.semantic_release)
                or not all(_epoch(item) for item in (
                    self.policy_epoch, self.rights_epoch,
                    self.correction_generation, self.causal_prefix_end))
                or not _names(self.invalidated_handles)
                or not self.invalidated_handles
                or self.schema_version != C09_INVALIDATION_SCHEMA):
            _invalid("BAMF_CONTEXT_C09_INVALIDATION_INVALID")

    @property
    def event_id(self) -> str:
        return contract_digest(self)


@dataclass(frozen=True)
class ContextTransition:
    current: ApprovedContextProjection | ContextHold
    invalidations: tuple[C09ContextInvalidation, ...]
    schema_version: str = CONTEXT_TRANSITION_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.current, (ApprovedContextProjection, ContextHold))
                or not isinstance(self.invalidations, tuple)
                or any(not isinstance(item, C09ContextInvalidation)
                       for item in self.invalidations)
                or tuple(item.event_id for item in self.invalidations)
                != tuple(sorted({item.event_id for item in self.invalidations}))
                or any(
                    item.new_context_digest != (
                        self.current.digest
                        if isinstance(self.current, ApprovedContextProjection)
                        else None)
                    for item in self.invalidations)
                or self.schema_version != CONTEXT_TRANSITION_SCHEMA):
            _invalid("BAMF_CONTEXT_TRANSITION_INVALID")

def transition_context(
    previous: ApprovedContextProjection | None,
    frames: tuple[ContextEligibility, ...],
    task_scope: TaskScope,
    source_frontier: SourceFrontier,
    policy: ContextPolicy,
) -> ContextTransition:
    """Compare pinned frontiers and emit C09 on loss/change of eligibility.

    This is a pure local transition. It never calls a policy service or
    mutates a learner, cache, source owner, outbox or external graph.
    """
    current = project_context(
        frames, task_scope, source_frontier, policy)
    if previous is None:
        return ContextTransition(current, ())
    if not isinstance(previous, ApprovedContextProjection):
        _invalid("BAMF_CONTEXT_TRANSITION_PRIOR_INVALID")
    if any(
        envelope.principal_id != task_scope.principal_id
        or envelope.tenant_id != task_scope.tenant_id
        or envelope.scope != task_scope.scope
        for envelope in previous.envelopes
    ):
        _invalid("BAMF_CONTEXT_TRANSITION_ACTOR_SCOPE_DRIFT")
    prior = previous.eligible
    new_digest = (
        current.digest if isinstance(current, ApprovedContextProjection)
        else None)
    if prior.digest == new_digest:
        return ContextTransition(current, ())
    reason_codes = (
        current.reason_codes if isinstance(current, ContextHold)
        else ("BAMF_CONTEXT_APPROVED_VIEW_CHANGED",))
    invalidation = C09ContextInvalidation(
        old_context_digest=prior.digest,
        new_context_digest=new_digest,
        reason_codes=tuple(sorted(set(reason_codes))),
        principal_id=task_scope.principal_id,
        tenant_id=task_scope.tenant_id,
        scope=task_scope.scope,
        semantic_release=task_scope.semantic_release,
        policy_epoch=policy.policy_epoch,
        rights_epoch=source_frontier.rights_epoch,
        correction_generation=source_frontier.correction_generation,
        causal_prefix_end=task_scope.causal_prefix_end,
        invalidated_handles=tuple(sorted({
            handle for frame in prior.frames
            for handle in (frame.frame_handle, *frame.member_handles)
        })),
    )
    return ContextTransition(current, (invalidation,))
