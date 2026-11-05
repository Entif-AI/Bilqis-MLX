"""Immutable generated-artifact models for BAMF semantic contrasts."""
from __future__ import annotations

from dataclasses import dataclass
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.frame_schema import RoleOccurrence
from bilqis_mlx.factory.semantic_contrast_types import AllowedVariation, ContrastFamily, ContrastSourceFrame, ObservationState, TemporalStatus

_SHA = re.compile(r"[0-9a-f]{64}\\Z")
SCHEMA = "bilqis.semantic-contrast-lesson/v1"
LINEAGE_SCHEMA = "bilqis.semantic-contrast-lineage/v1"
VARIANT_SCHEMA = "bilqis.semantic-contrast-variant/v1"
CHECKER = "bilqis.semantic-contrast-checker/v1"


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _text(value: object) -> bool:
    return type(value) is str and bool(value)


@dataclass(frozen=True)
class ContrastVariant:
    source_occurrence_id: str
    source_content_digest: str
    bindings: tuple[RoleOccurrence, ...]
    scope: str
    negated: bool
    status: TemporalStatus
    observation_state: ObservationState
    morphology: str
    schema: str = VARIANT_SCHEMA

    def __post_init__(self) -> None:
        keys = tuple(item.key for item in self.bindings)
        if (not _SHA.fullmatch(self.source_occurrence_id)
                or not _SHA.fullmatch(self.source_content_digest)
                or type(self.bindings) is not tuple
                or any(type(item) is not RoleOccurrence for item in self.bindings)
                or len(keys) != len(set(keys))
                or not _text(self.scope)
                or type(self.negated) is not bool
                or type(self.status) is not TemporalStatus
                or type(self.observation_state) is not ObservationState
                or not _text(self.morphology)
                or self.schema != VARIANT_SCHEMA):
            _fail("BAMF_SEMANTIC_CONTRAST_VARIANT_INVALID")

    def binding(self, role_id: str, occurrence_index: int) -> RoleOccurrence:
        matches = tuple(item for item in self.bindings
                        if item.role_id == role_id and item.occurrence_index == occurrence_index)
        if len(matches) != 1:
            _fail("BAMF_SEMANTIC_CONTRAST_BINDING_MISSING")
        return matches[0]

    def structural_payload(self) -> dict:
        return {
            "source_occurrence_id": self.source_occurrence_id,
            "source_content_digest": self.source_content_digest,
            "bindings": [item.content_identity() for item in self.bindings],
            "scope": self.scope,
            "negated": self.negated,
            "status": self.status.value,
            "observation_state": self.observation_state.value,
            "morphology": self.morphology,
        }


@dataclass(frozen=True)
class ContrastLineage:
    source_occurrence_id: str
    source_content_digest: str
    source_instance_id: str
    family: ContrastFamily
    mutation_digest: str
    variant_id: str
    checker_revision: str
    schema: str = LINEAGE_SCHEMA

    def __post_init__(self) -> None:
        if (not _SHA.fullmatch(self.source_occurrence_id)
                or not _SHA.fullmatch(self.source_content_digest)
                or not _text(self.source_instance_id)
                or type(self.family) is not ContrastFamily
                or not _SHA.fullmatch(self.mutation_digest)
                or not _SHA.fullmatch(self.variant_id)
                or not _text(self.checker_revision)
                or self.schema != LINEAGE_SCHEMA):
            _fail("BAMF_SEMANTIC_CONTRAST_LINEAGE_INVALID")


@dataclass(frozen=True)
class LessonSpec:
    family: ContrastFamily
    source: ContrastSourceFrame
    variation: AllowedVariation
    variant: ContrastVariant
    lineage: ContrastLineage
    applicability: str
    question: str
    expected_answer: str
    checker_id: str = CHECKER
    schema: str = SCHEMA

    def __post_init__(self) -> None:
        if (type(self.family) is not ContrastFamily
                or type(self.source) is not ContrastSourceFrame
                or type(self.variation) is not AllowedVariation
                or self.variation.family is not self.family
                or type(self.variant) is not ContrastVariant
                or type(self.lineage) is not ContrastLineage
                or self.lineage.family is not self.family
                or not _text(self.applicability)
                or not _text(self.question)
                or not _text(self.expected_answer)
                or self.checker_id != CHECKER
                or self.schema != SCHEMA):
            _fail("BAMF_SEMANTIC_CONTRAST_LESSON_INVALID")


