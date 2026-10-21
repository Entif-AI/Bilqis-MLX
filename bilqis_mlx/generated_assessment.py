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

GRADE_TEST_LIFECYCLE = "bilqis.grade-test.fixed-until-passed/v1"
ROUTINE_EVAL_LIFECYCLE = "bilqis.grade-test.fresh-routine/v2"
PROMOTION_ATTEMPT_LIFECYCLE = "bilqis.grade-test.promotion-attempt/v1"
GENERALIZATION_LIFECYCLE = "bilqis.grade-test.fresh-generalization/v1"
EXECUTABLE_COHORT_SCHEMA = "bilqis.mlx.generated-cohort/v2"
VERSIONED_COHORT_SCHEMA_PREFIX = "bilqis.mlx.generated-cohort/"
_METADATA_DRIFT = "STORED_COHORT_METADATA_DRIFT"


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


def verify_stored_cohort(
        stored: dict, expected_sha256: str, *,
        expected_rubric_sha256: str | None = None,
        expected_factory_release_sha256: str | None = None) -> Cohort:
    """Reconstruct one content-addressed v1/v2 cohort without changing its ABI.

    Historical v1 cohorts hashed their release/schema string as rubric_version.
    Executable v2 cohorts hash the separately stored rubric digest instead and
    bind that measurement identity to an admitted factory release. Unknown
    schemas in the explicit generated-cohort version family fail closed rather
    than being reinterpreted as historical release identifiers.
    """
    def valid_sha(value) -> bool:
        return (isinstance(value, str) and len(value) == 64 and
                all(char in "0123456789abcdef" for char in value))

    if (not isinstance(stored, dict) or not valid_sha(expected_sha256) or
            not isinstance(stored.get("schema"), str) or not stored["schema"] or
            not isinstance(stored.get("generator_version"), str) or
            not stored["generator_version"] or type(stored.get("seed")) is not int or
            not isinstance(stored.get("rows"), list)):
        raise ValueError(_METADATA_DRIFT)
    if stored.get("cohort_sha256") != expected_sha256:
        raise ValueError("STORED_COHORT_IDENTITY_DRIFT")

    schema = stored["schema"]
    if (schema.startswith(VERSIONED_COHORT_SCHEMA_PREFIX) and
            schema != EXECUTABLE_COHORT_SCHEMA):
        raise ValueError("STORED_COHORT_SCHEMA_UNSUPPORTED")
    if (expected_rubric_sha256 is not None and
            stored.get("rubric_sha256") != expected_rubric_sha256):
        raise ValueError(_METADATA_DRIFT)
    rubric_version = schema
    if schema == EXECUTABLE_COHORT_SCHEMA:
        rubric_sha256 = stored.get("rubric_sha256")
        factory_release_sha256 = stored.get("factory_release_sha256")
        if not valid_sha(rubric_sha256) or not valid_sha(factory_release_sha256):
            raise ValueError(_METADATA_DRIFT)
        if (expected_factory_release_sha256 is not None and
                factory_release_sha256 != expected_factory_release_sha256):
            raise ValueError(_METADATA_DRIFT)
        rubric_version = rubric_sha256
    elif expected_factory_release_sha256 is not None:
        # A receipt that declares an executable release must point at the v2
        # storage schema rather than silently reinterpret legacy hash rules.
        raise ValueError(_METADATA_DRIFT)

    cohort = make_cohort(
        stored["rows"], generator_version=stored["generator_version"],
        seed=stored["seed"], rubric_version=rubric_version)
    if cohort.digest != expected_sha256:
        raise ValueError("STORED_COHORT_CONTENT_DRIFT")
    return cohort


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
