"""Unadmitted law candidates anchored to original semantic operation IDs.

Only the future canonical catalog can admit a law and allocate its identity.
These immutable candidates supply proposed transformations for falsification,
not law registration, source proof, or student-learning evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .core import Expression, Operation, TypedError


class LawErrorCode(str, Enum):
    MISSING_SOURCE_LOCATOR = "LAW_MISSING_SOURCE_LOCATOR"
    INVALID_CANDIDATE = "LAW_INVALID_CANDIDATE"
    MISSING_CANDIDATE_OR_SCOPE = "LAW_MISSING_CANDIDATE_OR_SCOPE"
    SUBJECT_NOT_CATALOG_BOUND = "LAW_SUBJECT_NOT_CATALOG_BOUND"
    EXPRESSION_NOT_CATALOG_BOUND = "LAW_EXPRESSION_NOT_CATALOG_BOUND"
    INPUT_TYPE_MISMATCH = "LAW_INPUT_TYPE_MISMATCH"
    INPUT_WORLD_MISMATCH = "LAW_INPUT_WORLD_MISMATCH"
    INVALID_TRANSFORMATION = "LAW_INVALID_TRANSFORMATION"
    INVALID_CHECK_RECEIPT = "LAW_INVALID_CHECK_RECEIPT"


@dataclass(frozen=True)
class SourceLocator:
    """A declared source pointer, not a source-validity certificate."""

    artifact: str
    revision: str
    locus: str

    def __post_init__(self) -> None:
        if not all(isinstance(v, str) and v.strip() for v in
                   (self.artifact, self.revision, self.locus)):
            raise TypedError(LawErrorCode.MISSING_SOURCE_LOCATOR.value)


@dataclass(frozen=True)
class LawCandidate:
    """Pure, typed proposed rewrite anchored to an existing catalog operation."""

    subject: Operation
    source: SourceLocator
    input_type: str
    world_contract: str | None
    precondition: Callable[[Expression], bool]
    transform: Callable[[Expression], Expression]

    def __post_init__(self) -> None:
        if (not isinstance(self.subject, Operation) or
                not isinstance(self.source, SourceLocator) or
                self.input_type != self.subject.signature.output or
                (self.subject.world_contract is not None and
                 self.subject.world_contract != self.world_contract) or
                not callable(self.precondition) or not callable(self.transform)):
            raise TypedError(LawErrorCode.INVALID_CANDIDATE.value)
