"""Source-grounded lesson selection and weakness replay composition."""
from __future__ import annotations

from enum import Enum
import random
from typing import Mapping

from bilqis_mlx.factory.schedule import ScheduleProgram
from bilqis_mlx.learning.teacher_feedback import (
    LearningExperimentError, WeaknessTargetError, WeaknessTargetRequest,
    select_weakness_targets,
)


MIN_LESSON_BATCH_SIZE = 2
DEEP_SOURCE_POLICY_LEVEL = 3
POLICY_SCALE = 32


class LessonSelectionError(str, Enum):
    SCHEDULE_PROGRAM_REQUIRED = "LEARNING_EXPERIMENT_SCHEDULE_PROGRAM_REQUIRED"
    UNKNOWN_TARGET_GRADE = "LEARNING_EXPERIMENT_UNKNOWN_TARGET_GRADE"
    MISSING_SOURCE_ROWS = "LEARNING_EXPERIMENT_MISSING_SOURCE_ROWS"
    BINARY_PATTERN_CAPACITY = "LEARNING_EXPERIMENT_BINARY_PATTERN_CAPACITY"
    BINARY_CLASS_MISSING = "LEARNING_EXPERIMENT_BINARY_CLASS_MISSING"
    EMPTY_TYPED_LESSON = "LEARNING_EXPERIMENT_EMPTY_TYPED_LESSON"
    INVALID_OLD_POLICY = "LEARNING_EXPERIMENT_INVALID_OLD_POLICY"
    MISSING_FRESH_CURRENT_ROWS = "LEARNING_EXPERIMENT_MISSING_FRESH_CURRENT_ROWS"


def earlier_grade_capabilities(program, graduated_grades, target: str, *,
                               carried_mastery_debt=()) -> tuple[str, ...]:
    """Earlier graduated skills and explicitly carried debt supply old lessons."""
    if not isinstance(program, ScheduleProgram):
        raise TypeError(LessonSelectionError.SCHEDULE_PROGRAM_REQUIRED.value)
    target_index = next((
        index for index, grade in enumerate(program.grades)
        if target in {capability.id for capability in grade.capabilities}
    ), None)
    if target_index is None:
        raise ValueError(LessonSelectionError.UNKNOWN_TARGET_GRADE.value)
    graduated = set(graduated_grades)
    debt = set(carried_mastery_debt)
    return tuple(sorted(
        capability.id
        for grade in program.grades[:target_index]
        for capability in grade.capabilities
        if grade.id in graduated or capability.id in debt))


def _choose_binary_rows(source, count, policy, rng):
    if count == 0:
        return []
    if not source:
        raise ValueError(LessonSelectionError.MISSING_SOURCE_ROWS.value)
    groups = {}
    for row in source:
        groups.setdefault(tuple(row["operand_truths"]), []).append(row)
    if count < len(groups):
        raise ValueError(LessonSelectionError.BINARY_PATTERN_CAPACITY.value)
    chosen = []
    for pattern in sorted(groups):
        options = list(groups[pattern])
        if policy.get("depth", 1) >= DEEP_SOURCE_POLICY_LEVEL:
            options.sort(key=lambda row: (-len(row["tokens"]), row["id"]))
            chosen.append(options[0])
        else:
            chosen.append(rng.choice(options))

    remaining = count-len(chosen)
    pools = {gold: [row for row in source if row["gold"] == gold]
             for gold in ("FALSE", "TRUE")}
    if any(not pool for pool in pools.values()):
        raise ValueError(LessonSelectionError.BINARY_CLASS_MISSING.value)
    if policy.get("depth", 1) >= DEEP_SOURCE_POLICY_LEVEL:
        for pool in pools.values():
            pool.sort(key=lambda row: (-len(row["tokens"]), row["id"]))
    else:
        for pool in pools.values():
            rng.shuffle(pool)
    used = {row["id"] for row in chosen}
    counts = {gold: sum(row["gold"] == gold for row in chosen)
              for gold in pools}
    while remaining:
        gold = min(pools, key=lambda item: (counts[item], item))
        options = [row for row in pools[gold] if row["id"] not in used]
        if not options:
            options = pools[gold]
        row = (options[0] if policy.get("depth", 1) >= DEEP_SOURCE_POLICY_LEVEL
               else rng.choice(options))
        chosen.append(row)
        used.add(row["id"])
        counts[gold] += 1
        remaining -= 1
    rng.shuffle(chosen)
    return chosen


def _choose_typed_rows(source, count, policy, rng):
    if count == 0:
        return []
    if not source:
        raise ValueError(LessonSelectionError.MISSING_SOURCE_ROWS.value)
    groups = {}
    for row in source:
        groups.setdefault(row.get("source_id", row["id"]), []).append(row)
    chunks = list(groups.values())
    if policy.get("depth", 1) >= DEEP_SOURCE_POLICY_LEVEL:
        chunks.sort(key=lambda group: -max(len(row["tokens"]) for row in group))
        chunks = chunks[:max(1, (len(chunks)+1)//2)]
    if policy.get("contrast", 0.) >= .5:
        families = {}
        for chunk in chunks:
            key = tuple(sorted(set(row["gold"] for row in chunk)))
            families.setdefault(key, []).append(chunk)
        keys = sorted(families)
        result = []
        while len(result) < count:
            for key in keys:
                result.extend(rng.choice(families[key]))
                if len(result) >= count:
                    break
        return result[:count]
    result = []
    while len(result) < count:
        result.extend(rng.choice(chunks))
    return result[:count]


def reserve_weakness_targets(chosen: list[dict],
                             targets: list[dict], *,
                             protected_ids: set[str] | frozenset[str] = frozenset()
                             ) -> tuple[list[dict], tuple[dict, ...]]:
    """Replace generic current rows with weak semantics without changing batch size."""
    result = list(chosen)
    remaining_protected = set(protected_ids)
    consumed = set()
    for index, row in enumerate(result):
        identity = row.get("id")
        if identity in remaining_protected:
            consumed.add(index)
            remaining_protected.remove(identity)
    if remaining_protected:
        raise ValueError(
            WeaknessTargetError.LEARNING_EXPERIMENT_WEAKNESS_TARGET_CAPACITY_DRIFT.value)
    delivered = []
    for target in targets:
        existing = next((
            index for index, row in enumerate(result)
            if index not in consumed and row["id"] == target["id"]
        ), None)
        if existing is not None:
            consumed.add(existing)
            delivered.append(target)
            continue
        pattern = target.get("operand_truths")
        answer_kind = target.get("answer_kind", "binary")
        replacement = None
        if isinstance(pattern, list):
            replacement = next((
                index for index, row in enumerate(result)
                if index not in consumed and row.get("operand_truths") == pattern
            ), None)
        if replacement is None and answer_kind == "binary":
            replacement = next((
                index for index, row in enumerate(result)
                if index not in consumed and row.get("gold") == target.get("gold")
            ), None)
        if replacement is None:
            replacement = next((
                index for index, row in enumerate(result)
                if index not in consumed and
                row.get("answer_kind", "binary") == answer_kind
            ), None)
        if replacement is None:
            replacement = next((
                index for index in range(len(result))
                if index not in consumed
            ), None)
        if replacement is None:
            raise ValueError(
                WeaknessTargetError.
                LEARNING_EXPERIMENT_WEAKNESS_TARGET_CAPACITY_DRIFT.value)
        result[replacement] = target
        consumed.add(replacement)
        delivered.append(target)
    return result, tuple(delivered)


def _fresh_support_rows(current: list[dict], policy: dict, rng,
                        *, structured_binary: bool,
                        semantic_patterns: list[tuple],
                        present_count: int,
                        max_rows: int) -> tuple[dict, ...]:
    if not current or present_count < 1 or max_rows < 1:
        return ()
    if structured_binary:
        if len(semantic_patterns) > max_rows:
            return ()
        count = min(present_count, max_rows, len(semantic_patterns))
        return tuple(_choose_binary_rows(current, count, policy, rng))
    groups = {}
    for row in current:
        groups.setdefault(row.get("source_id", row["id"]), []).append(row)
    chunks = [group for group in groups.values() if len(group) <= max_rows]
    if not chunks:
        return ()
    if policy.get("depth", 1) >= DEEP_SOURCE_POLICY_LEVEL:
        chunks.sort(
            key=lambda group: (
                -max(len(row["tokens"]) for row in group),
                str(group[0].get("source_id", group[0]["id"]))))
        chosen = chunks[0]
    else:
        chosen = rng.choice(chunks)
    return tuple(chosen) if len(chosen) <= present_count else ()


def _selected_weakness_targets(
        targets, priority_target_ids, target_exposures, target_capacity):
    priority_targets = [
        row for row in targets if row["id"] in priority_target_ids]
    ordinary_targets = [
        row for row in targets if row["id"] not in priority_target_ids]
    selected_priority = select_weakness_targets(
        priority_targets,
        WeaknessTargetRequest(
            exposures=dict(target_exposures or {}),
            capacity=target_capacity))
    selected_ordinary = select_weakness_targets(
        ordinary_targets,
        WeaknessTargetRequest(
            exposures=dict(target_exposures or {}),
            capacity=max(0, target_capacity-len(selected_priority))))
    return (
        priority_targets, selected_priority,
        [*selected_priority, *selected_ordinary])


def _lesson_control_receipt(
        *, requested_old, old_count, targets, selected_targets,
        delivered_targets, delivered_support, priority_targets,
        selected_priority, priority_target_ids, reserved_support_slots,
        semantic_patterns, delivered_patterns, policy):
    return {
        "effective_old_grade_examples": old_count,
        "requested_old_per_32": requested_old,
        "weakness_targets_available": len(targets),
        "weakness_targets_requested": len(selected_targets),
        "weakness_targets_delivered": len(delivered_targets),
        "weakness_target_ids": [row["id"] for row in delivered_targets],
        "fresh_support_ids": [row["id"] for row in delivered_support],
        "fresh_support_delivered": len(delivered_support),
        "priority_weakness_targets_available": len(priority_targets),
        "priority_weakness_targets_requested": len(selected_priority),
        "priority_weakness_targets_delivered": sum(
            row["id"] in priority_target_ids for row in delivered_targets),
        "reserved_support_slots": reserved_support_slots,
        "current_semantic_patterns_required": len(semantic_patterns),
        "current_semantic_patterns_delivered": len(delivered_patterns),
        "depth_control": (
            "SOURCE_TOKEN_LENGTH_PROXY"
            if policy.get("depth", 1) >= DEEP_SOURCE_POLICY_LEVEL else
            "UNBIASED_SOURCE_GROUPS"),
        "contrast_control": (
            "SOURCE_GROUP_DIVERSITY"
            if policy.get("contrast", 0.) >= .5 else
            "SOURCE_GROUP_RANDOM"),
        "preview_control": "NOT_AVAILABLE_UNADMITTED_FUTURE_GRADE",
    }


def _lesson_selection_setup(
        current, prior, policy, *, seed, batch_size, targets,
        priority_target_ids, reserved_support_slots):
    if (not current or type(batch_size) is not int or
            batch_size < MIN_LESSON_BATCH_SIZE):
        raise ValueError(LessonSelectionError.EMPTY_TYPED_LESSON.value)
    if (type(reserved_support_slots) is not int or
            not 0 <= reserved_support_slots <= batch_size):
        raise ValueError(
            WeaknessTargetError.LEARNING_EXPERIMENT_SUPPORT_CAPACITY_INVALID.value)
    rng = random.Random(seed)
    requested_old = int(policy.get("old", 0))
    if not 0 <= requested_old <= POLICY_SCALE:
        raise ValueError(LessonSelectionError.INVALID_OLD_POLICY.value)
    target_ids = {row["id"] for row in targets}
    generic_current = [
        row for row in current if row.get("id") not in target_ids]
    if not generic_current:
        raise ValueError(
            LessonSelectionError.MISSING_FRESH_CURRENT_ROWS.value)
    semantic_patterns = sorted({
        tuple(row["operand_truths"]) for row in generic_current
        if isinstance(row.get("operand_truths"), list)
    })
    structured_binary = bool(semantic_patterns) and all(
        isinstance(row.get("operand_truths"), list) for row in generic_current)
    minimum_current = (
        len(semantic_patterns) if structured_binary else MIN_LESSON_BATCH_SIZE)
    old_count = min(
        batch_size-minimum_current,
        round(requested_old*batch_size/POLICY_SCALE)) if prior else 0
    present_count = batch_size-old_count
    choose_current = (
        _choose_binary_rows if structured_binary else _choose_typed_rows)
    current_ids = {row["id"] for row in current}
    if any(row.get("id") not in current_ids for row in targets):
        raise ValueError(
            WeaknessTargetError.
            LEARNING_EXPERIMENT_WEAKNESS_TARGET_OUTSIDE_CURRENT.value)
    priority_target_ids = set(priority_target_ids)
    if (any(not isinstance(identity, str) or not identity
            for identity in priority_target_ids) or
            not priority_target_ids <= target_ids):
        raise ValueError(LearningExperimentError.PRIORITY_TARGET_INVALID.value)
    return (
        rng, requested_old, generic_current, semantic_patterns,
        structured_binary, old_count, present_count, choose_current,
        priority_target_ids)


def select_source_lesson(current: list[dict], prior: list[dict], policy: dict,
                         *, seed: int, batch_size: int,
                         targets: list[dict] | tuple[dict, ...] = (),
                         priority_target_ids: set[str] | frozenset[str] = frozenset(),
                         target_exposures: Mapping[str, int] | None = None,
                         reserved_support_slots: int = 0
                         ) -> tuple[list[dict], dict]:
    """Make inherited old/contrast/depth knobs effective for every answer type."""
    (rng, requested_old, generic_current, semantic_patterns,
     structured_binary, old_count, present_count, choose_current,
     priority_target_ids) = _lesson_selection_setup(
        current, prior, policy, seed=seed, batch_size=batch_size,
        targets=targets, priority_target_ids=priority_target_ids,
        reserved_support_slots=reserved_support_slots)
    fresh_support = (
        _fresh_support_rows(
            generic_current, policy, rng,
            structured_binary=structured_binary,
            semantic_patterns=semantic_patterns,
            present_count=present_count,
            max_rows=max(0, batch_size-reserved_support_slots))
        if targets else ())
    free_current_slots = max(0, present_count - len(fresh_support))
    free_batch_slots_after_support = max(
        0, batch_size - len(fresh_support) - reserved_support_slots)
    target_capacity = min(
        free_current_slots, free_batch_slots_after_support)
    (priority_targets, selected_priority,
     selected_targets) = _selected_weakness_targets(
        targets, priority_target_ids, target_exposures, target_capacity)
    current_rows = choose_current(
        generic_current, present_count, policy, rng)
    current_rows, delivered_support = reserve_weakness_targets(
        current_rows, list(fresh_support))
    support_ids = {row["id"] for row in delivered_support}
    current_rows, delivered_targets = reserve_weakness_targets(
        current_rows, selected_targets, protected_ids=support_ids)
    result = current_rows + _choose_typed_rows(
        prior, old_count, policy, rng)
    rng.shuffle(result)
    delivered_patterns = (
        {tuple(row["operand_truths"]) for row in result
         if isinstance(row.get("operand_truths"), list)}
        if structured_binary else set())
    controls = _lesson_control_receipt(
        requested_old=requested_old, old_count=old_count, targets=targets,
        selected_targets=selected_targets, delivered_targets=delivered_targets,
        delivered_support=delivered_support, priority_targets=priority_targets,
        selected_priority=selected_priority,
        priority_target_ids=priority_target_ids,
        reserved_support_slots=reserved_support_slots,
        semantic_patterns=semantic_patterns,
        delivered_patterns=delivered_patterns, policy=policy)
    return (
        [{**row, "answer_kind": row.get("answer_kind", "binary")}
         for row in result],
        controls)
