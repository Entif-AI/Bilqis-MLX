"""Bounded ambiguity and presentation-noise contracts for BAMF A11.2."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.factory.semantic_contrast.checker import generate_contrasts
from bilqis_mlx.factory.semantic_contrast.models import LessonSpec
from bilqis_mlx.factory.semantic_contrast.types import (
    AllowedVariation,
    ContrastFamily,
    ContrastSourceFrame,
)


MAX_AMBIGUITY_INTERPRETATIONS = 4
SHA256_HEX_LENGTH = 64
_NOISE_TYPES = frozenset({"MASK_TEXT"})


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _text(value: object) -> bool:
    return type(value) is str and bool(value)


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class AmbiguityTarget:
    """One decisive answer or an unresolved ordered alternative set."""

    answers: tuple[str, ...]
    unresolved: bool

    def __post_init__(self) -> None:
        if (type(self.answers) is not tuple
                or not self.answers
                or any(not _text(item) for item in self.answers)
                or len(set(self.answers)) != len(self.answers)
                or type(self.unresolved) is not bool
                or self.unresolved != (len(self.answers) > 1)):
            _fail("BAMF_SEMANTIC_AMBIGUITY_TARGET_INVALID")


@dataclass(frozen=True)
class AmbiguityExploration:
    source_occurrence_id: str
    family: ContrastFamily
    interpretations: tuple[LessonSpec, ...]
    target: AmbiguityTarget
    ranking_sha256: str

    def __post_init__(self) -> None:
        if (not _text(self.source_occurrence_id)
                or type(self.family) is not ContrastFamily
                or type(self.interpretations) is not tuple
                or not self.interpretations
                or len(self.interpretations) > MAX_AMBIGUITY_INTERPRETATIONS
                or any(type(item) is not LessonSpec for item in self.interpretations)
                or any(item.family is not self.family for item in self.interpretations)
                or any(item.source.frame.occurrence_id != self.source_occurrence_id
                       for item in self.interpretations)
                or type(self.target) is not AmbiguityTarget
                or len(self.ranking_sha256) != SHA256_HEX_LENGTH):
            _fail("BAMF_SEMANTIC_AMBIGUITY_EXPLORATION_INVALID")


@dataclass(frozen=True)
class NoiseSignature:
    noise_type: str
    location: str
    amount: int
    seed: int

    def __post_init__(self) -> None:
        if (self.noise_type not in _NOISE_TYPES
                or not _text(self.location)
                or type(self.amount) is not int
                or self.amount <= 0
                or type(self.seed) is not int
                or self.seed < 0):
            _fail("BAMF_SEMANTIC_NOISE_SIGNATURE_INVALID")

    @property
    def signature_sha256(self) -> str:
        return _digest({
            "type": self.noise_type,
            "location": self.location,
            "amount": self.amount,
            "seed": self.seed,
        })


@dataclass(frozen=True)
class NoisyLessonPresentation:
    lesson: LessonSpec
    presented_question: str
    signature: NoiseSignature
    weakness_id: str

    def __post_init__(self) -> None:
        if (type(self.lesson) is not LessonSpec
                or not _text(self.presented_question)
                or type(self.signature) is not NoiseSignature
                or not _text(self.weakness_id)
                or len(self.weakness_id) != SHA256_HEX_LENGTH):
            _fail("BAMF_SEMANTIC_NOISY_PRESENTATION_INVALID")


def explore_ambiguity(
    source_frame: ContrastSourceFrame,
    family: ContrastFamily,
    seed: int,
    allowed_variations: tuple[AllowedVariation, ...],
    *,
    decisive_variant_id: str | None = None,
) -> AmbiguityExploration:
    """Rank source-valid interpretations and keep unresolved answers explicit."""
    ranked = generate_contrasts(source_frame, family, seed, allowed_variations)
    interpretations = ranked[:MAX_AMBIGUITY_INTERPRETATIONS]
    if decisive_variant_id is not None:
        matches = tuple(
            item for item in interpretations
            if item.lineage.variant_id == decisive_variant_id)
        if len(matches) != 1:
            _fail("BAMF_SEMANTIC_AMBIGUITY_DECISION_INVALID")
        answers = (matches[0].expected_answer,)
    else:
        answers = tuple(sorted({item.expected_answer for item in interpretations}))
    target = AmbiguityTarget(answers, len(answers) > 1)
    ranking_sha256 = _digest({
        "source_occurrence_id": source_frame.frame.occurrence_id,
        "family": family.value,
        "seed": seed,
        "variant_ids": [item.lineage.variant_id for item in interpretations],
    })
    return AmbiguityExploration(
        source_frame.frame.occurrence_id,
        family,
        interpretations,
        target,
        ranking_sha256,
    )


def apply_presentation_noise(
    lesson: LessonSpec,
    signature: NoiseSignature,
) -> NoisyLessonPresentation:
    """Mask presentation text while leaving source, structural variant, and gold intact."""
    if type(lesson) is not LessonSpec or type(signature) is not NoiseSignature:
        _fail("BAMF_SEMANTIC_NOISE_INPUT_INVALID")
    question = lesson.question
    if signature.location != "question":
        _fail("BAMF_SEMANTIC_NOISE_LOCATION_INVALID")
    amount = min(signature.amount, len(question))
    if amount == len(question):
        start = 0
    else:
        span = len(question) - amount + 1
        start = int(_digest({
            "seed": signature.seed,
            "variant_id": lesson.lineage.variant_id,
            "location": signature.location,
        })[:16], 16) % span
    presented = question[:start] + ("?" * amount) + question[start + amount:]
    weakness_id = _digest({
        "source_occurrence_id": lesson.lineage.source_occurrence_id,
        "variant_id": lesson.lineage.variant_id,
        "signature": signature.signature_sha256,
    })
    return NoisyLessonPresentation(lesson, presented, signature, weakness_id)
