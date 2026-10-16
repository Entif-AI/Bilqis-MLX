"""Unembargoed, reproducible cohort comparison over typed semantic examples.

An assessment cohort is a temporary measurement instrument, not a secret
question pool. Once measured, every missed construction is eligible for
reinstruction. All checkpoint scores compared in one decision must use the
same materialized cohort and complete model/optimizer checkpoint identity.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Cohort:
    generator_version: str
    seed: int
    rubric_version: str
    rows: tuple[dict, ...]
    digest: str


def make_cohort(rows, *, generator_version: str, seed: int,
                rubric_version: str) -> Cohort:
    """Bind reproducibility to *all* question content, not seed alone."""
    if (not generator_version or type(seed) is not int or
            not rubric_version):
        raise ValueError("COHORT_PROVENANCE_REQUIRED")
    records = tuple(rows)
    if not records:
        raise ValueError("COHORT_EMPTY")
    ids = [r["id"] for r in records]
    if len(ids) != len(set(ids)) or any(
            not r.get("capability") or "gold" not in r for r in records):
        raise ValueError("COHORT_IDENTITY_OR_GOLD_INVALID")
    identity = {"generator_version": generator_version,
                "rubric_version": rubric_version, "seed": seed,
                "rows": records}
    return Cohort(generator_version, seed, rubric_version, records,
                  digest(identity))


def score(cohort: Cohort, predictions: dict, checkpoint: dict) -> dict:
    """Score one intact checkpoint without mutating weights or the cohort."""
    if (not checkpoint.get("model_and_native_adamw") or
            not checkpoint.get("sha256") or
            type(checkpoint.get("optimizer_step")) is not int):
        raise ValueError("COHORT_COMPLETE_CHECKPOINT_REQUIRED")
    row_ids = {r["id"] for r in cohort.rows}
    if set(predictions) != row_ids:
        raise ValueError("COHORT_INCOMPLETE_PREDICTIONS")
    capabilities = sorted({r["capability"] for r in cohort.rows})
    scores = {cap: {"correct": sum(predictions[r["id"]] == r["gold"]
              for r in cohort.rows if r["capability"] == cap),
              "total": sum(r["capability"] == cap for r in cohort.rows)}
              for cap in capabilities}
    misses = tuple({"id": r["id"], "capability": r["capability"],
                    "source_id": r.get("source_id", r["id"]),
                    "gold": r["gold"], "predicted": predictions[r["id"]]}
                   for r in cohort.rows if predictions[r["id"]] != r["gold"])
    return {"cohort_sha256": cohort.digest,
            "generator_version": cohort.generator_version,
            "rubric_version": cohort.rubric_version,
            "seed": cohort.seed, "checkpoint": dict(checkpoint),
            "scores": scores, "misses_for_teacher": misses,
            "perfect_on_sample": not misses}


def compare_on_same_cohort(challenger: dict, incumbent: dict) -> tuple[str, ...]:
    """Return capability gains only on an identically sampled rubric."""
    if (challenger["cohort_sha256"] != incumbent["cohort_sha256"] or
            challenger["rubric_version"] != incumbent["rubric_version"] or
            set(challenger["scores"]) != set(incumbent["scores"])):
        raise ValueError("COHORT_NOT_COMPARABLE")
    gains = []
    for cap, current in challenger["scores"].items():
        previous = incumbent["scores"][cap]
        if current["total"] != previous["total"]:
            raise ValueError("COHORT_TOTAL_MISMATCH")
        if current["correct"] > previous["correct"]:
            gains.append(cap)
    return tuple(sorted(gains))
