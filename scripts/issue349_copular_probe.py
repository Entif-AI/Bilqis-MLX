"""Read-only neural prerequisite probe plus issue-owned source-candidate staging.

Only a run already registered to #349 may receive autonomy evidence/artifacts.
The causal student, optimizer, teacher, school state and event log are unchanged.
"""
from dataclasses import asdict
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from bilqis_mlx.factory.autonomy import obligations_for_capability, record_evidence
from bilqis_mlx.factory.evidence import measure_evidence
from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.runtime.admission import _require_executable_factory_admission
from bilqis_mlx.runtime.autonomy_live import LiveAutonomySession
from bilqis_mlx.runtime.autonomy_state import persist_autonomy_state
from bilqis_mlx.runtime.experiment_runs import ExperimentRunBudget
from bilqis_mlx.runtime.mlx_checkpoint import load_semantically_bound_bundle
from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.trainer import operator_lock, _predictions, _state_from_json


ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(run_dir, output):
    import mlx.core as mx
    mx.set_default_device(mx.gpu)
    budget = ExperimentRunBudget(ROOT / "runs/issue-349-experiments")
    run_dir = Path(run_dir).resolve(strict=True)
    budget.register(run_dir)
    budget.assert_can_allocate(10_000_000)
    output = Path(output)
    if output.exists():
        raise ValueError("ISSUE349_PROBE_RECEIPT_ALREADY_EXISTS")
    with operator_lock(run_dir):
        saved = json.loads((run_dir / "state.json").read_text())
        bundle = (run_dir / saved["model_bundle"]).resolve(strict=True)
        if bundle.parent != (run_dir / "bundles").resolve(strict=True):
            raise ValueError("ISSUE349_PROBE_BUNDLE_ESCAPES_RUN")
        protected = [run_dir / "state.json", run_dir / "events.jsonl", *bundle.iterdir()]
        before = {str(p.relative_to(run_dir)): sha(p) for p in protected if p.is_file()}
        parameters, optimizer, manifest, graph = load_semantically_bound_bundle(bundle)
        release = _require_executable_factory_admission(run_dir, saved, graph)
        program = schedule_program_from_executable_release(release)
        school = _state_from_json(saved["school"], program)
        checkpoint = school.current_student
        assert checkpoint.sha256 == manifest["safetensors_sha256"]
        assert checkpoint.optimizer_step == int(optimizer.state["step"].item())
        session = LiveAutonomySession.open(run_dir, ROOT / "vendor/legacy-v16", release)
        measured = {}
        for index, capability in enumerate(("A.IDENTITY", "A.MAPS")):
            obligation = next(o for o in obligations_for_capability(release, capability,
                plan=session.plan) if o.kind.value == "DIRECT")
            def predict(rows):
                guesses = _predictions(mx, parameters, list(rows), saved["config"], saved["answer_ids"])
                measured[capability] = dict(total=len(rows), correct=sum(
                    guesses[row["id"]] == row["gold"] for row in rows),
                    specimen_ids=[row["id"] for row in rows], predictions=guesses)
                return guesses
            receipt = measure_evidence(ROOT / "vendor/legacy-v16", graph, release,
                live_source_registry(), obligation, checkpoint=asdict(checkpoint),
                seed=2026102010 + index, predictor=predict)
            measured[capability]["evidence"] = asdict(receipt)
            existing = next((r for r in session.ledger.receipts
                             if r.evidence_id == receipt.evidence_id), None)
            if existing is None:
                session.ledger = record_evidence(release, session.ledger, receipt, plan=session.plan,
                    current_checkpoint_sha256=checkpoint.sha256,
                    current_optimizer_step=checkpoint.optimizer_step)
            elif existing != receipt:
                raise ValueError("ISSUE349_PROBE_EVIDENCE_DIVERGED")
        persist_autonomy_state(run_dir, release, plan=session.plan, ledger=session.ledger)
        proposal, relative = session.propose_source_frontier_work(checkpoint, graph)
        proposal_summary = asdict(proposal)
        proposal_summary["candidate_gate_count"] = len(proposal.candidate_gates)
        proposal_summary["candidate_gates"] = [asdict(g) for g in proposal.candidate_gates
            if g.operation_cost != (9999,) * 4]
        proposal_summary["candidate_gates_projection"] = "STAGED_TARGETS_ONLY"
        after = {str(p.relative_to(run_dir)): sha(p) for p in protected if p.is_file()}
        assert after == before, "ISSUE349_PROBE_CHANGED_CAUSAL_STATE"
        assert int(optimizer.state["step"].item()) == checkpoint.optimizer_step
        result = dict(schema="bilqis.issue349.copular-prerequisite-probe/v1",
            run=str(run_dir), generation=saved["generation"], checkpoint=asdict(checkpoint),
            factory_release_sha256=release.release_sha256,
            code_parent_sha=subprocess.check_output(["git", "rev-parse", "HEAD"],
                cwd=ROOT, text=True).strip(), source_worktree_observation=True,
            measurements=measured, jit_proposal=proposal_summary, proposal_file=relative,
            protected_files_before=before, protected_files_after=after,
            actual_neural_updates=0, learned_ithkuil="NOT_MEASURED", budget=budget.enforce())
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.run_dir, args.output)
    print(json.dumps(dict(measurements={c: {k: r[k] for k in ("correct", "total")}
        for c, r in result["measurements"].items()},
        disposition=result["jit_proposal"]["disposition"],
        actual_neural_updates=0, budget=result["budget"]), indent=2))
