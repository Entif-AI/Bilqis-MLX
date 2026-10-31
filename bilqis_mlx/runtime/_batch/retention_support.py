"""Structural extraction from candidate_evidence.py; behavior preserved."""
from __future__ import annotations
from bilqis_mlx.errors import ErrorBus, SOURCE
import bilqis_mlx.curriculum.scheduler as _curriculum_scheduler
import bilqis_mlx.profiles.retention as _profiles_retention
import bilqis_mlx.runtime.assessment as _runtime_assessment
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.state as _runtime_state

def _retention_support_capabilities(admitted, active_grades,
                                    capability: str) -> tuple[str, ...]:
    """Return fresh-source support matching the surfaces retention protects."""
    admitted = tuple(admitted)
    active_grades = tuple(active_grades)
    if (not active_grades or not isinstance(capability, str) or
            "." not in capability):
        return ()
    protected_grades = set(active_grades)
    return tuple(sorted(
        name for name in admitted
        if name != capability and name.partition(".")[0] in protected_grades))

def _retention_support_schedule(
        admitted, active_grades, capability: str, *, steps: int,
        rotation: int = 0, already_preserved=()) -> tuple[str, ...]:
    """Spend support steps first on the grade surfaces that can veto admission.

    The fresh lesson grade and latest active frontier are explicit retention
    gates.  Earlier grades already receive the teacher's ordinary old-grade
    rehearsal, while fragile capabilities can have a separate preservation
    channel.  Do not dilute a short candidate across every admitted capability
    before these hard-gated surfaces have been rehearsed.
    """
    if type(steps) is not int or steps < 1 or type(rotation) is not int or rotation < 0:
        raise ValueError("RETENTION_SUPPORT_SCHEDULE_INVALID")
    active_grades = tuple(active_grades)
    if not active_grades:
        return ()
    preserved = set(already_preserved)
    available = tuple(
        name for name in _retention_support_capabilities(
            admitted, active_grades, capability)
        if name not in preserved)
    if not available:
        return ()
    lesson_grade = capability.partition(".")[0]
    frontier_grade = active_grades[-1]
    priority = tuple(
        name for name in available
        if name.partition(".")[0] in {lesson_grade, frontier_grade})
    available = priority or available
    start = (rotation * steps) % len(available)
    return tuple(
        available[(start + index) % len(available)]
        for index in range(steps))

def _select_fresh_retention_support_rows(
        rows, *, rotation: int) -> tuple[dict, ...]:
    """Choose one complete fresh source family for preservation rehearsal."""
    if type(rotation) is not int or rotation < 0:
        raise ErrorBus.legacy_error(SOURCE.REPLAY.RETENTION_SUPPORT_ROTATION_INVALID)
    groups = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ErrorBus.legacy_error(SOURCE.REPLAY.RETENTION_SUPPORT_ROW_INVALID)
        groups.setdefault(row.get("source_id", row["id"]), []).append(row)
    if not groups:
        return ()
    keys = sorted(groups, key=str)
    return tuple(groups[keys[rotation % len(keys)]])

def _fresh_fragile_preservation_rows(run_dir, source_root, graph, receipt,
                                     course, school, capability, *, step,
                                     batch_size, fixed_rows=None,
                                     executable_release=None):
    """Generate fresh semantic siblings for the configured fragile safety rows.

    Rehearsal is active only after a source-verified replay exam exists.
    The fixed examination rows themselves are never delivered to the optimizer.
    """
    from bilqis_mlx.learning.fragile_replay import load_replay_rows, fresh_preservation_rows
    policy = _profiles_retention.fragile_preservation_policy()
    fixed = (tuple(fixed_rows) if fixed_rows is not None else
             load_replay_rows(run_dir, receipt, capabilities=policy.capabilities))
    if not fixed:
        return ()
    admitted = set(_curriculum_scheduler.assessment_capabilities(
        _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course), school))
    requested = tuple(name for name in policy.capabilities if name in admitted)
    return fresh_preservation_rows(
        fixed, capabilities=requested, rotation=max(0, step - 1) * policy.per_capability_target,
        batch_size=batch_size, retention_policy=policy,
        seed_for=lambda name, attempt: _runtime_state._seed(
            receipt, capability=f"FRAGILE_PRESERVE:{name}:{attempt}", step=step),
        draw_rows=lambda **kwargs: _runtime_assessment._draw_live_rows(
            source_root, graph, executable_release=executable_release, course=course, **kwargs))

def _inject_preservation_rows(chosen, preservation, *, reserved_ids=()):
    """Reserve preservation slots without displacing selected weakness targets."""
    result = list(chosen)
    reserved = set(reserved_ids)
    consumed = set()
    for index, row in enumerate(result):
        identity = row.get("id")
        if identity in reserved:
            consumed.add(index)
            reserved.remove(identity)
    delivered = []
    for item in preservation:
        replacement = next((
            index for index, row in enumerate(result)
            if index not in consumed and row.get("gold") == item.get("gold")
        ), None)
        if replacement is None:
            replacement = next((
                index for index in range(len(result)) if index not in consumed
            ), None)
        if replacement is None:
            break
        result[replacement] = item
        consumed.add(replacement)
        delivered.append(item)
    if len(delivered) != len(preservation):
        raise ValueError("FRAGILE_PRESERVATION_BATCH_CAPACITY_EXHAUSTED")
    return result, tuple(delivered)
