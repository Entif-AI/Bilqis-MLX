"""Project checker-grounded semantic contrasts through the existing Factory teacher option API."""
from __future__ import annotations

from dataclasses import dataclass

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.factory.semantic_contrast.checker import check_contrast, generate_contrasts
from bilqis_mlx.factory.semantic_contrast.models import LessonSpec
from bilqis_mlx.factory.semantic_contrast.types import (
    AllowedVariation,
    ContrastFamily,
    ContrastSourceFrame,
)


OPTION_ID = "source.semantic-contrast/v1"
CHOICE_REGISTRY_KEY = "semantic_contrast_choices"


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


@dataclass(frozen=True)
class ContrastTeachingChoice:
    """One source-owned structural contrast choice exposed to the teacher."""

    source_frame: ContrastSourceFrame
    family: ContrastFamily
    variations: tuple[AllowedVariation, ...]
    answer_kind: str
    source_roots: tuple[str, ...]

    def __post_init__(self) -> None:
        if (type(self.source_frame) is not ContrastSourceFrame
                or type(self.family) is not ContrastFamily
                or type(self.variations) is not tuple
                or not self.variations
                or any(type(item) is not AllowedVariation for item in self.variations)
                or any(item.family is not self.family for item in self.variations)
                or not isinstance(self.answer_kind, str)
                or not self.answer_kind
                or type(self.source_roots) is not tuple
                or not self.source_roots
                or any(not isinstance(item, str) or not item for item in self.source_roots)):
            _fail("BAMF_SEMANTIC_CONTRAST_TEACHING_CHOICE_INVALID")


def _choice(graph: dict, capability: str) -> ContrastTeachingChoice:
    if not isinstance(graph, dict):
        _fail("BAMF_SEMANTIC_CONTRAST_TEACHING_GRAPH_INVALID")
    registry = graph.get(CHOICE_REGISTRY_KEY)
    if not isinstance(registry, dict):
        _fail("BAMF_SEMANTIC_CONTRAST_TEACHING_REGISTRY_MISSING")
    choice = registry.get(capability)
    if type(choice) is not ContrastTeachingChoice:
        _fail("BAMF_SEMANTIC_CONTRAST_TEACHING_CHOICE_MISSING")
    return choice


def enrich_contrasts(*, graph, capability, seed, option_id, **_) -> tuple[dict, ...]:
    """Existing SourceAdapter.enrich signature; teacher HOW authority stays upstream."""
    if option_id != OPTION_ID:
        _fail("BAMF_SEMANTIC_CONTRAST_TEACHING_OPTION_INVALID")
    choice = _choice(graph, capability)
    lessons = generate_contrasts(
        choice.source_frame, choice.family, seed, choice.variations)
    return tuple({
        "id": lesson.lineage.variant_id,
        "source_id": lesson.lineage.source_occurrence_id,
        "capability": capability,
        "answer_kind": choice.answer_kind,
        "gold": lesson.expected_answer,
        "question": lesson.question,
        "contrast_family": lesson.family.value,
        "contrast_seed": seed,
        "source_roots": choice.source_roots,
        "generator": OPTION_ID,
        "oracle": lesson.checker_id,
    } for lesson in lessons)


def check_contrast_row(row: dict, *, graph=None, **_) -> bool:
    """Replay the independent A11 checker; never trust the stored row gold."""
    if (not isinstance(row, dict)
            or not isinstance(row.get("capability"), str)
            or type(row.get("contrast_seed")) is not int):
        return False
    try:
        choice = _choice(graph, row["capability"])
    except Exception:
        return False
    candidates = generate_contrasts(
        choice.source_frame,
        choice.family,
        row["contrast_seed"],
        choice.variations,
    )
    matches = tuple(
        lesson for lesson in candidates
        if lesson.lineage.variant_id == row.get("id"))
    if len(matches) != 1:
        return False
    lesson = matches[0]
    return (
        row.get("source_id") == lesson.lineage.source_occurrence_id
        and row.get("gold") == lesson.expected_answer
        and row.get("question") == lesson.question
        and row.get("contrast_family") == lesson.family.value
        and row.get("generator") == OPTION_ID
        and row.get("oracle") == lesson.checker_id
        and check_contrast(lesson)
    )


def contrast_semantic_footprint(row: dict) -> tuple[str, ...]:
    """Feed the existing Factory instructional-constituent closure."""
    roots = row.get("source_roots") if isinstance(row, dict) else None
    if (type(roots) is not tuple
            or not roots
            or any(not isinstance(item, str) or not item for item in roots)):
        _fail("BAMF_SEMANTIC_CONTRAST_TEACHING_ROOTS_INVALID")
    return roots
