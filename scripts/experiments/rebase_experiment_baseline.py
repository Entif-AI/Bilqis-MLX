#!/usr/bin/env python3
"""Rebase one manifested isolated experiment onto an existing local bundle clone.

Preview by default. --apply writes one new metadata generation only. The source
bundle and historical source state are read strictly as evidence. No neural
optimizer step is performed and the canonical source run is never mutated.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bilqis_mlx.backup import digest_file
from bilqis_mlx.learning.capability_frontier import promote
from bilqis_mlx.learning.epoch_championships import rebase_active_championships
from bilqis_mlx.trainer import (
    _persist,
    _reconcile_delivery_outbox,
    _verify_best_custody,
    _with_delivery_outbox,
    operator_lock,
)


EXPECTED_BUNDLE_FILES = (
    "manifest.json",
    "model-and-own-adamw.safetensors",
    "semantic-catalog.json",
)


def _bundle_hashes(path: Path) -> dict[str, str]:
    if path.is_symlink() or not path.is_dir():
        raise ValueError("EXPERIMENT_BASELINE_BUNDLE_UNSAFE")
    observed = tuple(sorted(member.name for member in path.iterdir()))
    if observed != tuple(sorted(EXPECTED_BUNDLE_FILES)):
        raise ValueError("EXPERIMENT_BASELINE_BUNDLE_CONTENT_DRIFT")
    result = {}
    for name in EXPECTED_BUNDLE_FILES:
        member = path / name
        if member.is_symlink() or not member.is_file():
            raise ValueError("EXPERIMENT_BASELINE_BUNDLE_FILE_UNSAFE")
        result[name] = digest_file(member)
    return result


def _compatible_state_contract(current: dict, historical: dict) -> None:
    fields = (
        "accepted_authority",
        "answer_ids",
        "config",
        "curriculum_mode",
        "semantic_graph_sha256",
        "source_manifest_sha256",
        "numeric_maximum",
    )
    if any(current.get(field) != historical.get(field) for field in fields):
        raise ValueError("EXPERIMENT_BASELINE_STATE_CONTRACT_DRIFT")
    if current["school"].get("course_digest") != historical["school"].get(
            "course_digest"):
        raise ValueError("EXPERIMENT_BASELINE_COURSE_DRIFT")


def _baseline_frontier(last_exam: dict, pointer: dict) -> dict:
    scores = last_exam.get("scores")
    rubric = last_exam.get("exam_rubric_sha256")
    evaluation = last_exam.get("evaluation_id")
    if not isinstance(scores, dict) or not scores or not rubric or not evaluation:
        raise ValueError("EXPERIMENT_BASELINE_EXAM_INCOMPLETE")
    roles = tuple(sorted(scores))
    return promote({}, scores, rubric, pointer, evaluation, roles)


def _baseline_peak(historical: dict, baseline_sha: str) -> list[dict]:
    peaks = [
        deepcopy(item) for item in historical.get("whole_student_peaks", ())
        if item.get("checkpoint", {}).get("sha256") == baseline_sha
    ]
    if len(peaks) != 1:
        raise ValueError("EXPERIMENT_BASELINE_PEAK_NOT_UNIQUE")
    return peaks


def _independent_local_clone(source_bundle: Path, local_bundle: Path) -> dict:
    source_hashes = _bundle_hashes(source_bundle)
    local_hashes = _bundle_hashes(local_bundle)
    if source_hashes != local_hashes:
        raise ValueError("EXPERIMENT_BASELINE_LOCAL_CLONE_DIFFERS_FROM_SOURCE")
    source_model = source_bundle / "model-and-own-adamw.safetensors"
    local_model = local_bundle / "model-and-own-adamw.safetensors"
    if os.stat(source_model).st_ino == os.stat(local_model).st_ino:
        raise ValueError("EXPERIMENT_BASELINE_LOCAL_CLONE_IS_HARDLINK")
    return source_hashes


def _resolve_inputs(run_dir: Path, source_bundle: Path, source_state: Path):
    run_dir = run_dir.expanduser().resolve(strict=True)
    source_bundle = source_bundle.expanduser().resolve(strict=True)
    source_state = source_state.expanduser().resolve(strict=True)
    fork_manifest = run_dir.with_name(run_dir.name + ".fork-manifest.json")
    if (run_dir.parent != (ROOT / "runs").resolve() or
            not fork_manifest.is_file()):
        raise ValueError("EXPERIMENT_BASELINE_REBASE_REQUIRES_MANIFESTED_FORK")

    local_bundle = run_dir / "bundles" / source_bundle.name
    source_hashes_before = _independent_local_clone(source_bundle, local_bundle)
    manifest = json.loads((source_bundle / "manifest.json").read_text(encoding="utf-8"))
    historical = json.loads(source_state.read_text(encoding="utf-8"))
    historical_pointer = historical["school"]["current_student"]
    if (historical_pointer.get("filename") != "bundles/" + source_bundle.name or
            historical_pointer.get("sha256") != manifest.get("safetensors_sha256") or
            historical_pointer.get("optimizer_step") != manifest.get("optimizer_step") or
            historical_pointer.get("model_and_native_adamw") is not True):
        raise ValueError("EXPERIMENT_BASELINE_HISTORICAL_POINTER_MISMATCH")

    historical_run = source_state.parent.parent
    cohort_file = historical_run / historical["last_exam"]["cohort_file"]
    local_cohort = run_dir / historical["last_exam"]["cohort_file"]
    if (not cohort_file.is_file() or cohort_file.is_symlink() or
            not local_cohort.is_file() or local_cohort.is_symlink() or
            digest_file(cohort_file) != digest_file(local_cohort)):
        raise ValueError("EXPERIMENT_BASELINE_COHORT_CLONE_DRIFT")
    return (run_dir, source_bundle, source_state, local_bundle,
            source_hashes_before, historical, historical_pointer)


def _baseline_exam(historical: dict) -> dict:
    last_exam = deepcopy(historical["last_exam"])
    # Historical scoring remains valid evidence. Old promotion side effects
    # are not replayed into this newly rebased epoch.
    last_exam["incumbent_comparisons"] = []
    last_exam["graduation_perfect_roles"] = []
    last_exam["grade_soups_refreshed"] = []
    last_exam["championship_decisions"] = []
    last_exam["experimental_baseline_reference"] = True
    return last_exam


def _build_record(receipt: dict, historical: dict, source_bundle: Path) -> dict:
    epoch = receipt.get("mentor_epoch")
    if not isinstance(epoch, dict):
        raise ValueError("EXPERIMENT_BASELINE_ACTIVE_EPOCH_REQUIRED")
    school = deepcopy(historical["school"])
    baseline = deepcopy(historical["school"]["current_student"])
    school["current_student"] = baseline
    last_exam = _baseline_exam(historical)
    rebased_epoch = rebase_active_championships(
        epoch, prior_student=receipt["school"]["current_student"],
        baseline=baseline, generation=receipt["generation"])
    correct = sum(score["correct"] for score in last_exam["scores"].values())
    total = sum(score["total"] for score in last_exam["scores"].values())
    record = {
        **receipt,
        "generation": receipt["generation"] + 1,
        "school": school,
        "model_bundle": baseline["filename"],
        "last_exam": last_exam,
        "qualification_cohort": deepcopy(historical["qualification_cohort"]),
        "teacher_misses": deepcopy(historical.get("teacher_misses", [])),
        "teacher_miss_exposures": deepcopy(
            historical.get("teacher_miss_exposures", {})),
        "whole_student_peaks": _baseline_peak(historical, baseline["sha256"]),
        "capability_best": _baseline_frontier(last_exam, baseline),
        "mentor_epoch": rebased_epoch,
        "live_rubric_sha256": last_exam["exam_rubric_sha256"],
        "legacy_frontier_pending_replay": False,
        "result": historical.get("result", "ACTIVE_GRADE_" + school[
            "active_grades"][school["grade_index"]]),
        "experimental_baseline_rebase": {
            "schema": "bilqis.mlx.experimental-baseline-rebase/v1",
            "source_bundle_name": source_bundle.name,
            "source_state_generation": historical["generation"],
            "prior_experiment_generation": receipt["generation"],
            "prior_student_sha256": receipt["school"]["current_student"]["sha256"],
            "baseline_sha256": baseline["sha256"],
            "baseline_optimizer_step": baseline["optimizer_step"],
            "baseline_exam_cohort_sha256": last_exam["cohort_sha256"],
            "baseline_exam_correct": correct,
            "baseline_exam_total": total,
            "active_championship_roles_after": 0,
            "active_championship_soups_after": 0,
            "baseline_challenge_required": False,
            "source_bundle_read_only": True,
            "neural_updates": 0,
        },
    }
    record.pop("_pending_visit_events", None)
    event = {
        "event": "SCHOOL_EXPERIMENT_BASELINE_REBASED",
        "generation": record["generation"],
        "source_generation": historical["generation"],
        "prior_student_sha256": receipt["school"]["current_student"]["sha256"],
        "student_sha256": baseline["sha256"],
        "optimizer_step": baseline["optimizer_step"],
        "active_championship_roles": 0,
        "active_championship_soups": 0,
        "baseline_challenge_required": False,
        "source_bundle_unchanged": True,
        "neural_updates": 0,
    }
    return _with_delivery_outbox(record, (event,))


def _preview(receipt, record, historical, source_bundle, source_state,
             local_bundle, source_hashes_before):
    baseline = record["school"]["current_student"]
    metadata = record["experimental_baseline_rebase"]
    return {
        "mode": "ISOLATED_EXPERIMENT_BASELINE_REBASE",
        "applied": False,
        "source_bundle": str(source_bundle),
        "local_bundle": str(local_bundle),
        "source_state": str(source_state),
        "source_hashes_before": source_hashes_before,
        "source_and_local_bundle_hashes_match": True,
        "source_and_local_model_inodes_distinct": True,
        "source_generation": historical["generation"],
        "prior_experiment_generation": receipt["generation"],
        "next_generation": record["generation"],
        "baseline_sha256": baseline["sha256"],
        "baseline_optimizer_step": baseline["optimizer_step"],
        "baseline_exam_correct": metadata["baseline_exam_correct"],
        "baseline_exam_total": metadata["baseline_exam_total"],
        "school_stage": record["school"]["stage"],
        "school_queue": list(record["school"]["queue"]),
        "active_championship_roles_after": 0,
        "active_championship_soups_after": 0,
        "baseline_challenge_required": False,
        "neural_updates": 0,
    }


def _apply_record(run_dir, source_bundle, source_hashes_before, record, preview):
    successor = run_dir / "states" / f"{record['generation']:07d}.json"
    if successor.exists() or successor.is_symlink():
        raise ValueError("EXPERIMENT_BASELINE_PENDING_STATE_RECONCILIATION_REQUIRED")
    saved = _persist(run_dir, record)
    _reconcile_delivery_outbox(run_dir, saved)
    if json.loads((run_dir / "state.json").read_text(encoding="utf-8")) != saved:
        raise ValueError("EXPERIMENT_BASELINE_POSTWRITE_STATE_DRIFT")
    source_hashes_after = _bundle_hashes(source_bundle)
    if source_hashes_after != source_hashes_before:
        raise ValueError("EXPERIMENT_BASELINE_SOURCE_MUTATED")
    return {
        **preview,
        "applied": True,
        "generation": saved["generation"],
        "source_hashes_after": source_hashes_after,
        "source_unchanged": True,
    }


def prepare(run_dir: Path, source_bundle: Path, source_state: Path, *,
            apply: bool = False) -> dict:
    (run_dir, source_bundle, source_state, local_bundle, source_hashes_before,
     historical, _) = _resolve_inputs(run_dir, source_bundle, source_state)
    with operator_lock(run_dir):
        receipt = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        _compatible_state_contract(receipt, historical)
        record = _build_record(receipt, historical, source_bundle)
        _verify_best_custody(run_dir, record)
        preview = _preview(
            receipt, record, historical, source_bundle, source_state,
            local_bundle, source_hashes_before)
        if not apply:
            return preview
        return _apply_record(
            run_dir, source_bundle, source_hashes_before, record, preview)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--source-bundle", required=True, type=Path)
    parser.add_argument("--source-state", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(prepare(
        args.run_dir, args.source_bundle, args.source_state, apply=args.apply),
        indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
