"""Checkpoint-local and durable teacher policy cooldown state."""
from __future__ import annotations

from bilqis_mlx.learning.teacher_feedback import LearningExperimentError

from .population import (
    BAMF_SUCCESSOR_SELECTION,
    CONTEXT_PART_COUNT,
    DURABLE_POLICY_COOLDOWN_CAPABILITY_VISITS,
    DURABLE_POLICY_FAILED_STUDENT_LIMIT,
    MAX_FAILED_STUDENT_EPOCHS,
    SAME_STUDENT_POLICY_NO_TARGET_GAIN_LIMIT,
    SAME_STUDENT_POLICY_UNRETAINED_LIMIT,
    SIBLING_COOLDOWN_PENALTY,
    STUDENT_SHA256_HEX_LENGTH,
    effective_context_scope,
    historical_policy_mean,
)

def _validated_student_checkpoint(student_checkpoint_sha256: str | None) -> str | None:
    if student_checkpoint_sha256 is None:
        return None
    if (not isinstance(student_checkpoint_sha256, str) or
            len(student_checkpoint_sha256) != STUDENT_SHA256_HEX_LENGTH or
            any(char not in "0123456789abcdef" for char in student_checkpoint_sha256)):
        raise ValueError(LearningExperimentError.STUDENT_CHECKPOINT_INVALID.value)
    return student_checkpoint_sha256


def _context_parts(context_key: str) -> tuple[str, str, str]:
    parts = context_key.split("|", 2)
    if len(parts) != CONTEXT_PART_COUNT or not parts[0]:
        raise ValueError(LearningExperimentError.STUDENT_POLICY_FAILURE_INVALID.value)
    return parts[0], parts[1], parts[2]


def _capability_attempts(channel: dict, capability: str, curriculum_scope: str) -> int:
    record = channel.get("capability_stagnation", {}).get(
        capability + "|" + curriculum_scope, {})
    return int(record.get("total_rejections", 0)) + int(record.get("total_retained", 0))


def _cooldown_bucket(channel: dict, capability: str, curriculum_scope: str,
                     *, create: bool = False) -> dict:
    all_cooldowns = channel.setdefault("policy_cooldowns", {}) if create else channel.get("policy_cooldowns", {})
    key = capability + "|" + curriculum_scope
    if create:
        return all_cooldowns.setdefault(key, {})
    bucket = all_cooldowns.get(key, {})
    return bucket if isinstance(bucket, dict) else {}


def durable_policy_cooldown_status(channel: dict, capability: str,
                                   curriculum_scope: str,
                                   effective_policy_key: str) -> dict:
    bucket = _cooldown_bucket(channel, capability, curriculum_scope)
    record = bucket.get(effective_policy_key)
    if not isinstance(record, dict):
        return {"active": False, "failed_student_epochs": 0,
                "remaining_capability_visits": 0}
    attempts = _capability_attempts(channel, capability, curriculum_scope)
    until = int(record.get("cooldown_until_attempt", 0))
    failed = list(record.get("failed_student_sha256", ()))
    if until and attempts >= until:
        # Expiry decays one epoch of bad evidence rather than granting amnesia.
        record["failed_student_sha256"] = failed[-1:]
        record.pop("cooldown_until_attempt", None)
        until = 0
        failed = record["failed_student_sha256"]
    active = until > attempts
    return {
        "active": active,
        "status": "SEARCH_NEIGHBORHOOD_EXHAUSTED" if active else None,
        "failed_student_epochs": len(failed),
        "remaining_capability_visits": max(0, until - attempts),
    }


def durable_cooled_effective_keys(channel: dict, capability: str,
                                  curriculum_scope: str) -> set[str]:
    return {
        key for key in _cooldown_bucket(channel, capability, curriculum_scope)
        if durable_policy_cooldown_status(
            channel, capability, curriculum_scope, key)["active"]
    }


def sibling_cooldown_penalty(channel: dict, capability: str,
                             curriculum_scope: str,
                             effective_policy_key: str) -> float:
    if channel.get("selection_contract") == BAMF_SUCCESSOR_SELECTION:
        # No source-qualified sibling relation is supplied at this boundary.
        return 0.
    grade = capability.partition(".")[0]
    siblings = 0
    for bucket_key in channel.get("policy_cooldowns", {}):
        sibling, separator, scope = bucket_key.partition("|")
        if (not separator or sibling == capability or scope != curriculum_scope or
                sibling.partition(".")[0] != grade):
            continue
        if durable_policy_cooldown_status(
                channel, sibling, scope, effective_policy_key)["active"]:
            siblings += 1
    return min(.05, siblings * SIBLING_COOLDOWN_PENALTY)


def _record_durable_capability_outcome(
        channel: dict, context_key: str, effective_policy_key: str,
        checkpoint: str, *, same_student_unretained: int, retained: bool) -> None:
    capability, _phase, curriculum_scope = _context_parts(context_key)
    bucket = _cooldown_bucket(channel, capability, curriculum_scope, create=True)
    if retained:
        bucket.pop(effective_policy_key, None)
        return
    if same_student_unretained < SAME_STUDENT_POLICY_UNRETAINED_LIMIT:
        return
    record = bucket.setdefault(effective_policy_key, {
        "failed_student_sha256": [],
    })
    failed = record.setdefault("failed_student_sha256", [])
    if checkpoint in failed:
        return
    failed.append(checkpoint)
    del failed[:-MAX_FAILED_STUDENT_EPOCHS]
    if len(failed) >= DURABLE_POLICY_FAILED_STUDENT_LIMIT:
        attempts = _capability_attempts(channel, capability, curriculum_scope)
        record["cooldown_until_attempt"] = (
            attempts + DURABLE_POLICY_COOLDOWN_CAPABILITY_VISITS)


def _checkpoint_policy_no_gain_streaks(channel: dict, context_key: str,
                                       student_checkpoint_sha256: str | None) -> dict:
    checkpoint = _validated_student_checkpoint(student_checkpoint_sha256)
    if checkpoint is None:
        return {}
    epoch = channel.get("student_policy_epoch")
    if not isinstance(epoch, dict) or epoch.get("student_sha256") != checkpoint:
        return {}
    if not isinstance(epoch.get("contexts"), dict):
        raise ValueError(LearningExperimentError.STUDENT_POLICY_EPOCH_INVALID.value)
    failures = epoch["contexts"].get(context_key, {})
    if (not isinstance(failures, dict) or any(
            not isinstance(key, str) or type(value) is not int or value < 0
            for key, value in failures.items())):
        raise ValueError(LearningExperimentError.STUDENT_POLICY_FAILURE_INVALID.value)
    return failures


def record_checkpoint_policy_outcome(
        channel: dict, context_key: str, effective_policy_key: str,
        student_checkpoint_sha256: str | None, *, no_target_gain: bool,
        retained: bool) -> None:
    checkpoint = _validated_student_checkpoint(student_checkpoint_sha256)
    if checkpoint is None:
        return
    epoch = channel.get("student_policy_epoch")
    if not isinstance(epoch, dict) or epoch.get("student_sha256") != checkpoint:
        epoch = {
            "student_sha256": checkpoint,
            "contexts": {},
            "unretained_contexts": {},
        }
        channel["student_policy_epoch"] = epoch
    if (not isinstance(epoch.get("contexts"), dict) or
            not isinstance(epoch.setdefault("unretained_contexts", {}), dict)):
        raise ValueError(LearningExperimentError.STUDENT_POLICY_EPOCH_INVALID.value)
    streaks = epoch["contexts"].setdefault(context_key, {})
    if no_target_gain:
        streaks[effective_policy_key] = streaks.get(effective_policy_key, 0) + 1
    else:
        streaks.pop(effective_policy_key, None)

    unretained = epoch["unretained_contexts"].setdefault(context_key, {})
    if retained:
        unretained.pop(effective_policy_key, None)
    else:
        unretained[effective_policy_key] = unretained.get(effective_policy_key, 0) + 1
    _record_durable_capability_outcome(
        channel, context_key, effective_policy_key, checkpoint,
        same_student_unretained=unretained.get(effective_policy_key, 0),
        retained=retained)


def checkpoint_active_effective_strategy_keys(
        teacher: dict, grade: str, scope: dict, channel: dict,
        context_key: str, active_effective: tuple[str, ...],
        inventory: dict[str, list[str]],
        student_checkpoint_sha256: str | None) -> tuple[tuple[str, ...], set[str]]:
    checkpoint_failures = _checkpoint_policy_no_gain_streaks(
        channel, context_key, student_checkpoint_sha256)
    checkpoint = _validated_student_checkpoint(student_checkpoint_sha256)
    unretained_failures = {}
    if checkpoint is not None:
        epoch = channel.get("student_policy_epoch")
        if isinstance(epoch, dict) and epoch.get("student_sha256") == checkpoint:
            unretained_contexts = epoch.get("unretained_contexts", {})
            if not isinstance(unretained_contexts, dict):
                raise ValueError(LearningExperimentError.STUDENT_POLICY_EPOCH_INVALID.value)
            unretained_failures = unretained_contexts.get(context_key, {})
            if (not isinstance(unretained_failures, dict) or any(
                    not isinstance(key, str) or type(value) is not int or value < 0
                    for key, value in unretained_failures.items())):
                raise ValueError(LearningExperimentError.STUDENT_POLICY_FAILURE_INVALID.value)
    capability, _phase, curriculum_scope = _context_parts(context_key)
    durable_retired = durable_cooled_effective_keys(
        channel, capability, curriculum_scope)
    retired = durable_retired | {
        key for key in set(checkpoint_failures) | set(unretained_failures)
        if (checkpoint_failures.get(key, 0) >= SAME_STUDENT_POLICY_NO_TARGET_GAIN_LIMIT or
            unretained_failures.get(key, 0) >= SAME_STUDENT_POLICY_UNRETAINED_LIMIT)
    }
    if not retired:
        return active_effective, retired
    evidence = effective_context_scope(teacher, scope) if scope else {}
    eligible = [key for key in active_effective if key not in retired]
    replacements = [
        key for key in inventory if key not in retired and key not in eligible
    ]

    def replacement_rank(key):
        record = evidence.get(key) or {}
        members = inventory[key]
        return (
            int(record.get("trials", 0)),
            int(record.get("retained", 0)),
            -sum(historical_policy_mean(teacher, grade, member)
                 for member in members) / len(members),
            key,
        )

    replacements.sort(key=replacement_rank)
    eligible.extend(replacements[:max(0, len(active_effective) - len(eligible))])
    if not eligible:
        eligible = [min(
            inventory, key=lambda key: (checkpoint_failures.get(key, 0), key))]
    return tuple(eligible), retired
