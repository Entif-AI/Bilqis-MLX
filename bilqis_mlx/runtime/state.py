"""Canonical serialization and deterministic identities for durable school state."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import uuid

from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.curriculum.scheduler import (
    SchoolState, migrate_b_full_run_epoch, migrate_c_frontier_priority_epoch,
    verify_state,
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
    legacy_frontier_priority_epoch = (
        "frontier_priority_visits" not in school and
        "nongating_b_visits" not in school)
    legacy_b_full_run_epoch = "non_b_training_turns_since_b_run" not in school
    school.setdefault("main_sweep_visited", ())
    school.setdefault("carried_mastery_debt", ())
    school.setdefault("introduction_frontiers", ())
    school.setdefault("promotion_sweep_scope", ())
    school.setdefault("promotion_sweep_return_stage", None)
    school.setdefault("promotion_sweep_scores", ())
    school.setdefault("frontier_priority_visits", 0)
    school.setdefault("nongating_b_visits", 0)
    school.setdefault("non_b_training_turns_since_b_run", 0)
    for name in ("active_grades", "queue", "first_recovery", "pending_failures",
                 "main_sweep_visited", "carried_mastery_debt",
                 "promotion_sweep_scope"):
        school[name] = tuple(school[name])
    school["promotion_sweep_scores"] = tuple(
        (capability, correct, total)
        for capability, correct, total in school["promotion_sweep_scores"])
    school["introduction_frontiers"] = tuple(
        (grade, stage) for grade, stage in school["introduction_frontiers"])
    school["current_student"] = Checkpoint(**school["current_student"])
    school["champions"] = {key: Checkpoint(**item)
                           for key, item in school["champions"].items()}
    result = SchoolState(**school)
    if legacy_frontier_priority_epoch:
        result = migrate_c_frontier_priority_epoch(course, result)
    if legacy_b_full_run_epoch:
        result = migrate_b_full_run_epoch(course, result)
    verify_state(course, result)
    return result


def _seed(receipt: dict, *, capability: str, step: int = 0) -> int:
    return int(_fingerprint([receipt["run_id"], receipt["generation"],
                             capability, step])[:16], 16)
