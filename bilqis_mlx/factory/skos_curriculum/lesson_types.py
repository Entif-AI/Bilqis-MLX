"""Typed source-fact lesson proposals, never learner credit."""
from __future__ import annotations
from dataclasses import dataclass
from .common import (LEARNING_UNVERIFIED, SOURCE_PROJECTION_ONLY,
    SOURCE_LESSON_SCHEMA, SOURCE_LESSON_SET_SCHEMA, _SHA, _fail)
from .types import FamilyObligation

@dataclass(frozen=True)
class SourceConstructiveLesson:
    """An exact source-fact teaching contrast, not a learner credit receipt."""

    semantic_release: str
    semantic_id: str
    family_id: str
    source_evidence_sha256: str
    positive_fact: tuple[str, ...]
    contrast_fact: tuple[str, ...]
    answer_modality: str
    checker_reference: str
    constituents: tuple[str, ...]
    prerequisite_closure: tuple[str, ...]
    variation_axes: tuple[str, ...]
    learning_state: str = LEARNING_UNVERIFIED
    source_authority: str = SOURCE_PROJECTION_ONLY
    schema: str = SOURCE_LESSON_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.semantic_release) is not str
                or not _SHA.fullmatch(self.semantic_release)
                or type(self.source_evidence_sha256) is not str
                or not _SHA.fullmatch(self.source_evidence_sha256)
                or type(self.semantic_id) is not str or not self.semantic_id
                or type(self.family_id) is not str or not self.family_id
                or type(self.positive_fact) is not tuple
                or type(self.contrast_fact) is not tuple
                or not self.positive_fact or not self.contrast_fact
                or any(type(item) is not str
                       for item in (*self.positive_fact, *self.contrast_fact))
                or self.positive_fact == self.contrast_fact
                or type(self.answer_modality) is not str
                or self.answer_modality not in {
                    "SEMANTIC_ID", "RELATION_TRIPLE"}
                or type(self.checker_reference) is not str
                or not self.checker_reference
                or type(self.constituents) is not tuple
                or any(type(item) is not str for item in self.constituents)
                or type(self.prerequisite_closure) is not tuple
                or any(type(item) is not str for item in self.prerequisite_closure)
                or type(self.variation_axes) is not tuple
                or any(type(item) is not str for item in self.variation_axes)
                or not self.variation_axes
                or type(self.learning_state) is not str
                or self.learning_state != LEARNING_UNVERIFIED
                or type(self.source_authority) is not str
                or self.source_authority != SOURCE_PROJECTION_ONLY
                or type(self.schema) is not str
                or self.schema != SOURCE_LESSON_SCHEMA):
            _fail("BAMF_LESSON_RECORD_INVALID")


@dataclass(frozen=True)
class SourceConstructiveLessonSet:
    semantic_release: str
    census_digest: str
    lessons: tuple[SourceConstructiveLesson, ...]
    uncovered: tuple[FamilyObligation, ...]
    learning_state: str = LEARNING_UNVERIFIED
    source_authority: str = SOURCE_PROJECTION_ONLY
    schema: str = SOURCE_LESSON_SET_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.lessons, tuple)
                or any(not isinstance(item, SourceConstructiveLesson)
                       for item in self.lessons)):
            _fail("BAMF_LESSON_SET_INVALID")
        keys = tuple(
            (item.semantic_id, item.family_id) for item in self.lessons)
        if (not isinstance(self.semantic_release, str)
                or not _SHA.fullmatch(self.semantic_release)
                or not isinstance(self.census_digest, str)
                or not _SHA.fullmatch(self.census_digest)
                or not isinstance(self.uncovered, tuple)
                or any(item.semantic_release != self.semantic_release
                       for item in self.lessons)
                or any(not isinstance(item, FamilyObligation)
                       for item in self.uncovered)
                or len(set(keys)) != len(keys)
                or self.learning_state != LEARNING_UNVERIFIED
                or self.source_authority != SOURCE_PROJECTION_ONLY
                or self.schema != SOURCE_LESSON_SET_SCHEMA):
            _fail("BAMF_LESSON_SET_INVALID")
