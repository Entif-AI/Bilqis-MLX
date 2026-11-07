"""Source-owned A13 contexts for A08 constructive source facts."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from bilqis_mlx.semantics.atlas.snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
)
from bilqis_mlx.semantics.context_eligibility import (
    ApprovedContextProjection, ContextHold, ContextPolicy, SourceFrontier,
    SourceGrant, TaskScope, project_context,
)
from bilqis_mlx.semantics.frame_adapters.source_rows import (
    SourceRowContext, _source_row_context,
)
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.source_owner.row_witness import source_row_byte_witness

from .checkers import assert_source_lesson_set_current
from .common import LEARNING_UNVERIFIED, _fail
from .lesson_types import SourceConstructiveLesson, SourceConstructiveLessonSet
from .source_context_policy import SourceContextPolicyWindow


SOURCE_CONTEXT_SCHEMA = "bilqis.source-lesson-context/v1"
_CANONICAL_SOURCE_ROOT = Path(__file__).resolve().parents[3] / "lib/ithkuil/_data/csv"
_SOURCE_FACT_ARITY = 3
_SOURCE_FACT_SPLIT_LIMIT = 2
_SOURCE_FACT_REFERENCE_INDEX = 2

@dataclass(frozen=True)
class SourceLessonContexts:
    """Positive and contrast source facts plus source-owner grants."""

    semantic_release: str
    positive: SourceRowContext
    contrast: SourceRowContext
    grants: tuple[SourceGrant, ...]
    validity: SourceContextPolicyWindow | None = None
    learning_state: str = LEARNING_UNVERIFIED
    schema: str = SOURCE_CONTEXT_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.positive) is not SourceRowContext
                or type(self.contrast) is not SourceRowContext
                or self.positive.envelope.semantic_release != self.semantic_release
                or self.contrast.envelope.semantic_release != self.semantic_release
                or self.positive.a01_source_bundle_id
                   != self.contrast.a01_source_bundle_id
                or not isinstance(self.grants, tuple)
                or len({item.source_handle for item in self.grants}) != len(self.grants)
                or (self.validity is not None
                    and type(self.validity) is not SourceContextPolicyWindow)
                or self.learning_state != LEARNING_UNVERIFIED
                or self.schema != SOURCE_CONTEXT_SCHEMA):
            _fail("BAMF_SOURCE_LESSON_CONTEXT_INVALID")
        if self.validity is not None:
            self.validity.__post_init__()
            envelopes = (self.positive.envelope, self.contrast.envelope)
            if (self.semantic_release != self.validity.semantic_release
                    or self.positive.a01_source_bundle_id
                       != self.validity.source_bundle_id
                    or any(item.principal_id != self.validity.principal_id
                    or item.tenant_id != self.validity.tenant_id
                    or item.purpose != self.validity.purpose
                    or item.jurisdiction != self.validity.jurisdiction
                    or item.scope != self.validity.scope
                    or item.policy_epoch != self.validity.policy_epoch
                    or item.rights_epoch != self.validity.rights_epoch
                    or item.correction_generation != self.validity.correction_generation
                    or item.observed_at != self.validity.observed_at
                    or item.effective_from != self.validity.effective_from
                    or item.effective_until != self.validity.effective_until
                    for item in envelopes)
                    or any(item.observed_at != self.validity.observed_at
                           or item.effective_from != self.validity.effective_from
                           or item.effective_until != self.validity.effective_until
                           for item in self.grants)):
                _fail("BAMF_SOURCE_LESSON_CONTEXT_VALIDITY_DRIFT")


def _source_fact_context(
    fact: tuple[str, ...], atlas: AtlasArtifactSelection, task: TaskScope,
    policy: ContextPolicy, *, rights_epoch: int, correction_generation: int,
    observed_at: int | None = None, effective_from: int = 0,
    effective_until: int | None = None,
) -> SourceRowContext:
    if (type(fact) is not tuple or len(fact) != _SOURCE_FACT_ARITY or fact[0] != "identity"
            or fact[_SOURCE_FACT_REFERENCE_INDEX].startswith("abi:")):
        _fail("BAMF_SOURCE_LESSON_ROW_PROVENANCE_UNAVAILABLE")
    try:
        domain, table, key = fact[_SOURCE_FACT_REFERENCE_INDEX].split(
            "/", _SOURCE_FACT_SPLIT_LIMIT)
        snapshot = load_pinned_atlas_snapshot(atlas)
        concept = next((item.concept for item in snapshot.concepts
                        if item.concept.semantic_id == fact[1]), None)
        if (concept is None or not any(
                (ref.domain, ref.table, ref.key) == (domain, table, key)
                for ref in concept.source_rows)):
            _fail("BAMF_SOURCE_LESSON_A01_SOURCE_IDENTITY_MISMATCH")
        witness = source_row_byte_witness(
            _CANONICAL_SOURCE_ROOT, domain, table, key)
        return _source_row_context(
            witness, semantic_release=task.semantic_release, semantic_id=fact[1],
            a01_source_bundle_id=snapshot.source_bundle_id,
            principal_id=task.principal_id, tenant_id=task.tenant_id,
            purpose=task.purpose or "<none>", jurisdiction=task.jurisdiction,
            scope=task.scope, policy_epoch=policy.policy_epoch,
            rights_epoch=rights_epoch, correction_generation=correction_generation,
            observed_at=(task.observed_frontier
                         if observed_at is None else observed_at),
            effective_from=effective_from, effective_until=effective_until,
            causal_prefix_end=task.causal_prefix_end)
    except (ValueError, OSError, ProfileError):
        _fail("BAMF_SOURCE_LESSON_ROW_PROVENANCE_INVALID")


def issue_source_lesson_contexts(
    lesson: SourceConstructiveLesson, lessons: SourceConstructiveLessonSet,
    atlas: AtlasArtifactSelection, task: TaskScope, policy: ContextPolicy,
    frontier: SourceFrontier,
    *, validity: SourceContextPolicyWindow | None = None,
) -> tuple[SourceLessonContexts, SourceFrontier]:
    """Replay A01 lesson authority before issuing exact frame/member grants."""
    assert_source_lesson_set_current(lessons, atlas)
    if (type(lesson) is not SourceConstructiveLesson
            or lesson not in lessons.lessons
            or lesson.family_id != "positive_identity"
            or task.semantic_release != lesson.semantic_release
            or type(frontier) is not SourceFrontier
            or policy.rights_epoch != frontier.rights_epoch):
        _fail("BAMF_SOURCE_LESSON_CONTEXT_INPUT_INVALID")
    observed_at = task.observed_frontier
    effective_from = 0
    effective_until = None
    if validity is not None:
        validity.__post_init__()
        if (validity.atlas_bundle_id != atlas.bundle_id
                or validity.semantic_release != atlas.release_sha256
                or validity.source_bundle_id != atlas.source_bundle_id
                or validity.principal_id != task.principal_id
                or validity.tenant_id != task.tenant_id
                or validity.purpose != task.purpose
                or validity.jurisdiction != task.jurisdiction
                or validity.scope != task.scope
                or validity.policy_id != policy.policy_id
                or validity.policy_epoch != policy.policy_epoch
                or validity.rights_epoch != policy.rights_epoch
                or validity.rights_epoch != frontier.rights_epoch
                or validity.correction_generation != frontier.correction_generation
                or validity.observed_at > task.observed_frontier
                or not validity.effective_from <= task.effective_time
                < validity.effective_until):
            _fail("BAMF_SOURCE_CONTEXT_POLICY_WINDOW_AUTHORITY_MISMATCH")
        observed_at = validity.observed_at
        effective_from = validity.effective_from
        effective_until = validity.effective_until
    positive = _source_fact_context(
        lesson.positive_fact, atlas, task, policy,
        rights_epoch=frontier.rights_epoch,
        correction_generation=frontier.correction_generation,
        observed_at=observed_at, effective_from=effective_from,
        effective_until=effective_until)
    contrast = _source_fact_context(
        lesson.contrast_fact, atlas, task, policy,
        rights_epoch=frontier.rights_epoch,
        correction_generation=frontier.correction_generation,
        observed_at=observed_at, effective_from=effective_from,
        effective_until=effective_until)
    by_handle = {}
    for grant in (*positive.grants, *contrast.grants):
        prior = by_handle.get(grant.source_handle)
        if prior is not None and prior != grant:
            _fail("BAMF_SOURCE_LESSON_GRANT_COLLISION")
        by_handle[grant.source_handle] = grant
    issued = SourceLessonContexts(
        lesson.semantic_release, positive, contrast,
        tuple(sorted(by_handle.values(), key=lambda item: item.source_handle)),
        validity)
    return issued, _merge_issued_grants(frontier, issued.grants)


def source_lesson_expiry_task(
    contexts: SourceLessonContexts, task: TaskScope,
    frontier: SourceFrontier, policy: ContextPolicy,
) -> TaskScope:
    """Cross exactly the declared finite boundary; never infer expiry from time."""
    if (type(contexts) is not SourceLessonContexts
            or type(task) is not TaskScope
            or type(frontier) is not SourceFrontier
            or type(policy) is not ContextPolicy
            or contexts.validity is None):
        _fail("BAMF_SOURCE_CONTEXT_POLICY_WINDOW_REQUIRED")
    contexts.__post_init__()
    validity = contexts.validity
    if (validity.semantic_release != task.semantic_release
            or validity.principal_id != task.principal_id
            or validity.tenant_id != task.tenant_id
            or validity.purpose != task.purpose
            or validity.jurisdiction != task.jurisdiction
            or validity.scope != task.scope
            or validity.policy_id != policy.policy_id
            or validity.policy_epoch != policy.policy_epoch
            or validity.rights_epoch != policy.rights_epoch
            or validity.rights_epoch != frontier.rights_epoch
            or validity.correction_generation != frontier.correction_generation
            or task.observed_frontier < validity.observed_at
            or not validity.effective_from <= task.effective_time
            < validity.effective_until):
        _fail("BAMF_SOURCE_CONTEXT_POLICY_WINDOW_AUTHORITY_MISMATCH")
    return replace(task, effective_time=validity.effective_until)


def _merge_issued_grants(
    frontier: SourceFrontier, grants: tuple[SourceGrant, ...],
) -> SourceFrontier:
    """Preserve current revocation/correction truth while adding new source grants."""
    merged = {item.source_handle: item for item in frontier.grants}
    for grant in grants:
        prior = merged.get(grant.source_handle)
        if prior is not None and prior != grant:
            _fail("BAMF_SOURCE_LESSON_GRANT_COLLISION")
        merged[grant.source_handle] = grant
    return SourceFrontier(
        frontier.rights_epoch, frontier.correction_generation,
        tuple(sorted(merged.values(), key=lambda item: item.source_handle)))


def project_source_lesson_contexts(
    contexts: SourceLessonContexts, task: TaskScope,
    frontier: SourceFrontier, policy: ContextPolicy,
) -> ApprovedContextProjection | ContextHold:
    """Apply current A13 state without regenerating revoked or missing grants."""
    SourceLessonContexts.__post_init__(contexts)
    if task.semantic_release != contexts.semantic_release:
        _fail("BAMF_SOURCE_LESSON_CONTEXT_RELEASE_MISMATCH")
    return project_context(
        (contexts.positive.envelope, contexts.contrast.envelope),
        task, frontier, policy)
