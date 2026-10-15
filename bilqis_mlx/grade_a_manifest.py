"""Deterministic, *candidate-only* Grade A exam custody and source-row ledger.

Generates sealed training and evaluation *records* from the pinned legacy
source, including labels alongside training questions. This file cannot
authorize a neural training run or certify NI surface wordforms.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .grade_a_oracle import VERSION as ORACLE_VERSION, evaluate as third_oracle
from .grade_a_probe import (FAMILIES, PINNED_SOURCES, PINNED_GRAPH_SHA256,
                            PINNED_FULL_STUDENT_GRAPH_SHA256, _draw,
                            candidate_course, parent_graph_binding, read_sources)

SCHEMA = "bilqis.mlx.grade-a-candidate-manifest/v2"
SEMANTIC_REVIEW = "mapping-review/20261015-d"


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _sha(value) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _source_rows(rows: list[dict], partition: str) -> list[dict]:
    return [
        {"id": row["id"], "capability": row["capability"],
         "partition": partition, "record": row["record"],
         "tokens": list(row["tokens"]), "gold": row["gold"],
         "answer_kind": row["kind"], "source_root": row["root"],
         "oracle": row["oracle"]}
        for row in rows
    ]


def build_manifest(legacy_root: Path, checkpoint: Path, *,
                   train_each: int = 24, exam_each: int = 12) -> dict:
    """Freeze 216 full input/gold rows; do not treat a source hash as approval."""
    micro, development, graph, sources, graph_sha = read_sources(legacy_root)
    binding = parent_graph_binding(checkpoint, graph)
    course = candidate_course()
    training = []
    examination = []
    used = set()
    for capability, _, _, _ in FAMILIES:
        train = _draw(capability, "train", count=train_each, micro=micro,
                      development=development, graph=graph, past_ids=set())
        exam = _draw(capability, "exam", count=exam_each, micro=micro,
                     development=development, graph=graph,
                     past_ids={r["id"] for r in train})
        ids = [r["id"] for r in train + exam]
        if used.intersection(ids) or len(set(ids)) != len(ids):
            raise ValueError("GRADE_A_MANIFEST_DUPLICATE_RECORD")
        used.update(ids)
        train_tokens = {t for row in train for t in row["tokens"]}
        exam_tokens = {t for row in exam for t in row["tokens"]}
        if not exam_tokens <= train_tokens:
            raise ValueError("GRADE_A_MANIFEST_UNSEEN_EXAM_TOKEN")
        if {r["universe_size"] for r in train} != {3, 4} or (
                {r["universe_size"] for r in exam} != {3, 4}):
            raise ValueError("GRADE_A_MANIFEST_UNTAUGHT_WORLD_SIZE")
        for row in train + exam:
            if third_oracle(row["record"], capability) != row["gold"]:
                raise ValueError("GRADE_A_MANIFEST_THIRD_ORACLE_MISMATCH")
        training.extend(_source_rows(train, "train"))
        examination.extend(_source_rows(exam, "exam"))
    if len(used) != len(training) + len(examination):
        raise ValueError("GRADE_A_MANIFEST_ITEM_ID_CONFLICT")
    body = {
        "schema": SCHEMA,
        "state": "CANDIDATE_SEALED_NOT_TRAINING_ADMITTED",
        "review_version": SEMANTIC_REVIEW,
        "course_proposal_digest": course.digest(),
        "source_sha256_by_file": sources,
        "source_graph_sha256": graph_sha,
        "parent_student": binding,
        "oracle_version": ORACLE_VERSION,
        "train_count": len(training),
        "exam_count": len(examination),
        "training_rows": training,
        "examination_rows": examination,
        "neural_updates": 0,
        "ni_wordforms_certified": False,
        "training_permission_granted": False,
    }
    return {
        **body,
        "exam_rubric_sha256": _sha(examination),
        "train_sha256": _sha(training),
        "manifest_sha256": _sha(body),
    }


def verify_manifest(manifest: dict, legacy_root: Path, checkpoint: Path) -> dict:
    """Verify full source rows against a fresh independent rendering, not metadata."""
    if (not isinstance(manifest, dict) or
            manifest.get("schema") != SCHEMA or
            manifest.get("state") != "CANDIDATE_SEALED_NOT_TRAINING_ADMITTED"):
        raise ValueError("GRADE_A_MANIFEST_STATE_OR_SCHEMA_INVALID")
    if (manifest.get("neural_updates") != 0 or
            manifest.get("training_permission_granted") is not False or
            manifest.get("ni_wordforms_certified") is not False):
        raise ValueError("GRADE_A_MANIFEST_IMPROPER_RELEASE_CLAIM")
    train = manifest.get("training_rows", [])
    exam = manifest.get("examination_rows", [])
    digests = ("manifest_sha256", "train_sha256", "exam_rubric_sha256")
    if not all(isinstance(manifest.get(d), str) for d in digests):
        raise ValueError("GRADE_A_MANIFEST_DIGESTS_MISSING")
    body = {k: v for k, v in manifest.items() if k not in digests}
    if (manifest["manifest_sha256"] != _sha(body) or
            manifest["train_sha256"] != _sha(train) or
            manifest["exam_rubric_sha256"] != _sha(exam)):
        raise ValueError("GRADE_A_MANIFEST_CONTENT_HASH_MISMATCH")
    expected = build_manifest(legacy_root, checkpoint,
                              train_each=manifest["train_count"] // len(FAMILIES),
                              exam_each=manifest["exam_count"] // len(FAMILIES))
    if manifest != expected:
        raise ValueError("GRADE_A_MANIFEST_NOT_EQUAL_TO_PINNED_SOURCE")
    return {"verified_items": len(train) + len(exam),
            "exam_rubric_sha256": manifest["exam_rubric_sha256"],
            "training_rows_have_gold": all("gold" in row for row in train),
            "model_unchanged": True}


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-code-root", type=Path, required=True)
    parser.add_argument("--champion-checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-manifest", type=Path)
    args = parser.parse_args(argv)
    if args.output and args.verify_manifest:
        parser.error("--output and --verify-manifest are mutually exclusive")
    if args.verify_manifest:
        frozen = json.loads(args.verify_manifest.read_text(encoding="utf-8"))
        print(json.dumps(verify_manifest(frozen, args.legacy_code_root,
                                         args.champion_checkpoint),
                         sort_keys=True, indent=2))
        return
    manifest = build_manifest(args.legacy_code_root, args.champion_checkpoint)
    if args.output:
        output = args.output
        rendered = json.dumps(manifest, sort_keys=True, indent=2,
                              ensure_ascii=False) + "\n"
        # Audit material is create-once; never quietly rewrite a sealed exam.
        with output.open("x", encoding="utf-8") as stream:
            stream.write(rendered)
    else:
        print(json.dumps({k: v for k, v in manifest.items()
                          if k not in ("training_rows", "examination_rows")},
                         indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
