"""Canonical serialization and deterministic identities for durable school state."""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus, SCHOOL

import hashlib
import json
import os
from pathlib import Path
import uuid

from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.curriculum.scheduler import (
    DebtCadencePolicy, SchoolState, migrate_legacy_debt_cadence_epoch,
    migrate_legacy_debt_cadence_policy, migrate_legacy_debt_cadence_queue,
    _restore_debt_counter_fields, verify_state,
)
from bilqis_mlx.curriculum.promotion import (
    migrate_promotion_sweep_attempt_epoch, restore_promotion_attempt_fields,
)

def _canonical(data: object) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def _fingerprint(data: object) -> str:
    return hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()


def _durable_json(path: Path, data: dict, *, replace_existing=False):
    """fsync temporary bytes and containing folder; retain old state receipts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    with tmp.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False,
                                allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    if replace_existing:
        os.replace(tmp, path)
    else:
        try:
            os.link(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _state_from_json(value: dict, course) -> SchoolState:
    school = dict(value)
    role_neutral_debt_state = (
        "bounded_debt_visits" in school or
        "priority_visits_since_bounded_debt" in school)
    legacy_bounded_counter_epoch, legacy_priority_visit_epoch = (
        _restore_debt_counter_fields(school))
    legacy_frontier_priority_epoch = (
        "frontier_priority_visits" not in school and legacy_bounded_counter_epoch)
    legacy_debt_cadence_policy = (
        school.get("debt_cadence_policy") is None and
        not role_neutral_debt_state)
    legacy_promotion_sweep_attempt_epoch = restore_promotion_attempt_fields(school)
    school.setdefault("main_sweep_visited", ())
    school.setdefault("frontier_catchup_passes", 0)
    school.setdefault("carried_mastery_debt", ())
    school.setdefault("mature_capability_debt", ())
    school.setdefault("mature_grade_debt", ())
    school.setdefault("introduction_frontiers", ())
    school.setdefault("promotion_sweep_scope", ())
    school.setdefault("promotion_sweep_return_stage", None)
    school.setdefault("promotion_sweep_scores", ())
    school.setdefault("promotion_sweep_retry_scores", ())
    school.setdefault("frontier_priority_visits", 0)
    policy_value = school.get("debt_cadence_policy")
    if policy_value is not None:
        if not isinstance(policy_value, dict):
            raise ErrorBus.legacy_error(SCHOOL.SCHEDULE.INVALID_DEBT_CADENCE_POLICY)
        school["debt_cadence_policy"] = DebtCadencePolicy(**policy_value)
    else:
        school["debt_cadence_policy"] = None
    for name in ("active_grades", "queue", "first_recovery", "pending_failures",
                 "main_sweep_visited", "carried_mastery_debt",
                 "promotion_sweep_scope", "promotion_sweep_attempt_scope"):
        school[name] = tuple(school[name])
    school["mature_capability_debt"] = tuple(
        (capability, amount)
        for capability, amount in school["mature_capability_debt"])
    school["mature_grade_debt"] = tuple(
        (grade, amount) for grade, amount in school["mature_grade_debt"])
    if not school["mature_grade_debt"] and school["mature_capability_debt"]:
        totals = {}
        for capability, amount in school["mature_capability_debt"]:
            grade = capability.partition(".")[0]
            totals[grade] = totals.get(grade, 0) + amount
        school["mature_grade_debt"] = tuple(sorted(totals.items()))
        school["mature_capability_debt"] = ()
    school["promotion_sweep_scores"] = tuple(
        (capability, correct, total)
        for capability, correct, total in school["promotion_sweep_scores"])
    school["promotion_sweep_retry_scores"] = tuple(
        (capability, correct, total)
        for capability, correct, total in school["promotion_sweep_retry_scores"])
    attempt_scope = set(school["promotion_sweep_attempt_scope"])
    if any(capability not in attempt_scope
           for capability, _correct, _total in school["promotion_sweep_retry_scores"]):
        school["promotion_sweep_retry_scores"] = ()
    school["introduction_frontiers"] = tuple(
        (grade, stage) for grade, stage in school["introduction_frontiers"])
    school["current_student"] = Checkpoint(**school["current_student"])
    school["champions"] = {key: Checkpoint(**item)
                           for key, item in school["champions"].items()}
    result = SchoolState(**school)
    if legacy_debt_cadence_policy:
        result = migrate_legacy_debt_cadence_policy(course, result)
    if legacy_frontier_priority_epoch:
        result = migrate_legacy_debt_cadence_queue(course, result)
    if legacy_priority_visit_epoch:
        result = migrate_legacy_debt_cadence_epoch(course, result)
    if legacy_promotion_sweep_attempt_epoch:
        result = migrate_promotion_sweep_attempt_epoch(course, result)
    verify_state(course, result)
    return result


def _seed(receipt: dict, *, capability: str, step: int = 0) -> int:
    return int(_fingerprint([receipt.get("qualification_training_seed", receipt["run_id"]), receipt["generation"],
                             capability, step])[:16], 16)
