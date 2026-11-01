"""Source-owned A13 contexts for A08 constructive source facts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bilqis_mlx.semantics.atlas_snapshot import (
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
                or self.learning_state != LEARNING_UNVERIFIED
                or self.schema != SOURCE_CONTEXT_SCHEMA):
            _fail("BAMF_SOURCE_LESSON_CONTEXT_INVALID")


def _source_fact_context(
    fact: tuple[str, ...], atlas: AtlasArtifactSelection, task: TaskScope,
    policy: ContextPolicy, *, rights_epoch: int, correction_generation: int,
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
            observed_at=task.observed_frontier, effective_from=0,
            causal_prefix_end=task.causal_prefix_end)
    except (ValueError, OSError, ProfileError):
        _fail("BAMF_SOURCE_LESSON_ROW_PROVENANCE_INVALID")


def issue_source_lesson_contexts(
    lesson: SourceConstructiveLesson, lessons: SourceConstructiveLessonSet,
    atlas: AtlasArtifactSelection, task: TaskScope, policy: ContextPolicy,
    frontier: SourceFrontier,
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
    positive = _source_fact_context(
        lesson.positive_fact, atlas, task, policy,
        rights_epoch=frontier.rights_epoch,
        correction_generation=frontier.correction_generation)
    contrast = _source_fact_context(
        lesson.contrast_fact, atlas, task, policy,
        rights_epoch=frontier.rights_epoch,
        correction_generation=frontier.correction_generation)
    by_handle = {}
    for grant in (*positive.grants, *contrast.grants):
        prior = by_handle.get(grant.source_handle)
        if prior is not None and prior != grant:
            _fail("BAMF_SOURCE_LESSON_GRANT_COLLISION")
        by_handle[grant.source_handle] = grant
    issued = SourceLessonContexts(
        lesson.semantic_release, positive, contrast,
        tuple(sorted(by_handle.values(), key=lambda item: item.source_handle)))
    return issued, _merge_issued_grants(frontier, issued.grants)


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
