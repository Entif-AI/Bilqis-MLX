"""Operator-facing recovery policy for failures that survive domain self-healing.

The domain owner should repair, defer, retry, or regenerate a safe condition
before it reaches the CLI.  This module is the final translation layer for the
conditions that still require source repair or human action.  It never weakens
custody, source, semantic, or optimizer authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class RecoveryAdvice:
    code: str
    disposition: str
    next_action: str


_EXACT = MappingProxyType({
    "HUMAN_TRAINER_NEW_RUN_HAS_EXISTING_CONTENT": RecoveryAdvice(
        "HUMAN_TRAINER_NEW_RUN_HAS_EXISTING_CONTENT",
        "OPERATOR_ACTION",
        "A saved school already exists. Resume it with --resume rather than starting a new run.",
    ),
    "VERIFY_SOURCE_REQUIRES_DRY_RUN": RecoveryAdvice(
        "VERIFY_SOURCE_REQUIRES_DRY_RUN",
        "OPERATOR_ACTION",
        "Source verification is neural-inert. Re-run the command with --dry-run --verify-source.",
    ),
    "FLASH_MODE_REQUIRES_RESUME": RecoveryAdvice(
        "FLASH_MODE_REQUIRES_RESUME",
        "OPERATOR_ACTION",
        "Flash mode only applies to an existing school. Add --resume or omit --flash-mode.",
    ),
    "NUMERIC_STAIRCASE_REQUIRES_RESUME": RecoveryAdvice(
        "NUMERIC_STAIRCASE_REQUIRES_RESUME",
        "OPERATOR_ACTION",
        "Numeric staircase is a continuation of an existing student. Add --resume.",
    ),
    "COHORT_EMPTY": RecoveryAdvice(
        "COHORT_EMPTY",
        "INTERNAL_RECOVERY_REQUIRED",
        "An internal path attempted to materialize an empty assessment cohort. "
        "The durable checkpoint remains the resume authority; do not invent questions or bypass the cohort guard.",
    ),
    "CHAMPIONSHIP_TITLE_MATCH_CURRENT_PANEL_UNMEASURED": RecoveryAdvice(
        "CHAMPIONSHIP_TITLE_MATCH_CURRENT_PANEL_UNMEASURED",
        "INTERNAL_RECOVERY_REQUIRED",
        "A title match was requested without a current comparable capability panel. "
        "That match must be deferred until the capability is measured, not forced or synthesized.",
    ),
})


def error_code(error: BaseException | str) -> str:
    """Extract the stable leading code without depending on exception prose."""
    text = str(error).strip()
    return text.split(":", 1)[0].strip() or error.__class__.__name__


def recovery_advice(error: BaseException | str) -> RecoveryAdvice:
    """Classify every surfaced operator failure into one safe recovery posture."""
    code = error_code(error)
    exact = _EXACT.get(code)
    if exact is not None:
        return exact
    if code.endswith("_EXHAUSTED") or "_EXHAUSTED_" in code:
        return RecoveryAdvice(
            code,
            "RETRY_OR_REGENERATE",
            "The owning source/generator exhausted its bounded search. Retry or expand that "
            "source-valid search; do not weaken gold, scope, or custody requirements.",
        )
    if "REQUIRES" in code or code.endswith("_REQUIRED"):
        return RecoveryAdvice(
            code,
            "OPERATOR_OR_SOURCE_PREREQUISITE",
            "A declared prerequisite is absent. Satisfy or safely produce the named prerequisite "
            "before retrying; do not fabricate its receipt.",
        )
    if any(marker in code for marker in (
            "DRIFT", "TAMPER", "UNSAFE", "MISMATCH", "CONFLICT", "CORRUPT")):
        return RecoveryAdvice(
            code,
            "PRESERVE_AND_REPAIR",
            "Identity or custody evidence disagrees. Preserve the durable checkpoint and repair "
            "the mismatched source/state boundary before retrying; bypass is not safe.",
        )
    if code.endswith("_MISSING") or "_MISSING_" in code:
        return RecoveryAdvice(
            code,
            "RECONSTRUCT_OR_RESTORE",
            "Required durable evidence is missing. Reconstruct it only from authoritative "
            "receipts or restore the original artifact; do not synthesize replacement evidence.",
        )
    if code.endswith("_INVALID") or "_INVALID_" in code:
        return RecoveryAdvice(
            code,
            "CORRECT_INPUT_OR_STATE",
            "The supplied configuration or saved structure is invalid. Correct the owning input "
            "or state producer, then retry from the last durable checkpoint.",
        )
    if any(marker in code for marker in (
            "FORBIDDEN", "PROHIBITED", "NOT_AUTHORIZED", "AUTHORITY_DENIED")):
        return RecoveryAdvice(
            code,
            "AUTHORITY_OR_POLICY_BLOCK",
            "The requested action crosses an explicit authority or safety boundary. Keep the "
            "durable state unchanged and obtain the required authority or choose the permitted path.",
        )
    if any(marker in code for marker in (
            "UNKNOWN", "UNSUPPORTED", "OUTSIDE", "INCOMPLETE", "WRONG_",
            "NOT_ADMITTED", "NOT_SCHEDULED", "NOT_COMPLETE", "OUT_OF_")):
        return RecoveryAdvice(
            code,
            "CORRECT_INPUT_OR_STATE",
            "The current request or generated state is outside the admitted contract. Correct the "
            "owning input/scope producer and retry; do not coerce the invalid value through the gate.",
        )
    if any(marker in code for marker in (
            "UNQUALIFIED", "NOT_QUALIFIED", "NOT_READY", "NOT_MASTERED", "UNAVAILABLE")):
        return RecoveryAdvice(
            code,
            "OPERATOR_OR_SOURCE_PREREQUISITE",
            "The operation is not yet qualified on current evidence. Produce the missing source or "
            "student evidence through its normal owner, then retry from the durable checkpoint.",
        )
    if "EMPTY" in code:
        return RecoveryAdvice(
            code,
            "RETRY_OR_REGENERATE",
            "A generated or selected work set is empty. The owning domain should regenerate, defer, "
            "or choose another admitted work item; it must not fabricate evidence.",
        )
    return RecoveryAdvice(
        code,
        "PRESERVE_AND_REPORT",
        "No automatic repair is proven safe for this condition. Preserve the last durable "
        "checkpoint and diagnose the owning boundary before retrying.",
    )
