"""Public enums and variation contracts for BAMF semantic contrasts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.frame_schema import BindingState, ConceptRef, FrameInstance, FrameSchema

_SHA = re.compile(r"[0-9a-f]{64}\\Z")


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _text(value: object) -> bool:
    return type(value) is str and bool(value)


class ContrastFamily(str, Enum):
    ROLE_SWAP = "ROLE_SWAP"
    CARDINALITY_CHANGE = "CARDINALITY_CHANGE"
    SCOPE_NEGATION = "SCOPE_NEGATION"
    KNOWN_UNKNOWN = "KNOWN_UNKNOWN"
    PLANNED_OCCURRED = "PLANNED_OCCURRED"
    MISSING_NEGATIVE = "MISSING_NEGATIVE"
    MORPHOLOGY_ALTERNATIVE = "MORPHOLOGY_ALTERNATIVE"


class TemporalStatus(str, Enum):
    PLANNED = "PLANNED"
    OCCURRED = "OCCURRED"
    UNKNOWN = "UNKNOWN"


class ObservationState(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ContrastSourceFrame:
    frame: FrameInstance
    frame_schema: FrameSchema
    semantic_release: str
    status: TemporalStatus
    observation_state: ObservationState
    scope: str
    negated: bool
    source_morphology: str
    authorized_morphology_alternatives: tuple[str, ...]
    checker_revision: str

    def __post_init__(self) -> None:
        if (type(self.frame) is not FrameInstance
                or type(self.frame_schema) is not FrameSchema
                or self.frame.frame_schema_id != self.frame_schema.schema_id
                or self.frame.frame_schema_revision != self.frame_schema.revision
                or self.frame.schema_role_order != tuple(r.role_id for r in self.frame_schema.roles)
                or not _SHA.fullmatch(self.semantic_release)
                or type(self.status) is not TemporalStatus
                or type(self.observation_state) is not ObservationState
                or not _text(self.scope)
                or type(self.negated) is not bool
                or not _text(self.source_morphology)
                or type(self.authorized_morphology_alternatives) is not tuple
                or any(not _text(item) for item in self.authorized_morphology_alternatives)
                or len(set(self.authorized_morphology_alternatives))
                    != len(self.authorized_morphology_alternatives)
                or not _text(self.checker_revision)):
            _fail("BAMF_SEMANTIC_CONTRAST_SOURCE_INVALID")
        for binding in self.frame.bindings:
            concepts = ()
            if binding.state is BindingState.VALUE and binding.concept is not None:
                concepts = (binding.concept,)
            elif binding.state is BindingState.ALTERNATIVES:
                concepts = binding.alternatives
            if any(item.semantic_release != self.semantic_release for item in concepts):
                _fail("BAMF_SEMANTIC_CONTRAST_RELEASE_MISMATCH")


@dataclass(frozen=True)
class AllowedVariation:
    family: ContrastFamily
    role_a: str | None = None
    role_b: str | None = None
    query_role: str | None = None
    role_id: str | None = None
    occurrence_index: int | None = None
    concept: ConceptRef | None = None
    remove: bool = False
    scope: str | None = None
    negated: bool | None = None
    status: TemporalStatus | None = None
    observation_state: ObservationState | None = None
    morphology: str | None = None
    surface_label: str | None = None

    @classmethod
    def role_swap(cls, role_a: str, role_b: str, *, query_role: str) -> "AllowedVariation":
        return cls(ContrastFamily.ROLE_SWAP, role_a=role_a, role_b=role_b,
                   query_role=query_role)

    @classmethod
    def add_role_value(cls, role_id: str, concept: ConceptRef) -> "AllowedVariation":
        return cls(ContrastFamily.CARDINALITY_CHANGE, role_id=role_id, concept=concept)

    @classmethod
    def remove_role_value(cls, role_id: str, occurrence_index: int) -> "AllowedVariation":
        return cls(ContrastFamily.CARDINALITY_CHANGE, role_id=role_id,
                   occurrence_index=occurrence_index, remove=True)

    @classmethod
    def scope_negation(
        cls, scope: str, negated: bool, *, surface_label: str | None = None,
    ) -> "AllowedVariation":
        return cls(ContrastFamily.SCOPE_NEGATION, scope=scope, negated=negated,
                   surface_label=surface_label)

    @classmethod
    def unknown_role(cls, role_id: str, occurrence_index: int) -> "AllowedVariation":
        return cls(ContrastFamily.KNOWN_UNKNOWN, role_id=role_id,
                   occurrence_index=occurrence_index)

    @classmethod
    def temporal_status(cls, status: TemporalStatus) -> "AllowedVariation":
        return cls(ContrastFamily.PLANNED_OCCURRED, status=status)

    @classmethod
    def observation(cls, state: ObservationState) -> "AllowedVariation":
        return cls(ContrastFamily.MISSING_NEGATIVE, observation_state=state)

    @classmethod
    def morphology(cls, form: str) -> "AllowedVariation":
        return cls(ContrastFamily.MORPHOLOGY_ALTERNATIVE, morphology=form)

    def __post_init__(self) -> None:
        if type(self.family) is not ContrastFamily or type(self.remove) is not bool:
            _fail("BAMF_SEMANTIC_CONTRAST_VARIATION_INVALID")
        if self.surface_label is not None and not _text(self.surface_label):
            _fail("BAMF_SEMANTIC_CONTRAST_VARIATION_INVALID")
        if self.family is ContrastFamily.ROLE_SWAP:
            if (not all(_text(x) for x in (self.role_a, self.role_b, self.query_role))
                    or self.role_a == self.role_b):
                _fail("BAMF_SEMANTIC_CONTRAST_VARIATION_INVALID")
        elif self.family is ContrastFamily.CARDINALITY_CHANGE:
            if not _text(self.role_id):
                _fail("BAMF_SEMANTIC_CONTRAST_VARIATION_INVALID")
            if self.remove:
                if type(self.occurrence_index) is not int or self.occurrence_index < 0 or self.concept is not None:
                    _fail("BAMF_SEMANTIC_CONTRAST_VARIATION_INVALID")
            elif type(self.concept) is not ConceptRef or self.occurrence_index is not None:
                _fail("BAMF_SEMANTIC_CONTRAST_VARIATION_INVALID")
        elif self.family is ContrastFamily.SCOPE_NEGATION:
            if not _text(self.scope) or type(self.negated) is not bool:
                _fail("BAMF_SEMANTIC_CONTRAST_VARIATION_INVALID")
        elif self.family is ContrastFamily.KNOWN_UNKNOWN:
            if not _text(self.role_id) or type(self.occurrence_index) is not int or self.occurrence_index < 0:
                _fail("BAMF_SEMANTIC_CONTRAST_VARIATION_INVALID")
        elif self.family is ContrastFamily.PLANNED_OCCURRED:
            if type(self.status) is not TemporalStatus or self.status is TemporalStatus.UNKNOWN:
                _fail("BAMF_SEMANTIC_CONTRAST_VARIATION_INVALID")
        elif self.family is ContrastFamily.MISSING_NEGATIVE:
            if (type(self.observation_state) is not ObservationState
                    or self.observation_state not in {ObservationState.MISSING, ObservationState.NEGATIVE}):
                _fail("BAMF_SEMANTIC_CONTRAST_VARIATION_INVALID")
        elif self.family is ContrastFamily.MORPHOLOGY_ALTERNATIVE:
            if not _text(self.morphology):
                _fail("BAMF_SEMANTIC_CONTRAST_VARIATION_INVALID")


