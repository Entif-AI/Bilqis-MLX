"""Independent checker, lineage, and generation for BAMF semantic contrasts."""
from __future__ import annotations

from hashlib import sha256
import json

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.frame_schema import BindingState, ChildFrameRef, RoleOccurrence
from bilqis_mlx.factory.semantic_contrast.models import VARIANT_SCHEMA, ContrastLineage, ContrastVariant, LessonSpec
from bilqis_mlx.factory.semantic_contrast.transform import apply_variation
from bilqis_mlx.factory.semantic_contrast.types import AllowedVariation, ContrastFamily, ContrastSourceFrame


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


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
    raise AssertionError


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
    raise AssertionError


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
        variant, applicability = apply_variation(source_frame, variation)
        lineage = _lineage(source_frame, family, variant)
        question, outcome = _checker_outcome(family, variant, variation)
        lesson = LessonSpec(
            family, source_frame, variation, variant, lineage,
            applicability, question, outcome,
        )
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
    expected_variant, applicability = apply_variation(lesson.source, lesson.variation)
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
