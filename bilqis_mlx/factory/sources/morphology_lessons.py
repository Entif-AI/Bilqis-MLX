"""Source-valid morphology proposals from exact source-attested laws."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.context_eligibility import (
    ContextPolicy,
    ContextHold,
    SourceFrontier,
    SourceGrant,
    TaskScope,
)

from .morphology_source import (
    MorphologySourceLaw,
    _digest,
    _fail,
    resolve_morphology_source_law,
)
from .morphology_lesson_types import (
    MorphologyAnswer,
    MorphologyConstructiveLesson,
    MorphologyDirection,
    MorphologyFact,
)


def _facts(law: MorphologySourceLaw) -> tuple[MorphologyFact, MorphologyFact]:
    compose = MorphologyFact(
        MorphologyDirection.COMPOSE,
        law.component_forms,
        MorphologyAnswer(law.semantic_release, "MORPHOLOGY_SURFACE", law.surface_form),
    )
    decompose = MorphologyFact(
        MorphologyDirection.DECOMPOSE,
        (law.surface_form,),
        MorphologyAnswer(
            law.semantic_release, "MORPHOLOGY_COMPONENTS", law.component_forms),
    )
    return compose, decompose


def _evidence(
    law: MorphologySourceLaw,
    positive: MorphologyFact,
    contrast: MorphologyFact,
) -> str:
    return _digest({
        "schema": "bilqis.morphology-lesson-evidence/v1",
        "law_sha256": law.law_sha256,
        "positive": asdict(positive),
        "source_valid_contrast": asdict(contrast),
        "constituents": law.component_ids,
    })


def construct_morphology_lesson(
    selection: AtlasArtifactSelection,
    source_bundle: str | Path,
    composition_id: str,
    direction: MorphologyDirection,
) -> MorphologyConstructiveLesson:
    """Build a source-valid proposal without inventing A13 runtime authority."""
    if type(direction) is not MorphologyDirection:
        _fail("BAMF_MORPHOLOGY_LESSON_INPUT_INVALID")
    law = resolve_morphology_source_law(selection, source_bundle, composition_id)
    compose, decompose = _facts(law)
    positive, contrast = (
        (compose, decompose) if direction is MorphologyDirection.COMPOSE
        else (decompose, compose)
    )
    return MorphologyConstructiveLesson(
        law.semantic_release, selection.bundle_id, law.composition_id, direction,
        law.law_sha256, positive, contrast, law.component_ids, law.component_ids,
        ("composition-decomposition-direction", "ordered-source-components"),
        _evidence(law, positive, contrast),
    )


def check_morphology_lesson(
    lesson: MorphologyConstructiveLesson,
    answer: MorphologyAnswer,
    selection: AtlasArtifactSelection,
    source_bundle: str | Path,
) -> bool:
    """Replay source law without trusting generator-provided gold."""
    if type(lesson) is not MorphologyConstructiveLesson:
        _fail("BAMF_MORPHOLOGY_LESSON_CHECKER_INPUT_INVALID")
    MorphologyConstructiveLesson.__post_init__(lesson)
    law = resolve_morphology_source_law(selection, source_bundle, lesson.composition_id)
    if lesson.direction is MorphologyDirection.COMPOSE:
        positive = MorphologyFact(
            MorphologyDirection.COMPOSE, law.component_forms,
            MorphologyAnswer(
                law.semantic_release, "MORPHOLOGY_SURFACE", law.surface_form))
        contrast = MorphologyFact(
            MorphologyDirection.DECOMPOSE, (law.surface_form,),
            MorphologyAnswer(
                law.semantic_release, "MORPHOLOGY_COMPONENTS", law.component_forms))
    else:
        positive = MorphologyFact(
            MorphologyDirection.DECOMPOSE, (law.surface_form,),
            MorphologyAnswer(
                law.semantic_release, "MORPHOLOGY_COMPONENTS", law.component_forms))
        contrast = MorphologyFact(
            MorphologyDirection.COMPOSE, law.component_forms,
            MorphologyAnswer(
                law.semantic_release, "MORPHOLOGY_SURFACE", law.surface_form))
    if (lesson.semantic_release != law.semantic_release
            or lesson.atlas_bundle_id != selection.bundle_id
            or lesson.source_law_sha256 != law.law_sha256
            or lesson.positive != positive
            or lesson.source_valid_contrast != contrast
            or lesson.constituents != law.component_ids
            or lesson.prerequisite_closure != law.component_ids
            or lesson.evidence_sha256 != _evidence(law, positive, contrast)):
        _fail("BAMF_MORPHOLOGY_LESSON_SOURCE_EVIDENCE_MISMATCH")
    return type(answer) is MorphologyAnswer and answer == positive.answer


def morphology_runtime_hold(
    lesson: MorphologyConstructiveLesson,
    selection: AtlasArtifactSelection,
    source_bundle: str | Path,
    task: TaskScope,
    frontier: SourceFrontier,
    policy: ContextPolicy,
) -> ContextHold:
    """Return the A13 hold until #557 supplies source-owner grant provenance."""
    if (type(task) is not TaskScope or type(frontier) is not SourceFrontier
            or type(policy) is not ContextPolicy):
        _fail("BAMF_MORPHOLOGY_LESSON_INPUT_INVALID")
    if not check_morphology_lesson(
            lesson, lesson.positive.answer, selection, source_bundle):
        _fail("BAMF_MORPHOLOGY_LESSON_SOURCE_EVIDENCE_MISMATCH")
    law = resolve_morphology_source_law(selection, source_bundle, lesson.composition_id)
    if task.semantic_release != law.semantic_release:
        return ContextHold(("BAMF_MORPHOLOGY_FOREIGN_RELEASE",), (), ())
    grants = tuple(
        item for item in frontier.grants
        if (item.evidence_digest == law.law_sha256
            and item.semantic_release == law.semantic_release
            and item.principal_id == task.principal_id
            and item.tenant_id == task.tenant_id)
    )
    if not grants:
        return ContextHold(("BAMF_MORPHOLOGY_SOURCE_GRANT_MISSING",), (), ())
    if len(grants) != 1 or type(grants[0]) is not SourceGrant:
        handles = tuple(sorted(item.source_handle for item in grants))
        return ContextHold(("BAMF_MORPHOLOGY_SOURCE_GRANT_AMBIGUOUS",), handles, ())
    grant = grants[0]
    handles = (grant.source_handle,)
    if (frontier.rights_epoch != policy.rights_epoch
            or grant.rights_epoch != frontier.rights_epoch
            or grant.correction_generation != frontier.correction_generation
            or grant.revoked or task.purpose is None
            or task.purpose not in policy.allowed_purposes
            or task.purpose not in grant.permitted_purposes
            or task.jurisdiction not in policy.allowed_jurisdictions
            or task.jurisdiction not in grant.permitted_jurisdictions
            or task.scope not in policy.allowed_scopes
            or task.scope not in grant.permitted_scopes
            or grant.source_regime not in policy.allowed_regimes
            or grant.observed_at > task.observed_frontier
            or grant.effective_from > task.effective_time
            or (grant.effective_until is not None
                and task.effective_time >= grant.effective_until)):
        return ContextHold(("BAMF_MORPHOLOGY_SOURCE_RIGHTS_HELD",), handles, ())
    return ContextHold(
        ("BAMF_MORPHOLOGY_A13_SOURCE_ISSUER_UNAVAILABLE",), handles,
        (("missing", "source-owned-span-grant-projection"),
         ("owner", "A08.1b.5#557")),
    )
