"""Source-only constructive facts and held family obligations."""
from __future__ import annotations
from bilqis_mlx.semantics.atlas_projection import FrozenAtlasSnapshot
from .common import _digest, _fail, _SEMANTIC_RELATIONS
from .inventory import _inventory_source_families
from .lesson_types import SourceConstructiveLesson, SourceConstructiveLessonSet
from .serialization import _strict_source_bytes
from .types import FamilyObligation, SemanticFamilyInventory

def _source_lesson_evidence(
    obligation: FamilyObligation,
    positive: tuple[str, ...],
    contrast: tuple[str, ...],
) -> str:
    """Bind each source fact to its A01 family obligation."""
    return _digest({
        "schema": "bilqis.source-lesson-evidence/v1",
        "obligation_sha256": obligation.source_evidence_sha256,
        "positive_fact": positive,
        "contrast_fact": contrast,
    })


def _ordered_other(
    ordered: tuple[str, ...],
    position: int,
    own_index: int,
) -> str:
    """Select from one ordered set with a known member removed."""
    width = len(ordered) - 1
    if width < 1:
        _fail("BAMF_SOURCE_LESSON_CONTRAST_POOL_EXHAUSTED")
    selected = position % width
    if selected >= own_index:
        selected += 1
    return ordered[selected]


def _compile_source_constructive_lessons_from_census(
    atlas: FrozenAtlasSnapshot,
    census: SemanticFamilyInventory,
) -> SourceConstructiveLessonSet:
    """Compile lessons from a census already derived by the current owner call."""
    if type(census) is not SemanticFamilyInventory:
        _fail("BAMF_LESSON_CENSUS_DRIFT")
    by_id = {item.semantic_id: item for item in census.concepts}
    eligible = census.source_eligible_concept_ids
    position = {identifier: index for index, identifier in enumerate(eligible)}
    authority_groups = {False: [], True: []}
    authority_index = {}
    for identifier in eligible:
        source_refs = by_id[identifier].source_refs
        authority = bool(source_refs and source_refs[0].startswith("abi:"))
        authority_index[identifier] = len(authority_groups[authority])
        authority_groups[authority].append(identifier)
    authority_groups = {
        key: tuple(value) for key, value in authority_groups.items()
    }
    relations = tuple(sorted(
        (edge.source_semantic_id, edge.predicate, edge.target_semantic_id)
        for edge in atlas.relations
        if edge.source_semantic_id in by_id
        and edge.target_semantic_id in by_id
        and edge.predicate in _SEMANTIC_RELATIONS))
    relations_by_source: dict[str, tuple[str, str, str]] = {}
    for triple in relations:
        relations_by_source.setdefault(triple[0], triple)
    first_relation = relations[0] if relations else None
    first_other_relation = (
        next((item for item in relations if item[0] != first_relation[0]), None)
        if first_relation is not None else None
    )
    lessons = []
    uncovered = []
    for obligation in census.obligations:
        semantic_id = obligation.semantic_id
        family = obligation.family_id
        if family == "positive_identity" and len(eligible) > 1:
            source_ref = by_id[semantic_id].source_refs[0]
            authority = source_ref.startswith("abi:")
            group = authority_groups[authority]
            if len(group) > 1:
                contrast_id = _ordered_other(
                    group, position[semantic_id], authority_index[semantic_id])
            else:
                contrast_id = _ordered_other(
                    eligible, position[semantic_id], position[semantic_id])
            positive = ("identity", semantic_id, source_ref)
            contrast = ("identity", contrast_id, by_id[contrast_id].source_refs[0])
            modality = "SEMANTIC_ID"
            checker = "bilqis.source-checker.identity/v1"
            constituents = (semantic_id,)
            prerequisites = ()
            axes = ("source-identity", "source-contrast")
        elif family == "source_attested_relation" and len(relations) > 1:
            positive = relations_by_source.get(semantic_id)
            if positive is None:
                uncovered.append(obligation)
                continue
            contrast = (
                first_relation
                if first_relation is not None and first_relation[0] != semantic_id
                else first_other_relation
            )
            if contrast is None:
                uncovered.append(obligation)
                continue
            modality = "RELATION_TRIPLE"
            checker = "bilqis.source-checker.attested-relation/v1"
            constituents = tuple(dict.fromkeys((
                positive[0], positive[2], contrast[0], contrast[2])))
            prerequisites = constituents
            axes = ("source-relation", "source-contrast")
        else:
            uncovered.append(obligation)
            continue
        lessons.append(SourceConstructiveLesson(
            atlas.release_sha256, semantic_id, family,
            _source_lesson_evidence(
                obligation, tuple(positive), tuple(contrast)),
            tuple(positive), tuple(contrast), modality, checker,
            constituents, prerequisites, axes))
    return SourceConstructiveLessonSet(
        atlas.release_sha256, census.digest, tuple(lessons),
        tuple(uncovered), tuple(census.source_held))


def _compile_source_constructive_lessons_snapshot(
    atlas: FrozenAtlasSnapshot,
    *, census: SemanticFamilyInventory | None = None,
) -> SourceConstructiveLessonSet:
    """Compile only facts provable from A01; other families remain debt."""
    authoritative = _inventory_source_families(atlas)
    if (census is not None
            and (type(census) is not SemanticFamilyInventory
                 or _strict_source_bytes(census)
                 != _strict_source_bytes(authoritative))):
        _fail("BAMF_LESSON_CENSUS_DRIFT")
    return _compile_source_constructive_lessons_from_census(
        atlas, authoritative)
