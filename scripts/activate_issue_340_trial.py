#!/usr/bin/env python3
"""Prepare, or explicitly activate, a frozen mentor epoch on an isolated fork.

Human-run neural training remains human-only. The command creates at most one
new *fork-local* state generation and generation-bound event; never modifies
student or optimizer tensors. No original-run mutation or cleanup.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from bilqis_mlx.trainer import (
    _fingerprint, _mentor_sources_for_visit, _persist, _reconcile_delivery_outbox,
    _verify_best_custody, _with_delivery_outbox, operator_lock,
)
from bilqis_mlx.mentor_epoch import begin_epoch
from bilqis_mlx.mlx_checkpoint import load_semantically_bound_bundle


def _graduation(run_dir, step):
    seen = []
    with (run_dir / "events.jsonl").open() as stream:
        for line in stream:
            event = json.loads(line)
            if (event.get("event") == "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED" and
                    event.get("optimizer_step") == step):
                seen.append(event)
    if len(seen) != 1:
        raise ValueError("MENTOR_TRIAL_GRADUATION_EXAM_AMBIGUOUS")
    exam = seen[0]
    scores = exam["scores"]
    if (len(scores) != 12 or set(cap.partition(".")[0] for cap in scores) !=
            {"A", "B"} or any(item["correct"] != item["total"] for item in scores.values())):
        raise ValueError("MENTOR_TRIAL_GRADUATION_NOT_COMPLETE")
    matches = []
    for manifest_file in (run_dir / "bundles").glob("*/manifest.json"):
        pointer = json.loads(manifest_file.read_text())
        if (pointer.get("safetensors_sha256") == exam["student_sha256"] and
                pointer.get("optimizer_step") == step):
            matches.append({"filename": "bundles/" + manifest_file.parent.name,
                            "sha256": exam["student_sha256"],
                            "optimizer_step": step, "model_and_native_adamw": True})
    if len(matches) != 1:
        raise ValueError("MENTOR_TRIAL_GRADUATE_BUNDLE_MISSING_OR_AMBIGUOUS")
    return matches[0], {"checkpoint_sha256": exam["student_sha256"],
                        "cohort_sha256": exam["cohort_sha256"],
                        "rubric_sha256": exam["rubric"], "scores": scores}


def prepare(run_dir: Path, *, graduation_step: int, activate: bool) -> dict:
    root = Path(__file__).resolve().parents[1]
    run_dir = run_dir.expanduser().resolve(strict=True)
    if (run_dir.parent != (root / "runs").resolve() or
            not run_dir.with_name(run_dir.name + ".fork-manifest.json").is_file()):
        raise ValueError("MENTOR_TRIAL_REQUIRES_OWN_MANIFESTED_RUN")
    with operator_lock(run_dir):
        receipt = json.loads((run_dir / "state.json").read_text())
        if receipt.get("mentor_epoch") is not None:
            raise ValueError("MENTOR_TRIAL_ALREADY_ACTIVATED")
        student = receipt["school"]["current_student"]
        previous, exam = _graduation(run_dir, graduation_step)
        weights, own_adamw, metadata, graph = load_semantically_bound_bundle(
            run_dir / student["filename"])
        if (metadata["optimizer_step"] != student["optimizer_step"] or
                metadata["safetensors_sha256"] != student["sha256"] or
                _fingerprint(graph) != receipt["semantic_graph_sha256"]):
            raise ValueError("MENTOR_TRIAL_SOURCE_STUDENT_DRIFT")
        del weights, own_adamw
        epoch = begin_epoch(
            previous_graduate=previous, admitted_baseline=student,
            introduced_grade="C", source_graph_sha256=_fingerprint(graph),
            previous_capabilities=tuple(exam["scores"]),
            previous_graduation_exam=exam)
        epoch["experimental_refresh"] = "MID_GRADE_FROZEN_CURRENT_STUDENT"
        trial = {**receipt, "mentor_epoch": epoch}
        mentors, soups, _ = _mentor_sources_for_visit(
            run_dir, trial, "C", graph, len(receipt["school"]["active_grades"]))
        if mentors or soups:
            raise ValueError("MENTOR_TRIAL_UNEXPECTED_ACTIVE_ADVISERS")
        result = {"mode": "FORK_ONLY_MENTOR_POLICY_TRIAL",
                  "previous_AB_graduate": previous,
                  "frozen_baseline": student,
                  "active_advisers": 0, "active_historical_soups": 0,
                  "source_generation": receipt["generation"],
                  "neural_updates": 0, "activated": False}
        if not activate:
            return result
        record = {**trial, "generation": receipt["generation"] + 1}
        event = {"event": "SCHOOL_FORK_MENTOR_EPOCH_TRIAL_ACTIVATED",
                 "generation": record["generation"],
                 "student_sha256": student["sha256"],
                 "optimizer_step": student["optimizer_step"],
                 "historical_soups_preserved": True, "neural_updates": 0}
        record = _with_delivery_outbox(record, (event,))
        _verify_best_custody(run_dir, record)
        written = _persist(run_dir, record)
        _reconcile_delivery_outbox(run_dir, written)
        if json.loads((run_dir / "state.json").read_text()) != written:
            raise ValueError("MENTOR_TRIAL_POSTWRITE_STATE_DRIFT")
        return {**result, "activated": True,
                "trial_generation": record["generation"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--graduation-step", type=int, required=True)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    print(json.dumps(prepare(args.run_dir, graduation_step=args.graduation_step,
                             activate=args.activate), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
