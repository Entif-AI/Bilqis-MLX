"""Immutable task-scoped morphology lesson records."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .morphology_source import _fail


LESSON_SCHEMA = "bilqis.morphology-constructive-lesson-proposal/v1"
ANSWER_SCHEMA = "bilqis.morphology-typed-answer/v1"
FACT_SCHEMA = "bilqis.morphology-source-fact/v1"
SOURCE_VALID_NOT_ADMITTED = "SOURCE_VALID_NOT_ADMITTED"
SOURCE_PROJECTION_ONLY = "SOURCE_PROJECTION_NOT_AUTHORITY"
A13_RIGHTS_UNVERIFIED = "A13_RIGHTS_UNVERIFIED"
LEARNING_UNVERIFIED = "LEARNING_UNVERIFIED"


def _hex64(value: object) -> bool:
    return (type(value) is str and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


class MorphologyDirection(str, Enum):
    COMPOSE = "COMPOSE"
    DECOMPOSE = "DECOMPOSE"


@dataclass(frozen=True)
class MorphologyAnswer:
    semantic_release: str
    modality: str
    value: str | tuple[str, ...]
    schema: str = ANSWER_SCHEMA

    def __post_init__(self) -> None:
        surface = self.modality == "MORPHOLOGY_SURFACE" and type(self.value) is str
        components = (
            self.modality == "MORPHOLOGY_COMPONENTS"
            and type(self.value) is tuple
            and len(self.value) >= 2
            and all(type(item) is str and item for item in self.value)
        )
        if (not _hex64(self.semantic_release)
                or not (surface or components)
                or not self.value
                or self.schema != ANSWER_SCHEMA):
            _fail("BAMF_MORPHOLOGY_ANSWER_INVALID")


@dataclass(frozen=True)
class MorphologyFact:
    direction: MorphologyDirection
    inputs: tuple[str, ...]
    answer: MorphologyAnswer
    schema: str = FACT_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.direction) is not MorphologyDirection
                or type(self.inputs) is not tuple
                or any(type(item) is not str or not item for item in self.inputs)
                or type(self.answer) is not MorphologyAnswer
                or self.schema != FACT_SCHEMA):
            _fail("BAMF_MORPHOLOGY_FACT_INVALID")
        if self.direction is MorphologyDirection.COMPOSE:
            valid = len(self.inputs) >= 2 and self.answer.modality == "MORPHOLOGY_SURFACE"
        else:
            valid = len(self.inputs) == 1 and self.answer.modality == "MORPHOLOGY_COMPONENTS"
        if not valid:
            _fail("BAMF_MORPHOLOGY_FACT_INVALID")


@dataclass(frozen=True)
class MorphologyConstructiveLesson:
    semantic_release: str
    atlas_bundle_id: str
    composition_id: str
    direction: MorphologyDirection
    source_law_sha256: str
    positive: MorphologyFact
    source_valid_contrast: MorphologyFact
    constituents: tuple[str, ...]
    prerequisite_closure: tuple[str, ...]
    variation_axes: tuple[str, ...]
    evidence_sha256: str
    status: str = SOURCE_VALID_NOT_ADMITTED
    source_authority: str = SOURCE_PROJECTION_ONLY
    runtime_rights: str = A13_RIGHTS_UNVERIFIED
    learning_state: str = LEARNING_UNVERIFIED
    schema: str = LESSON_SCHEMA

    def __post_init__(self) -> None:
        hashes = (self.source_law_sha256, self.evidence_sha256)
        if (not _hex64(self.semantic_release)
                or not _hex64(self.atlas_bundle_id)
                or type(self.composition_id) is not str or not self.composition_id
                or type(self.direction) is not MorphologyDirection
                or any(not _hex64(item) for item in hashes)
                or type(self.positive) is not MorphologyFact
                or type(self.source_valid_contrast) is not MorphologyFact
                or self.positive.direction is not self.direction
                or self.source_valid_contrast.direction is self.direction
                or not self.constituents
                or any(type(item) is not str or not item for item in self.constituents)
                or self.prerequisite_closure != self.constituents
                or self.positive.answer.semantic_release != self.semantic_release
                or self.source_valid_contrast.answer.semantic_release
                != self.semantic_release
                or self.variation_axes != (
                    "composition-decomposition-direction", "ordered-source-components")
                or self.status != SOURCE_VALID_NOT_ADMITTED
                or self.source_authority != SOURCE_PROJECTION_ONLY
                or self.runtime_rights != A13_RIGHTS_UNVERIFIED
                or self.learning_state != LEARNING_UNVERIFIED
                or self.schema != LESSON_SCHEMA):
            _fail("BAMF_MORPHOLOGY_LESSON_INVALID")
