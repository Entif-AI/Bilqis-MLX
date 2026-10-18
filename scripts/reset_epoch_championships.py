#!/usr/bin/env python3
"""Reset only active championship teaching rights on an existing isolated run.

Preview by default. --apply commits one new metadata-only state generation
with an outbox receipt. Never copy or modify the student or native AdamW.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from bilqis_mlx.epoch_championships import reset_active_championships
from bilqis_mlx.trainer import (
    _persist, _reconcile_delivery_outbox, _verify_best_custody,
    _with_delivery_outbox, operator_lock,
)


def prepare(run_dir: Path, *, apply: bool = False) -> dict:
    root = Path(__file__).resolve().parents[1]
    run_dir = run_dir.expanduser().resolve(strict=True)
    if (run_dir.parent != (root / "runs").resolve() or
            not run_dir.with_name(run_dir.name + ".fork-manifest.json").is_file()):
        raise ValueError("CHAMPIONSHIP_RESET_REQUIRES_MANIFESTED_ISOLATED_RUN")
    with operator_lock(run_dir):
        receipt = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        epoch = receipt.get("mentor_epoch")
        if epoch is None:
            raise ValueError("CHAMPIONSHIP_RESET_NO_ACTIVE_EPOCH")
        student = receipt["school"]["current_student"]
        updated, change = reset_active_championships(
            epoch, student=student, generation=receipt["generation"])
        marker = updated.get("active_championship_reset", {})
        result = {
            "mode": "FORK_ONLY_ZERO_ACTIVE_CHAMPIONSHIP_RESET",
            "source_generation": receipt["generation"],
            "student_sha256": student["sha256"],
            "optimizer_step": student["optimizer_step"],
            "active_roles_after": len(updated.get("active_roles", {})),
            "active_soups_after": len(updated.get("active_grade_soups", {})),
            "active_baseline_advisers_after": 0,
            "historical_roles_preserved": len(receipt.get("graduation_perfect", {})),
            "historical_soup_grades_preserved": sorted(receipt.get("grade_soups", {})),
            "pre_reset_active_roles_archived": marker.get("old_active_role_count"),
            "pre_reset_active_soups_archived": marker.get("old_active_soup_grades"),
            "model_or_native_adamw_updates": 0,
            "already_reset": not change,
            "applied": False,
        }
        if not apply or not change:
            return result
        successor = run_dir / "states" / f"{receipt['generation']+1:07d}.json"
        if successor.exists() or successor.is_symlink():
            raise ValueError("CHAMPIONSHIP_RESET_PENDING_STATE_RECONCILIATION_REQUIRED")
        record = {**receipt, "generation": receipt["generation"] + 1,
                  "mentor_epoch": updated}
        event = {
            "event": "SCHOOL_EPOCH_CHAMPIONSHIPS_RESET_EMPTY",
            "generation": record["generation"],
            "source_generation": receipt["generation"],
            "student_sha256": student["sha256"],
            "optimizer_step": student["optimizer_step"],
            "displaced_active_roles_archived": marker["old_active_role_count"],
            "displaced_active_soup_grades_archived": marker["old_active_soup_grades"],
            "active_champions": 0, "active_soup_votes": 0,
            "active_baseline_advisers": 0,
            "student_and_own_adamw_unchanged": True,
            "neural_updates": 0,
        }
        record = _with_delivery_outbox(record, (event,))
        _verify_best_custody(run_dir, record)
        saved = _persist(run_dir, record)
        _reconcile_delivery_outbox(run_dir, saved)
        if json.loads((run_dir / "state.json").read_text()) != saved:
            raise ValueError("CHAMPIONSHIP_RESET_POSTWRITE_STATE_DRIFT")
        return {**result, "applied": True, "generation": saved["generation"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--apply", action="store_true",
                        help="Commit the forward-only metadata reset.")
    args = parser.parse_args()
    print(json.dumps(prepare(args.run_dir, apply=args.apply),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
