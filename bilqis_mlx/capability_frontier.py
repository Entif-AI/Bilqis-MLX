"""Best-score capability pointers, independent of 100%-grade admission.

The active student is never selected by mixing these winners.  Each entry
references an *entire* FP32 student with its matching AdamW optimizer.
Rubric IDs are part of identity: scores from different tests never compete.
"""
from __future__ import annotations

import json
from pathlib import Path


def _key(rubric: str, capability: str) -> str:
    if len(rubric) != 64 or not capability:
        raise ValueError("CAPABILITY_FRONTIER_RUBRIC_IDENTITY_MISSING")
    return rubric + ":" + capability


def _score(value: dict) -> tuple[int, int]:
    right, total = value["correct"], value["total"]
    if (type(right) is not int or type(total) is not int or
            total <= 0 or not 0 <= right <= total):
        raise ValueError("CAPABILITY_FRONTIER_INVALID_SCORE")
    return right, total


def candidate_roles(frontier: dict, scores: dict, rubric: str) -> tuple[str, ...]:
    """Qualify *before* writing a candidate binary.

    Strict gains qualify. Tied best slots may also transfer to a single
    candidate already qualified by a gain, or when doing so collapses
    multiple separately stored champion checkpoints into one.
    """
    if not scores:
        raise ValueError("CAPABILITY_FRONTIER_EMPTY_TEST")
    previously_measured = {item["capability"] for item in frontier.values()
                           if item["rubric"] == rubric}
    if previously_measured and not previously_measured <= set(scores):
        raise ValueError("CAPABILITY_FRONTIER_INCOMPLETE_RUBRIC")
    gain, tied = set(), set()
    for cap, score in scores.items():
        right, total = _score(score)
        previous = frontier.get(_key(rubric, cap))
        if previous is None:
            gain.add(cap)
            continue
        old, old_total = _score(previous)
        if total != old_total:
            raise ValueError("CAPABILITY_FRONTIER_TEST_TOTAL_DRIFT")
        if right > old:
            gain.add(cap)
        elif right == old:
            tied.add(cap)
    if gain:
        return tuple(sorted(gain | tied))
    distinct = {frontier[_key(rubric, cap)]["checkpoint"]["sha256"]
                for cap in tied}
    return tuple(sorted(tied)) if len(distinct) > 1 else ()


def promote(frontier: dict, scores: dict, rubric: str, checkpoint: dict,
            evaluation_id: str, roles: tuple[str, ...]) -> dict:
    """One candidate claims every best role for which it qualifies."""
    if not evaluation_id or not checkpoint.get("model_and_native_adamw"):
        raise ValueError("CAPABILITY_FRONTIER_WHOLE_STUDENT_REQUIRED")
    actual = set(candidate_roles(frontier, scores, rubric))
    if set(roles) != actual:
        raise ValueError("CAPABILITY_FRONTIER_ROLE_SELECTION_DRIFT")
    result = dict(frontier)
    for cap in roles:
        right, total = _score(scores[cap])
        result[_key(rubric, cap)] = {
            "rubric": rubric, "capability": cap,
            "correct": right, "total": total,
            "checkpoint": dict(checkpoint), "evaluation_id": evaluation_id,
        }
    return result


def pinned(frontier: dict, current: dict,
           grade_champions: dict) -> set[str]:
    """These roles, not existence of old receipt JSON, protect hot binaries."""
    checkpoints = [current, *grade_champions.values(),
                   *(item["checkpoint"] for item in frontier.values())]
    result = set()
    for cp in checkpoints:
        name = cp["filename"]
        parts = Path(name).parts
        if (len(parts) != 2 or parts[0] != "bundles" or
                parts[1] in (".", "..") or not cp.get("model_and_native_adamw")):
            raise ValueError("CAPABILITY_FRONTIER_UNSAFE_PIN")
        result.add(name)
    return result


def graduation_perfect(previous, scores, rubric, cohort, checkpoint, evaluation_id):
    """Retain a whole-student witness of each perfect graduation capability."""
    result = dict(previous)
    updated = []
    if not checkpoint.get("model_and_native_adamw"):
        raise ValueError("GRADUATION_PERFECT_REQUIRES_WHOLE_STUDENT")
    for capability, score in sorted(scores.items()):
        correct, total = _score(score)
        if correct == total:
            key = _key(rubric, capability)
            prior = result.get(key)
            if prior and prior["checkpoint"]["sha256"] == checkpoint["sha256"]:
                continue
            result[key] = {"rubric": rubric, "capability": capability,
                           "correct": correct, "total": total,
                           "cohort_sha256": cohort,
                           "checkpoint": dict(checkpoint),
                           "evaluation_id": evaluation_id}
            updated.append(capability)
    return result, tuple(updated)


def retirement_plan(run_dir: Path, keep: set[str]) -> tuple[str, ...]:
    """Conservative, nonmutating census; any unknown data blocks retirement."""
    root = Path(run_dir) / "bundles"
    if not root.exists():
        if keep:
            raise ValueError("CAPABILITY_FRONTIER_CUSTODY_PROTECTED_BUNDLE_MISSING")
        return ()
    expected = {"model-and-own-adamw.safetensors", "semantic-catalog.json",
                "manifest.json"}
    if root.is_symlink():
        raise ValueError("CAPABILITY_FRONTIER_CUSTODY_SYMLINK")
    paths = list(root.iterdir())
    all_names = set()
    for folder in paths:
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("CAPABILITY_FRONTIER_CUSTODY_UNRECOGNIZED_BUNDLE")
        name = "bundles/" + folder.name
        all_names.add(name)
        files = list(folder.iterdir())
        if ({f.name for f in files} != expected or
                any(not f.is_file() or f.is_symlink() for f in files)):
            raise ValueError("CAPABILITY_FRONTIER_CUSTODY_UNRECOGNIZED_CONTENT")
    if not keep <= all_names:
        raise ValueError("CAPABILITY_FRONTIER_CUSTODY_PROTECTED_BUNDLE_MISSING")
    return tuple(sorted(all_names - keep))


def historical_frontier(run_dir: Path, *, expected_rubric: str | None = None,
                        expected_capabilities: dict[str, int] | None = None) -> dict:
    """Rebuild candidate-best pointers from real, source-bound exam receipts.

    This is a read-only migration for earlier trainers with no best ledger.
    If any exam's whole-student bundle is missing or mismatched, fail closed.
    """
    run_dir = Path(run_dir)
    bundle_by_hash = {}
    for bundle in (run_dir / "bundles").iterdir():
        if bundle.is_symlink() or not bundle.is_dir():
            raise ValueError("CAPABILITY_FRONTIER_CUSTODY_UNRECOGNIZED_BUNDLE")
        meta = json.loads((bundle / "manifest.json").read_text())
        digest = meta["safetensors_sha256"]
        if digest in bundle_by_hash:
            raise ValueError("CAPABILITY_FRONTIER_DUPLICATE_MODEL_ID")
        bundle_by_hash[digest] = {
            "filename": "bundles/" + bundle.name, "sha256": digest,
            "optimizer_step": meta["optimizer_step"],
            "model_and_native_adamw": True,
        }
    frontier = {}
    events = run_dir / "events.jsonl"
    if not events.exists():
        return frontier
    with events.open(encoding="utf-8") as stream:
        for line in stream:
            event = json.loads(line)
            if event.get("event") != "GRADE_A_EXAM_COMMITTED":
                continue
            if expected_rubric and event.get("rubric") != expected_rubric:
                raise ValueError("CAPABILITY_FRONTIER_HISTORIC_RUBRIC_DRIFT")
            if expected_capabilities is not None:
                measured = event["scores"]
                if (set(measured) != set(expected_capabilities) or any(
                        measured[cap]["total"] != expected_capabilities[cap]
                        for cap in expected_capabilities)):
                    raise ValueError("CAPABILITY_FRONTIER_HISTORIC_INCOMPLETE_EXAM")
            candidate = bundle_by_hash.get(event["student_sha256"])
            if candidate is None:
                raise ValueError("CAPABILITY_FRONTIER_EXAM_BUNDLE_MISSING")
            score_map = event["scores"]
            rubric = event["rubric"]
            roles = candidate_roles(frontier, score_map, rubric)
            if roles:
                frontier = promote(frontier, score_map, rubric, candidate,
                                   "existing-generation-" + str(event["generation"]),
                                   roles)
    return frontier


def retire_bundles(run_dir: Path, keep: set[str]) -> tuple[str, ...]:
    """Remove only unreferenced, enumerated bundle members after state commit.

    The trainer's exclusive operator lock MUST cover both pointer publication
    and this operation. A retired staging folder isolates interrupted cleanup.
    """
    run_dir = Path(run_dir)
    selected = retirement_plan(run_dir, keep)
    for name in selected:
        source = run_dir / name
        stage = run_dir / "retired-bundles"
        if stage.is_symlink() or (stage.exists() and not stage.is_dir()):
            raise ValueError("CAPABILITY_FRONTIER_CUSTODY_UNSAFE_STAGING")
        stage.mkdir(exist_ok=True)
        target = stage / source.name
        if target.exists() or target.is_symlink():
            raise ValueError("CAPABILITY_FRONTIER_CUSTODY_STAGING_COLLISION")
        if source.is_symlink() or not source.is_dir():
            raise ValueError("CAPABILITY_FRONTIER_CUSTODY_SOURCE_CHANGED")
        source.rename(target)
        for filename in ("manifest.json", "semantic-catalog.json",
                         "model-and-own-adamw.safetensors"):
            path = target / filename
            if path.is_symlink() or not path.is_file():
                raise ValueError("CAPABILITY_FRONTIER_CUSTODY_STAGED_FILE_CHANGED")
            path.unlink()
        target.rmdir()
    return selected
