"""Read-only replay of championship candidates suppressed by old quarantine routing.

This audit reads durable JSON receipts only. It never loads model tensors, calls
inference, mutates run state, or starts training.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path


SETTLED = {"TITLE_WON", "TITLE_DEFENDED"}


def _pair_key(capability: str, left: str, right: str) -> str:
    return capability + "|" + "|".join(sorted((left, right)))


def _read_events(run_dir: Path) -> list[dict]:
    with (run_dir / "events.jsonl").open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _checkpoint_origins(events: list[dict]) -> tuple[dict[str, str], set[str]]:
    observed: dict[str, set[str]] = defaultdict(set)
    for event in events:
        if (event.get("event") == "SCHOOL_TEACHER_VISIT_COMMITTED" and
                event.get("retained_optimizer_updates", 0) > 0 and
                isinstance(event.get("recovered_at_student_sha256"), str) and
                isinstance(event.get("grade"), str)):
            observed[event["recovered_at_student_sha256"]].add(event["grade"])
    proven = {sha: next(iter(grades)) for sha, grades in observed.items()
              if len(grades) == 1}
    ambiguous = {sha for sha, grades in observed.items() if len(grades) != 1}
    return proven, ambiguous


def audit(run_dir: Path, *, before_generation: int | None = None) -> dict:
    """Classify old silent 12/12 cases from immutable state and event evidence."""
    run_dir = Path(run_dir).resolve()
    events = _read_events(run_dir)
    origins, ambiguous = _checkpoint_origins(events)
    by_generation: dict[int, list[dict]] = defaultdict(list)
    for event in events:
        generation = event.get("generation")
        if type(generation) is int:
            by_generation[generation].append(event)

    prior_settled: dict[str, dict] = {}
    candidates = []
    withheld = []
    best_events = [event for event in events
                   if event.get("event") == "SCHOOL_CAPABILITY_BEST_COMMITTED"]
    best_by_generation: dict[int, list[dict]] = defaultdict(list)
    for event in best_events:
        best_by_generation[event["generation"]].append(event)

    generations = sorted(set(by_generation) | set(best_by_generation))
    for generation in generations:
        if before_generation is not None and generation >= before_generation:
            break
        for event in by_generation.get(generation, ()):
            epoch = event.get("championship_epoch")
            if not isinstance(epoch, dict):
                continue
            for decision in epoch.get("cross_origin_decisions", ()) or ():
                if decision.get("decision") not in SETTLED:
                    continue
                capability = decision.get("capability")
                left = decision.get("incumbent_sha256")
                right = decision.get("challenger_sha256")
                if all(isinstance(value, str) and value for value in
                       (capability, left, right)):
                    prior_settled.setdefault(_pair_key(capability, left, right), decision)

        state_path = run_dir / "states" / f"{generation:07d}.json"
        if not state_path.is_file():
            continue
        state = json.loads(state_path.read_text(encoding="utf-8"))
        current = (state.get("school") or {}).get("current_student") or {}
        quarantine = (state.get("stagnation_session") or {}).get("quarantined") or {}
        quarantine = set(quarantine if isinstance(quarantine, dict) else quarantine)
        if not quarantine:
            continue
        for event in best_by_generation.get(generation, ()):
            challenger = event.get("student_sha256")
            origin = origins.get(challenger)
            if (current.get("sha256") != challenger or
                    current.get("optimizer_step") != event.get("optimizer_step")):
                continue
            if challenger in ambiguous or origin is None:
                continue
            exams = [item for item in by_generation.get(generation, ())
                     if "LIVE_EXAM_COMMITTED" in item.get("event", "") and
                     item.get("student_sha256") == challenger]
            decisions = [decision for exam in exams
                         for decision in ((exam.get("championship_epoch") or {}).get(
                             "cross_origin_decisions", ()) or ())]
            decided = {decision.get("capability") for decision in decisions}
            roles = (state.get("mentor_epoch") or {}).get("active_roles", {})
            epoch = state.get("mentor_epoch") or {}
            floor = epoch.get("championship_eligibility_after_step", -1)
            if type(floor) is int and event.get("optimizer_step", -1) <= floor:
                continue
            identity_missing = (
                not isinstance(state.get("championship_school_identity"), dict) or
                not isinstance(epoch.get("championship_school_identity"), dict))

            scores = event.get("scores", {})
            explicitly_withheld = {
                capability
                for exam in exams
                for capability in exam.get("withheld_capabilities", ())
            }
            for capability in sorted(quarantine & explicitly_withheld):
                withheld.append({
                    "generation": generation,
                    "student_sha256": challenger,
                    "capability": capability,
                    "classification": "NOT_MEASURED",
                })
            for capability, score in scores.items():
                grade = capability.partition(".")[0]
                if (capability in explicitly_withheld or origin != grade or
                        score.get("correct") != score.get("total") or
                        score.get("total") != 12 or capability in decided):
                    continue
                role = roles.get(capability)
                if identity_missing:
                    classification = "ROLE_MINT_AFTER_HOLISTIC_RESET"
                    incumbent = None
                elif role is None:
                    classification = "ROLE_MINT"
                    incumbent = None
                else:
                    incumbent = (role.get("checkpoint") or {}).get("sha256")
                    incumbent_origin = origins.get(incumbent)
                    if incumbent in ambiguous or incumbent_origin != grade:
                        classification = "ROLE_MINT_AFTER_INVALID_ORIGIN_ARCHIVE"
                    elif incumbent == challenger:
                        continue
                    elif _pair_key(capability, incumbent, challenger) in prior_settled:
                        classification = "PAIR_ALREADY_SETTLED"
                    else:
                        classification = "TITLE_MATCH_REQUIRED"
                candidates.append({
                    "generation": generation,
                    "optimizer_step": event.get("optimizer_step"),
                    "student_sha256": challenger,
                    "origin_grade": origin,
                    "capability": capability,
                    "classification": classification,
                    "incumbent_sha256": incumbent,
                    "quarantined_capabilities": sorted(quarantine),
                    "observed_championship_decisions": len(decisions),
                })

    counts: dict[str, int] = defaultdict(int)
    for item in candidates:
        counts[item["classification"]] += 1
    counts["NOT_MEASURED"] = len(withheld)
    return {
        "schema": "bilqis.mlx.championship-quarantine-audit/v1",
        "run_dir": str(run_dir),
        "before_generation": before_generation,
        "checkpoint_origins_proven": len(origins),
        "checkpoint_origins_ambiguous": len(ambiguous),
        "classification_counts": dict(sorted(counts.items())),
        "silent_measured_candidates": candidates,
        "withheld_not_measured": withheld,
        "neural_inference_calls": 0,
        "state_writes": 0,
        "optimizer_updates": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--before-generation", type=int)
    parser.add_argument("--example-limit", type=int, default=20)
    args = parser.parse_args()
    result = audit(args.run_dir, before_generation=args.before_generation)
    limit = args.example_limit
    result["silent_measured_candidates"] = result["silent_measured_candidates"][-limit:]
    result["withheld_not_measured"] = result["withheld_not_measured"][-limit:]
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
