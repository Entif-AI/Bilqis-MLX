"""Read-only neural replay of the preserved pre-C false-graduate regression.

The checkpoint, native AdamW, source cohorts and historical files are never
written. Output is a new engineering receipt, not a student graduation seal.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bilqis_mlx.backup import digest_file
from bilqis_mlx.factory.assessment import qualification_complete
from bilqis_mlx.factory.model import AssessmentClass, LearningEvidence
from bilqis_mlx.factory.verification import check_connective, check_predicate
from bilqis_mlx.generated_assessment import make_cohort, score
from bilqis_mlx.runtime.mlx_checkpoint import load_semantically_bound_bundle
from bilqis_mlx.runtime.state import _durable_json
from bilqis_mlx.source import AUDITED_PARENT
from bilqis_mlx.trainer import _predictions


def replay(run_dir: Path) -> dict:
    import mlx.core as mx
    import torch

    fixture = json.loads((ROOT / "bilqis_mlx/factory/tests/fixtures/historical_b_false_mastery.json").read_text())
    checkpoint = fixture["checkpoint"]
    bundle = run_dir / "bundles" / Path(checkpoint["bundle"]).name
    parameters, optimizer, manifest, graph = load_semantically_bound_bundle(bundle)
    if (manifest["safetensors_sha256"] != checkpoint["sha256"] or
            manifest["optimizer_step"] != checkpoint["optimizer_step"]):
        raise ValueError("HISTORICAL_REPLAY_CHECKPOINT_DRIFT")
    source_root = ROOT / "vendor/legacy-v16"
    original = source_root / "runs/primitive-consolidation-v16-triplets" / AUDITED_PARENT.basename
    if digest_file(original) != AUDITED_PARENT.sha256:
        raise ValueError("HISTORICAL_REPLAY_SOURCE_CHECKPOINT_DRIFT")
    config = torch.load(original, map_location="cpu", weights_only=True)["config"]
    answer_ids = [graph["tokens"].index(name) for name in ("cogal.value.false", "cogal.value.true")]
    evidence = {}
    observations = {}
    for plane, kind in (("promotion", AssessmentClass.PROMOTION),
                        ("fresh_generalization", AssessmentClass.GENERALIZATION)):
        expected = fixture[plane]
        payload = json.loads((run_dir / "cohorts" / (expected["cohort_sha256"] + ".json")).read_text())
        original_cohort = make_cohort(payload["rows"], generator_version=payload["generator_version"],
                                      seed=payload["seed"], rubric_version=payload["schema"])
        if original_cohort.digest != expected["cohort_sha256"]:
            raise ValueError("HISTORICAL_REPLAY_COHORT_DRIFT")
        # The later source cohort also enrolled C.COUNT. Its A/B slice is
        # compatible with the pre-C checkpoint; C is outside this replay.
        cohort = make_cohort(
            [row for row in original_cohort.rows if row["capability"].startswith(("A.", "B."))],
            generator_version=original_cohort.generator_version, seed=original_cohort.seed,
            rubric_version=original_cohort.rubric_version)
        for row in cohort.rows:
            checker = check_predicate if row["capability"].startswith("A.") else check_connective
            if not checker(row, source_root=source_root):
                raise ValueError("HISTORICAL_REPLAY_SOURCE_DISAGREEMENT")
        measured = score(cohort, _predictions(mx, parameters, list(cohort.rows), config, answer_ids),
                         {**checkpoint, "model_and_native_adamw": True})
        totals = {grade: {field: sum(value[field] for cap, value in measured["scores"].items()
                                    if cap.startswith(grade + ".")) for field in ("correct", "total")}
                  for grade in ("A", "B")}
        for grade in totals:
            if totals[grade] != {field: expected[grade.lower() + "_" + field]
                                 for field in ("correct", "total")}:
                raise ValueError("HISTORICAL_REPLAY_MEASUREMENT_DRIFT:" + grade)
        evidence[plane] = LearningEvidence(kind, cohort.digest, checkpoint["sha256"],
            checkpoint["optimizer_step"], totals["B"]["correct"] == totals["B"]["total"])
        observations[plane] = {"cohort_sha256": cohort.digest,
                               "original_cohort_sha256": original_cohort.digest,
                               "evaluated_scope": "A+B", "grades": totals,
                               "capabilities": measured["scores"]}
    if (int(optimizer.state["step"].item()) != checkpoint["optimizer_step"] or
            digest_file(bundle / "model-and-own-adamw.safetensors") != checkpoint["sha256"]):
        raise ValueError("HISTORICAL_REPLAY_CUSTODY_CHANGED")
    return {"schema": "bilqis.mlx.factory-historical-neural-replay/v1",
            "checkpoint": checkpoint, "observations": observations,
            "factory_qualification_passed": qualification_complete(
                evidence["promotion"], evidence["fresh_generalization"]),
            "actual_neural_updates": 0, "native_adamw_unchanged": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = replay(args.run_dir.resolve(strict=True))
    if args.output is not None:
        if args.output.exists():
            if args.output.is_symlink() or json.loads(args.output.read_text()) != result:
                raise ValueError("HISTORICAL_REPLAY_OUTPUT_COLLISION")
        else:
            _durable_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    print("Historical replay passed: B promotion 72/72; fresh 47/72; factory graduation refused; 0 neural updates")


if __name__ == "__main__":
    main()
