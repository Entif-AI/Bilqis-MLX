"""Independent source replay and exact constructive lesson checking."""
from __future__ import annotations
from bilqis_mlx.semantics.atlas_projection import FrozenAtlasSnapshot
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from .common import (_fail, _load_pinned, _SEMANTIC_RELATIONS, SOURCE_FACT_ARITY,
    SOURCE_FACT_PREFIX_ARITY, SOURCE_FACT_REF_INDEX)
from .inventory import _inventory_source_families
from .lesson_compiler import (_compile_source_constructive_lessons_snapshot,
    _source_lesson_evidence)
from .lesson_types import SourceConstructiveLesson, SourceConstructiveLessonSet
from .serialization import _strict_source_bytes
from .types import SemanticFamilyInventory

def compile_source_constructive_lessons(
    atlas: AtlasArtifactSelection,
    *, census: SemanticFamilyInventory | None = None,
) -> SourceConstructiveLessonSet:
    return _compile_source_constructive_lessons_snapshot(
        _load_pinned(atlas), census=census)


def assert_source_lesson_set_current(
    lessons: SourceConstructiveLessonSet,
    atlas: AtlasArtifactSelection,
) -> None:
    """Reconstruct source lessons at the consuming boundary, never trust a tag."""
    if (type(lessons) is not SourceConstructiveLessonSet
            or _strict_source_bytes(lessons)
            != _strict_source_bytes(compile_source_constructive_lessons(atlas))):
        _fail("BAMF_LESSON_SOURCE_PROJECTION_DRIFT")


def _check_source_constructive_lesson_snapshot(
    lesson: SourceConstructiveLesson, answer: object,
    atlas: FrozenAtlasSnapshot,
) -> bool:
    """Check against A01 source facts without consulting the lesson generator."""
    if type(lesson) is not SourceConstructiveLesson:
        _fail("BAMF_LESSON_CHECKER_INPUT_INVALID")
    _strict_source_bytes(lesson)
    census = _inventory_source_families(atlas)
    matching = tuple(
        item for item in census.obligations
        if (item.semantic_id, item.family_id)
        == (lesson.semantic_id, lesson.family_id))
    if (lesson.semantic_release != atlas.release_sha256
            or len(matching) != 1
            or lesson.source_evidence_sha256 != _source_lesson_evidence(
                matching[0], lesson.positive_fact, lesson.contrast_fact)):
        _fail("BAMF_LESSON_SOURCE_EVIDENCE_MISMATCH")
    by_id = {item.semantic_id: item for item in census.concepts}
    if lesson.family_id == "positive_identity":
        positive, contrast = lesson.positive_fact, lesson.contrast_fact
        other = by_id.get(contrast[1]) if len(contrast) == SOURCE_FACT_ARITY else None
        if (lesson.answer_modality != "SEMANTIC_ID"
                or lesson.checker_reference != "bilqis.source-checker.identity/v1"
                or len(positive) != SOURCE_FACT_ARITY
                or positive[:SOURCE_FACT_PREFIX_ARITY] != (
                    "identity", lesson.semantic_id)
                or positive[SOURCE_FACT_REF_INDEX]
                not in by_id[lesson.semantic_id].source_refs
                or other is None or contrast[0] != "identity"
                or contrast[1] == lesson.semantic_id
                or contrast[SOURCE_FACT_REF_INDEX] not in other.source_refs
                or lesson.constituents != (lesson.semantic_id,)
                or lesson.prerequisite_closure != ()
                or lesson.variation_axes != (
                    "source-identity", "source-contrast")):
            _fail("BAMF_LESSON_SOURCE_EVIDENCE_MISMATCH")
        return (type(answer) is str
                and answer.encode("utf-8")
                == lesson.semantic_id.encode("utf-8"))
    if lesson.family_id == "source_attested_relation":
        if any(len(fact) != SOURCE_FACT_ARITY
               or any(type(part) is not str for part in fact)
               for fact in (lesson.positive_fact, lesson.contrast_fact)):
            _fail("BAMF_LESSON_SOURCE_EVIDENCE_MISMATCH")
        eligible = set(census.source_eligible_concept_ids)
        attested = {
            (edge.source_semantic_id, edge.predicate, edge.target_semantic_id)
            for edge in atlas.relations
            if edge.source_semantic_id in eligible
            and edge.target_semantic_id in eligible
            and edge.predicate in _SEMANTIC_RELATIONS}
        positive, contrast = lesson.positive_fact, lesson.contrast_fact
        constituents = tuple(dict.fromkeys((
            positive[0], positive[2], contrast[0], contrast[2])))
        if (lesson.answer_modality != "RELATION_TRIPLE"
                or lesson.checker_reference
                != "bilqis.source-checker.attested-relation/v1"
                or positive not in attested or contrast not in attested
                or positive[0] != lesson.semantic_id
                or contrast[0] == lesson.semantic_id
                or lesson.constituents != constituents
                or lesson.prerequisite_closure != constituents
                or lesson.variation_axes != (
                    "source-relation", "source-contrast")):
            _fail("BAMF_LESSON_SOURCE_EVIDENCE_MISMATCH")
        return (type(answer) is tuple
                and all(type(item) is str for item in answer)
                and _strict_source_bytes(answer)
                == _strict_source_bytes(positive))
    _fail("BAMF_LESSON_CHECKER_UNSUPPORTED")


def check_source_constructive_lesson(
    lesson: SourceConstructiveLesson, answer: object,
    atlas: AtlasArtifactSelection,
) -> bool:
    return _check_source_constructive_lesson_snapshot(
        lesson, answer, _load_pinned(atlas))
