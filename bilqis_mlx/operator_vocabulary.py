"""Typed operator-visible stop reasons, blockers, and handoff signals."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OperationalKind(str, Enum):
    STOP_REASON = "STOP_REASON"
    BLOCKER = "BLOCKER"


@dataclass(frozen=True)
class OperationalTerm:
    code: str
    kind: OperationalKind
    owner: str
    meaning: str
    next_action: str
    neural_effect: str
    aliases: tuple[str, ...] = ()


AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED = OperationalTerm(
    code="AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED",
    kind=OperationalKind.STOP_REASON,
    owner="runtime.autonomy_live",
    meaning=(
        "The executable learner frontier is exhausted or deferred, while the "
        "verified source/JIT frontier still contains candidates that are not "
        "yet executable."),
    next_action=(
        "Continue in source-development mode. Build the missing source/factory "
        "binding, then recompile a normally admitted executable successor."),
    neural_effect="No optimizer update is authorized by this stop reason.",
    aliases=("SCHOOL_AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED",),
)


STAGED_SUCCESSOR_BINDING_REQUIRED = OperationalTerm(
    code="STAGED_SUCCESSOR_BINDING_REQUIRED",
    kind=OperationalKind.BLOCKER,
    owner="factory.jit_curriculum",
    meaning=(
        "A source-grounded candidate exists, but no exact precompiled executable "
        "successor binds that candidate through the normal factory admission path."),
    next_action=(
        "Construct and verify the candidate-to-successor source, answer, world, "
        "coverage and admission bindings. Do not self-admit the candidate."),
    neural_effect="The candidate cannot enter training while this blocker exists.",
)


AUTONOMY_SAFE_HOLD = OperationalTerm(
    code="AUTONOMY_SAFE_HOLD",
    kind=OperationalKind.STOP_REASON,
    owner="factory.autonomy",
    meaning=(
        "No productive legal learner action remains in the current executable "
        "frontier after bounded remediation."),
    next_action=(
        "Check the source/JIT frontier. If source-grounded work exists, transition "
        "to source development. Otherwise preserve state and report the blocker."),
    neural_effect="Model and optimizer remain unchanged while the hold is active.",
    aliases=("SCHOOL_AUTONOMY_SAFE_HOLD",),
)


ATLAS_ADMISSION_STAGED = OperationalTerm(
    code="ATLAS_ADMISSION_STAGED",
    kind=OperationalKind.STOP_REASON,
    owner="runtime.atlas_admission",
    meaning="An exact source successor remains staged without current Atlas admission authority.",
    next_action="Retain the staged successor; reconcile the explicit Atlas scope and accepted run-owner admission interface.",
    neural_effect="No optimizer update or release adoption is authorized by this stop reason.",
)


OPERATIONAL_TERMS = (
    ATLAS_ADMISSION_STAGED,
    AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED,
    STAGED_SUCCESSOR_BINDING_REQUIRED,
    AUTONOMY_SAFE_HOLD,
)


BY_OPERATIONAL_CODE = {
    code: term
    for term in OPERATIONAL_TERMS
    for code in (term.code, *term.aliases)
}
