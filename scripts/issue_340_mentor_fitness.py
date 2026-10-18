#!/usr/bin/env python3
"""Read-only source-cohort B fitness: continuing student versus historical B soup.

No optimizer calls, teacher changes or neural training. Saved source-gold rows
remain the independent judges, with scores separated by exact cohort.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from bilqis_mlx.trainer import _predictions, _fingerprint, _compatible_graphs
from bilqis_mlx.grade_soup import soup_shards, verify_frozen_soup
from bilqis_mlx.mlx_checkpoint import load_semantically_bound_bundle


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_rows(root, cohort):
    if len(cohort) != 64 or any(c not in "0123456789abcdef" for c in cohort):
        raise ValueError("MENTOR_FITNESS_INVALID_COHORT_ID")
    path = root / "cohorts" / (cohort + ".json")
    data = json.loads(path.read_text())
    if data["cohort_sha256"] != cohort:
        raise ValueError("MENTOR_FITNESS_COHORT_DRIFT")
    rows = [r for r in data["rows"] if r["capability"].startswith("B.")]
    if len(rows) != 72 or any(r.get("answer_kind") != "binary" for r in rows):
        raise ValueError("MENTOR_FITNESS_B_SCOPE_DRIFT")
    return rows, sha(path)


def score(mx, weights, rows, config, answer_ids, vocabulary):
    supported = [r for r in rows if max([*r["tokens"], *answer_ids]) < vocabulary]
    guesses = _predictions(mx, weights, supported, config, answer_ids) if supported else {}
    caps = {}
    for r in supported:
        cell = caps.setdefault(r["capability"], {"correct": 0, "total": 0})
        cell["total"] += 1
        cell["correct"] += guesses[r["id"]] == r["gold"]
    return {"correct": sum(v["correct"] for v in caps.values()),
            "supported": len(supported), "total": len(rows),
            "capabilities": dict(sorted(caps.items()))}


def evaluate(root: Path, cohorts: list[str]):
    import mlx.core as mx
    root = root.resolve(strict=True)
    manifest = root.with_name(root.name + ".fork-manifest.json")
    if not manifest.is_file() or json.loads(manifest.read_text()).get("destination") != str(root):
        raise ValueError("MENTOR_FITNESS_REQUIRES_MANIFESTED_FORK")
    saved = json.loads((root / "state.json").read_text())
    current = saved["school"]["current_student"]
    weights, optimizer, meta, graph = load_semantically_bound_bundle(
        root / current["filename"])
    if (meta["safetensors_sha256"] != current["sha256"] or
            meta["optimizer_step"] != current["optimizer_step"] or
            _fingerprint(graph) != saved["semantic_graph_sha256"]):
        raise ValueError("MENTOR_FITNESS_STUDENT_DRIFT")
    del optimizer
    ids = cohorts or [saved["last_exam"]["cohort_sha256"]]
    specimens = {cohort: source_rows(root, cohort) for cohort in ids}
    config, answer_ids = saved["config"], saved["answer_ids"]
    models = {"current_student": {
        "sha256": current["sha256"],
        "results": {c: score(mx, weights, rows, config, answer_ids,
                             len(graph["tokens"])) for c, (rows, _) in specimens.items()}}}
    del weights

    # Compare intact checkpoints rather than assigning unearned trust from
    # historical grade-role labels. The reference keeps its own AdamW read-only.
    references = [("curriculum_epoch_origin", saved["curriculum_parent"], None)]
    references.extend((f"B_recipe_ingredient_{index+1}", item["checkpoint"],
                       item["votes"]) for index, item in enumerate(
                           saved["grade_soups"]["B"]["members"]))
    for name, pointer, role_votes in references:
        path = root / pointer["filename"]
        if path.parent != root / "bundles" or path.is_symlink():
            raise ValueError("MENTOR_FITNESS_UNSAFE_REFERENCE_BUNDLE")
        other, other_adamw, metadata, old_graph = load_semantically_bound_bundle(path)
        if (metadata["safetensors_sha256"] != pointer["sha256"] or
                metadata["optimizer_step"] != pointer["optimizer_step"] or
                not _compatible_graphs(old_graph, graph)):
            raise ValueError("MENTOR_FITNESS_REFERENCE_SOURCE_DRIFT")
        models[name] = {"sha256": pointer["sha256"],
                        "optimizer_step": pointer["optimizer_step"],
                        "historical_role_votes": None if name == "curriculum_epoch_origin" else
                        next(item["votes"] for item in saved["grade_soups"]["B"]["members"]
                             if item["checkpoint"]["sha256"] == pointer["sha256"]),
                        "exact_graph": old_graph == graph,
                        "results": {c: score(mx, other, rows, config, answer_ids,
                                             len(old_graph["tokens"]))
                                    for c, (rows, _) in specimens.items()}}
        del other, other_adamw
    for i, soup in enumerate(soup_shards(saved["grade_soups"]["B"])):
        blob = verify_frozen_soup(root, soup)
        mentor = mx.load(str(blob))
        models[f"B_soup_shard_{i+1}"] = {
            "sha256": soup["sha256"], "historical_role_votes": soup["vote_count"],
            "exact_graph": soup.get("source_graph_sha256") == _fingerprint(graph),
            "results": {c: score(mx, mentor, rows, config, answer_ids,
                                 soup["token_count"]) for c, (rows, _) in specimens.items()}}
        del mentor
    return {"schema": "bilqis.mlx.issue340-mentor-fitness/v1", "read_only": True,
            "student_step": current["optimizer_step"],
            "source_state_sha256": sha(root / "state.json"),
            "cohort_files": {c: file_sha for c, (_, file_sha) in specimens.items()},
            "models": models}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", required=True, type=Path)
    p.add_argument("--cohort", action="append", default=[])
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    result = evaluate(args.run_dir, args.cohort)
    output = args.output.expanduser().absolute()
    if args.run_dir.resolve(strict=True) in output.parents or output.exists():
        raise ValueError("MENTOR_FITNESS_UNSAFE_OUTPUT")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("READ_ONLY_MENTOR_FITNESS=" + str(output))


if __name__ == "__main__":
    main()
