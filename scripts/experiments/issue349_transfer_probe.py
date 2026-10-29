"""Read-only fresh-seed transfer measurement in the two registered experiments."""
from collections import Counter
from dataclasses import asdict
import argparse
import hashlib
import inspect
import json
from pathlib import Path
from bilqis_mlx.state_dag import read_current

from bilqis_mlx.factory.generation import draw_executable_release_rows
from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.runtime.admission import _require_executable_factory_admission
from bilqis_mlx.runtime.experiment_runs import ExperimentRunBudget
from bilqis_mlx.runtime.mlx_checkpoint import load_semantically_bound_bundle
from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.trainer import _predictions, _state_from_json, operator_lock


ROOT = Path(__file__).resolve().parents[2]
SEEDS = (2026102101, 2026102102, 2026102103)
CAPABILITIES = ("A.IDENTITY", "A.MAPS")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(run_dir, output):
    run_dir = Path(run_dir).resolve(strict=True)
    output = Path(output)
    budget = ExperimentRunBudget(run_dir.parent)
    budget.register(run_dir)
    budget.assert_within_budget()
    if output.exists():
        raise ValueError("ISSUE349_TRANSFER_RECEIPT_ALREADY_EXISTS")
    import mlx.core as mx
    mx.set_default_device(mx.gpu)
    with operator_lock(run_dir):
        saved = read_current(run_dir)
        bundle = (run_dir / saved["model_bundle"]).resolve(strict=True)
        if bundle.parent != run_dir / "bundles":
            raise ValueError("ISSUE349_TRANSFER_BUNDLE_ESCAPES_RUN")
        protected = [run_dir / "state.json", run_dir / "events.jsonl", *bundle.iterdir()]
        before = {str(p.relative_to(run_dir)): digest(p) for p in protected if p.is_file()}
        parameters, optimizer, manifest, graph = load_semantically_bound_bundle(bundle)
        release = _require_executable_factory_admission(run_dir, saved, graph)
        school = _state_from_json(saved["school"], schedule_program_from_executable_release(release))
        checkpoint = school.current_student
        if (checkpoint.sha256 != manifest["safetensors_sha256"] or
                checkpoint.optimizer_step != int(optimizer.state["step"].item())):
            raise ValueError("ISSUE349_TRANSFER_NATIVE_CHECKPOINT_DRIFT")
        registry = live_source_registry()
        measurements = {}
        for capability in CAPABILITIES:
            specimens = {}
            for seed in SEEDS:
                rows = draw_executable_release_rows(ROOT / "vendor/legacy-v16", graph,
                    release, registry, capability=capability, seed=seed, each=60)
                for row in rows:
                    if row["id"] in specimens and specimens[row["id"]] != row:
                        raise ValueError("ISSUE349_TRANSFER_SPECIMEN_IDENTITY_CONFLICT")
                    specimens[row["id"]] = row
            rows = list(specimens.values())
            predictions = _predictions(mx, parameters, rows, saved["config"], saved["answer_ids"])
            if set(predictions) != set(specimens):
                raise ValueError("ISSUE349_TRANSFER_INCOMPLETE_PREDICTIONS")
            gold = Counter(row["gold"] for row in rows)
            measurements[capability] = dict(total=len(rows),
                correct=sum(predictions[row["id"]] == row["gold"] for row in rows),
                gold_counts=dict(gold), majority_baseline=max(gold.values()),
                prediction_counts=dict(Counter(predictions.values())),
                specimens=[dict(id=row["id"], gold=row["gold"], predicted=predictions[row["id"]],
                    tokens_sha256=hashlib.sha256(json.dumps(row["tokens"]).encode()).hexdigest())
                    for row in rows])
        after = {str(p.relative_to(run_dir)): digest(p) for p in protected if p.is_file()}
        if after != before or int(optimizer.state["step"].item()) != checkpoint.optimizer_step:
            raise ValueError("ISSUE349_TRANSFER_CHANGED_CAUSAL_STATE")
        report = dict(schema="bilqis.issue349.fresh-seed-transfer/v1", run=run_dir.name,
            checkpoint=asdict(checkpoint), generation=saved["generation"], seeds=SEEDS,
            factory_release_sha256=release.release_sha256, measurements=measurements,
            predictor_sha256=hashlib.sha256(inspect.getsource(_predictions).encode()).hexdigest(),
            source_files_sha256={name: digest(ROOT / "bilqis_mlx" / name) for name in (
                "trainer.py", "runtime/mlx_parity.py", "runtime/mlx_checkpoint.py",
                "source_adapters/school.py", "live_grade_a.py", "grade_a_probe.py",
                "grade_a_oracle.py", "factory/generation.py", "factory/verification.py")},
            protected_files_before=before, protected_files_after=after,
            actual_neural_updates=0, admission_evidence_written=False,
            training_exposure_overlap="NOT_MEASURED", learned_ithkuil="NOT_MEASURED",
            budget=budget.enforce())
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x") as stream:
            stream.write(json.dumps(report, indent=2) + "\n")
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.run_dir, args.output)
    print(json.dumps({cap: {k: row[k] for k in ("correct", "total", "majority_baseline")}
                      for cap, row in result["measurements"].items()}))
