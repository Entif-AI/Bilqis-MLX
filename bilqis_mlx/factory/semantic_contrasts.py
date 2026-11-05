"""Checker-grounded structural lesson contrasts for BAMF A11.1.

Generated variants are task-scoped projections over an immutable source
FrameInstance.  They do not become source authority or canonical FrameInstances.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
import json
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.frame_schema import (
    BindingState,
    ChildFrameRef,
    ConceptRef,
    FrameInstance,
    FrameSchema,
    RoleOccurrence,
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
SCHEMA = "bilqis.semantic-contrast-lesson/v1"
LINEAGE_SCHEMA = "bilqis.semantic-contrast-lineage/v1"
VARIANT_SCHEMA = "bilqis.semantic-contrast-variant/v1"
CHECKER = "bilqis.semantic-contrast-checker/v1"


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


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


def _binding(frame: FrameInstance, role_id: str, index: int = 0) -> RoleOccurrence:
    matches = tuple(item for item in frame.bindings
                    if item.role_id == role_id and item.occurrence_index == index)
    if len(matches) != 1:
        _fail("BAMF_SEMANTIC_CONTRAST_NOT_APPLICABLE")
    return matches[0]


def _target_kwargs(binding: RoleOccurrence) -> dict:
    return {
        "concept": binding.concept,
        "child_frame": binding.child_frame,
        "state": binding.state,
        "alternatives": binding.alternatives,
    }


def _sorted_bindings(source: ContrastSourceFrame, bindings: tuple[RoleOccurrence, ...]) -> tuple[RoleOccurrence, ...]:
    roles = {role.role_id: role for role in source.frame_schema.roles}
    rank = {role.role_id: index for index, role in enumerate(source.frame_schema.roles)}
    if any(item.role_id not in roles for item in bindings):
        _fail("BAMF_SEMANTIC_CONTRAST_NOT_APPLICABLE")
    for role_id, spec in roles.items():
        members = tuple(item for item in bindings if item.role_id == role_id)
        if not spec.min_cardinality <= len(members) <= spec.max_cardinality:
            _fail("BAMF_SEMANTIC_CONTRAST_CARDINALITY_INVALID")
        if tuple(sorted(item.occurrence_index for item in members)) != tuple(range(len(members))):
            _fail("BAMF_SEMANTIC_CONTRAST_OCCURRENCE_SEQUENCE_INVALID")
        for member in members:
            targets = ()
            if member.concept is not None:
                targets = (member.concept,)
            elif member.alternatives:
                targets = member.alternatives
            if any(not set(item.type_ids).intersection(spec.allowed_type_ids) for item in targets):
                _fail("BAMF_SEMANTIC_CONTRAST_ROLE_TYPE_INVALID")
    return tuple(sorted(bindings, key=lambda item: (rank[item.role_id], item.occurrence_index)))


def _apply(source: ContrastSourceFrame, variation: AllowedVariation) -> tuple[ContrastVariant, str]:
    bindings = source.frame.bindings
    scope = source.scope
    negated = source.negated
    status = source.status
    observation = source.observation_state
    morphology = source.source_morphology

    if variation.family is ContrastFamily.ROLE_SWAP:
        left = _binding(source.frame, variation.role_a, 0)
        right = _binding(source.frame, variation.role_b, 0)
        replaced = []
        for item in bindings:
            if item.key == left.key:
                replaced.append(RoleOccurrence(item.role_id, item.occurrence_index, **_target_kwargs(right)))
            elif item.key == right.key:
                replaced.append(RoleOccurrence(item.role_id, item.occurrence_index, **_target_kwargs(left)))
            else:
                replaced.append(item)
        bindings = tuple(replaced)
        applicability = "two-present-role-bindings"
    elif variation.family is ContrastFamily.CARDINALITY_CHANGE:
        same_role = tuple(item for item in bindings if item.role_id == variation.role_id)
        if variation.remove:
            target = _binding(source.frame, variation.role_id, variation.occurrence_index)
            bindings = tuple(item for item in bindings if item.key != target.key)
            # Reindex the retained role occurrences canonically after removal.
            retained = [item for item in bindings if item.role_id == variation.role_id]
            remapped = {item.key: index for index, item in enumerate(retained)}
            bindings = tuple(
                replace(item, occurrence_index=remapped[item.key])
                if item.role_id == variation.role_id else item
                for item in bindings)
            applicability = "existing-role-occurrence-removal"
        else:
            if variation.concept.semantic_release != source.semantic_release:
                _fail("BAMF_SEMANTIC_CONTRAST_RELEASE_MISMATCH")
            next_index = max((item.occurrence_index for item in same_role), default=-1) + 1
            bindings = bindings + (RoleOccurrence(
                variation.role_id, next_index, concept=variation.concept),)
            applicability = "role-cardinality-extension"
    elif variation.family is ContrastFamily.SCOPE_NEGATION:
        scope = variation.scope
        negated = variation.negated
        if scope == source.scope and negated == source.negated:
            _fail("BAMF_SEMANTIC_CONTRAST_NOOP")
        applicability = "scope-or-negation-change"
    elif variation.family is ContrastFamily.KNOWN_UNKNOWN:
        target = _binding(source.frame, variation.role_id, variation.occurrence_index)
        if target.state is BindingState.UNKNOWN:
            _fail("BAMF_SEMANTIC_CONTRAST_NOOP")
        bindings = tuple(
            RoleOccurrence(item.role_id, item.occurrence_index, state=BindingState.UNKNOWN)
            if item.key == target.key else item
            for item in bindings)
        applicability = "known-binding-to-unknown"
    elif variation.family is ContrastFamily.PLANNED_OCCURRED:
        status = variation.status
        if status is source.status:
            _fail("BAMF_SEMANTIC_CONTRAST_NOOP")
        applicability = "planned-occurred-status-change"
    elif variation.family is ContrastFamily.MISSING_NEGATIVE:
        observation = variation.observation_state
        if observation is source.observation_state:
            _fail("BAMF_SEMANTIC_CONTRAST_NOOP")
        applicability = "missing-negative-observation-distinction"
    elif variation.family is ContrastFamily.MORPHOLOGY_ALTERNATIVE:
        if variation.morphology not in source.authorized_morphology_alternatives:
            _fail("BAMF_SEMANTIC_CONTRAST_MORPHOLOGY_UNAUTHORIZED")
        morphology = variation.morphology
        if morphology == source.source_morphology:
            _fail("BAMF_SEMANTIC_CONTRAST_NOOP")
        applicability = "source-authorized-morphology-alternative"
    else:
        _fail("BAMF_SEMANTIC_CONTRAST_FAMILY_UNSUPPORTED")

    return ContrastVariant(
        source.frame.occurrence_id,
        source.frame.content_digest,
        _sorted_bindings(source, bindings),
        scope,
        negated,
        status,
        observation,
        morphology,
    ), applicability


def _answer_for_binding(binding: RoleOccurrence) -> str:
    if binding.state is BindingState.UNKNOWN:
        return "UNKNOWN"
    if binding.state is BindingState.NONE:
        return "NONE"
    if binding.state is BindingState.ALTERNATIVES:
        return "|".join(item.semantic_id for item in binding.alternatives)
    if binding.concept is not None:
        return binding.concept.semantic_id
    if type(binding.child_frame) is ChildFrameRef:
        return binding.child_frame.content_digest
    _fail("BAMF_SEMANTIC_CONTRAST_CHECKER_INVALID")
    raise AssertionError("unreachable")


def _checker_outcome(
    family: ContrastFamily, variant: ContrastVariant, variation: AllowedVariation,
) -> tuple[str, str]:
    """Independent literal oracle over the transformed structural state."""
    if family is ContrastFamily.ROLE_SWAP:
        return f"What fills role {variation.query_role}?", _answer_for_binding(
            variant.binding(variation.query_role, 0))
    if family is ContrastFamily.CARDINALITY_CHANGE:
        count = sum(1 for item in variant.bindings if item.role_id == variation.role_id)
        return f"How many {variation.role_id} bindings?", str(count)
    if family is ContrastFamily.SCOPE_NEGATION:
        polarity = "NEGATED" if variant.negated else "AFFIRMED"
        return "What is the scope/polarity state?", f"{polarity}@{variant.scope}"
    if family is ContrastFamily.KNOWN_UNKNOWN:
        return f"What fills role {variation.role_id}?", _answer_for_binding(
            variant.binding(variation.role_id, variation.occurrence_index))
    if family is ContrastFamily.PLANNED_OCCURRED:
        return "Planned or occurred?", variant.status.value
    if family is ContrastFamily.MISSING_NEGATIVE:
        return "Missing observation or negative observation?", variant.observation_state.value
    if family is ContrastFamily.MORPHOLOGY_ALTERNATIVE:
        return "Which source-authorized morphology is realized?", variant.morphology
    _fail("BAMF_SEMANTIC_CONTRAST_CHECKER_INVALID")
    raise AssertionError("unreachable")


def _lineage(
    source: ContrastSourceFrame, family: ContrastFamily, variant: ContrastVariant,
) -> ContrastLineage:
    mutation_digest = _digest({"family": family.value, "variant": variant.structural_payload()})
    variant_id = _digest({
        "schema": VARIANT_SCHEMA,
        "source_occurrence_id": source.frame.occurrence_id,
        "source_content_digest": source.frame.content_digest,
        "family": family.value,
        "mutation_digest": mutation_digest,
    })
    return ContrastLineage(
        source.frame.occurrence_id,
        source.frame.content_digest,
        source.frame.source_instance_id,
        family,
        mutation_digest,
        variant_id,
        source.checker_revision,
    )


def generate_contrasts(
    source_frame: ContrastSourceFrame,
    family: ContrastFamily,
    seed: int,
    allowed_variations: tuple[AllowedVariation, ...],
) -> tuple[LessonSpec, ...]:
    """Generate deterministic checker-grounded structural variants only."""
    if (type(source_frame) is not ContrastSourceFrame
            or type(family) is not ContrastFamily
            or type(seed) is not int or seed < 0
            or type(allowed_variations) is not tuple or not allowed_variations
            or any(type(item) is not AllowedVariation for item in allowed_variations)
            or any(item.family is not family for item in allowed_variations)):
        _fail("BAMF_SEMANTIC_CONTRAST_INPUT_INVALID")

    unique: dict[str, LessonSpec] = {}
    for variation in allowed_variations:
        variant, applicability = _apply(source_frame, variation)
        lineage = _lineage(source_frame, family, variant)
        question, outcome = _checker_outcome(family, variant, variation)
        lesson = LessonSpec(
            family, source_frame, variation, variant, lineage,
            applicability, question, outcome,
        )
        # Surface labels are intentionally excluded from structural identity.
        unique.setdefault(lineage.variant_id, lesson)
    return tuple(sorted(
        unique.values(),
        key=lambda item: _digest({"seed": seed, "variant_id": item.lineage.variant_id}),
    ))


def check_contrast(lesson: LessonSpec) -> bool:
    """Replay transformation and oracle without trusting stored variant/gold."""
    if type(lesson) is not LessonSpec:
        _fail("BAMF_SEMANTIC_CONTRAST_CHECKER_INPUT_INVALID")
    LessonSpec.__post_init__(lesson)
    expected_variant, applicability = _apply(lesson.source, lesson.variation)
    expected_lineage = _lineage(lesson.source, lesson.family, expected_variant)
    question, outcome = _checker_outcome(
        lesson.family, expected_variant, lesson.variation)
    return (
        lesson.variant == expected_variant
        and lesson.lineage == expected_lineage
        and lesson.applicability == applicability
        and lesson.question == question
        and lesson.expected_answer == outcome
    )
