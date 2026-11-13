"""Typed immutable records for the Curriculum Registry projection."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from .helpers import _digest

@dataclass(frozen=True)
class Origin:
    tab: str
    row: int
    sheet_id: int

@dataclass(frozen=True)
class TokenNode:
    id: int
    symbol: str
    identity: str
    meaning: str
    signature: str
    family: str
    subtype: str
    arity: str
    ni_locus: str
    graph_sha256: str
    contract_sha256: str
    meaning_review: str
    origin: Origin

@dataclass(frozen=True)
class LessonNode:
    id: str
    legacy_alias: str
    title: str
    semantics: str
    teaching_intent: str
    prerequisite_text: str
    assessment_intent: str
    evidence_status: str
    gate: str
    source_claim: str
    grade: str | None
    requires_grades: tuple[str, ...]
    requires_lessons: tuple[str, ...]
    construction: str
    intended_probe: str
    origin: Origin

@dataclass(frozen=True)
class PrerequisiteNode:
    sequence: str
    concept: str
    prerequisite_text: str
    construction: str
    assessment: str
    status: str
    source_claim: str
    grade: str
    proposed_lesson: str
    requires_grades: tuple[str, ...]
    requires_lessons: tuple[str, ...]
    evidence_gate: str
    origin: Origin

@dataclass(frozen=True)
class GradeNode:
    id: str
    title: str
    status: str
    planned_capabilities: str
    notes: str
    origin: Origin

@dataclass(frozen=True)
class BridgeNode:
    id: str
    concept: str
    meaning: str
    link_type: str
    construction: str
    probe: str
    status: str
    source_claim: str
    caution: str
    related_lessons: tuple[str, ...]
    origin: Origin

@dataclass(frozen=True)
class RegistryAST:
    source_id: str
    source_sha256: str
    tokens: tuple[TokenNode, ...]
    lessons: tuple[LessonNode, ...]
    prerequisites: tuple[PrerequisiteNode, ...]
    grades: tuple[GradeNode, ...]
    bridges: tuple[BridgeNode, ...]
    supplemental_constraints: tuple[PrerequisiteNode, ...]
    training_authorized: bool = False

    def digest(self) -> str:
        return _digest(asdict(self))

@dataclass(frozen=True)
class StagePlan:
    grade: str
    status: str
    lessons: tuple[LessonNode, ...]
    blockers: tuple[str, ...]
    training_authorized: bool = False

    def digest(self) -> str:
        return _digest(asdict(self))

@dataclass(frozen=True)
class ConstructionTask:
    id: str
    concept: str
    instruction: str
    proposed_probe: str
    unmet_grades: tuple[str, ...]
    unmet_lessons: tuple[str, ...]
    ready_to_construct: bool
    training_authorized: bool = False

def _origin(tab: str, i: int, sheet_id: int) -> Origin:
    return Origin(tab, i, sheet_id)
