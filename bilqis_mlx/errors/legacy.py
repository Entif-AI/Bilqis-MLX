"""Compatibility classification for not-yet-migrated string exceptions."""
from __future__ import annotations

from types import MappingProxyType

from .model import ErrorReport


_EXACT = MappingProxyType({
    "HUMAN_TRAINER_NEW_RUN_HAS_EXISTING_CONTENT": (
        "OPERATOR_ACTION",
        "A saved school already exists. Resume it with --resume rather than starting a new run."),
    "VERIFY_SOURCE_REQUIRES_DRY_RUN": (
        "OPERATOR_ACTION",
        "Source verification is neural-inert. Re-run with --dry-run --verify-source."),
    "FLASH_MODE_REQUIRES_RESUME": (
        "OPERATOR_ACTION",
        "Flash mode only applies to an existing school. Add --resume or omit --flash-mode."),
    "NUMERIC_STAIRCASE_REQUIRES_RESUME": (
        "OPERATOR_ACTION",
        "Numeric staircase is a continuation of an existing student. Add --resume."),
    "COHORT_EMPTY": (
        "INTERNAL_RECOVERY_REQUIRED",
        "An internal path attempted to materialize an empty assessment cohort. "
        "The owning domain must regenerate, defer, or reroute it."),
    "CHAMPIONSHIP_TITLE_MATCH_CURRENT_PANEL_UNMEASURED": (
        "INTERNAL_RECOVERY_REQUIRED",
        "A title match lacks a current comparable panel. Defer the match until "
        "the capability is measured."),
})


def leading_legacy_code(error: BaseException | str) -> str:
    text = str(error).strip()
    return text.split(":", 1)[0].strip() or error.__class__.__name__


def legacy_report(error: BaseException | str) -> ErrorReport:
    code = leading_legacy_code(error)
    exact = _EXACT.get(code)
    if exact is not None:
        disposition, next_action = exact
    elif code.endswith("_EXHAUSTED") or "_EXHAUSTED_" in code:
        disposition = "RETRY_OR_REGENERATE"
        next_action = (
            "The owning source/generator exhausted its bounded search. Regenerate "
            "or choose another admitted work item; do not weaken the oracle.")
    elif "REQUIRES" in code or code.endswith("_REQUIRED"):
        disposition = "OPERATOR_OR_SOURCE_PREREQUISITE"
        next_action = (
            "A declared prerequisite is absent. Produce it through its owning "
            "boundary before retrying.")
    elif any(marker in code for marker in (
            "DRIFT", "TAMPER", "UNSAFE", "MISMATCH", "CONFLICT", "CORRUPT")):
        disposition = "PRESERVE_AND_REPAIR"
        next_action = (
            "Identity or custody evidence disagrees. Preserve the durable checkpoint "
            "and repair the mismatched source/state boundary before retrying.")
    elif code.endswith("_MISSING") or "_MISSING_" in code:
        disposition = "RECONSTRUCT_OR_RESTORE"
        next_action = (
            "Required durable evidence is missing. Reconstruct it only from "
            "authoritative receipts or restore the original artifact.")
    elif code.endswith("_INVALID") or "_INVALID_" in code:
        disposition = "CORRECT_INPUT_OR_STATE"
        next_action = (
            "The supplied configuration or saved structure is invalid. Correct "
            "the owning producer and retry from the last durable checkpoint.")
    elif any(marker in code for marker in (
            "FORBIDDEN", "PROHIBITED", "NOT_AUTHORIZED", "AUTHORITY_DENIED")):
        disposition = "AUTHORITY_OR_POLICY_BLOCK"
        next_action = (
            "The action crosses an authority boundary. Keep durable state unchanged "
            "and use the permitted path.")
    elif any(marker in code for marker in (
            "UNKNOWN", "UNSUPPORTED", "OUTSIDE", "INCOMPLETE", "WRONG_",
            "NOT_ADMITTED", "NOT_SCHEDULED", "NOT_COMPLETE", "OUT_OF_")):
        disposition = "CORRECT_INPUT_OR_STATE"
        next_action = (
            "The request/state is outside the admitted contract. Correct the owning "
            "scope producer rather than coercing the value through the gate.")
    elif any(marker in code for marker in (
            "UNQUALIFIED", "NOT_QUALIFIED", "NOT_READY", "NOT_MASTERED",
            "UNAVAILABLE")):
        disposition = "OPERATOR_OR_SOURCE_PREREQUISITE"
        next_action = (
            "The operation is not qualified on current evidence. Produce the "
            "missing evidence through its normal owner.")
    elif "EMPTY" in code:
        disposition = "RETRY_OR_REGENERATE"
        next_action = (
            "A generated/selected work set is empty. The owning domain should "
            "regenerate, defer, or choose another admitted work item.")
    else:
        disposition = "PRESERVE_AND_REPORT"
        next_action = (
            "No automatic repair is proven safe. Preserve the last durable "
            "checkpoint and diagnose the owning boundary.")
    return ErrorReport(
        code=code,
        title=code.replace("_", " ").title(),
        summary=str(error),
        owner="legacy.untyped",
        disposition=disposition,
        next_action=next_action,
        operator_steps=(),
        preserve_state=True,
        self_heal_owner=None,
        context={},
        legacy_untyped=True,
    )
