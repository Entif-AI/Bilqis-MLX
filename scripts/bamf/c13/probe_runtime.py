"""Read-only complete-solver probes for the disposable C13.1 lineage."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.paths import LEGACY_SOURCE
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.bamf_bundle import read_accepted_generation_feature_receipt
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.factory_complete_solver import (
    factory_complete_solver,
    factory_evaluation_instrument,
)
from bilqis_mlx.semantics.atlas.snapshot import (
    AtlasArtifactIdentity,
    resolve_atlas_artifact_selection,
)
from bilqis_mlx.source_adapters.c13_episode import CAPABILITY

from scripts.bamf.c13.contracts import SolverProbeReceipt


def _accepted_context(run_dir: Path):
    run_dir = Path(run_dir).resolve()
    candidate = load_accepted_generation(run_dir)
    context = AcceptedRuntimeHost(run_dir).source_context(
        source_root=LEGACY_SOURCE.resolve())
    receipt = read_accepted_generation_feature_receipt(run_dir / "bamf-state.json")
    selection = resolve_atlas_artifact_selection(AtlasArtifactIdentity(
        receipt.source_atlas_bundle_id,
        receipt.source_release_sha256,
        receipt.source_source_bundle_id,
    ))
    return candidate, context, selection.path


def complete_solver_probe(run_dir: Path, split: str) -> SolverProbeReceipt:
    """Score the required literal C13 seed split without mutating the student."""
    if split not in ("BASELINE", "FRESH"):
        raise ValueError("BAMF_C13_SOLVER_PROBE_SPLIT_INVALID")
    candidate, context, artifact = _accepted_context(run_dir)
    if split == "BASELINE":
        source_each = 64
        rows = tuple(context.draw_rows(seed=0, capability=CAPABILITY, each=source_each))
    else:
        source_each = 128
        rows = tuple(context.draw_rows(
            seed=0, capability=CAPABILITY, each=source_each))[64:]
    observed = tuple(row["record"]["seed"] for row in rows)
    expected = tuple(range(64)) if split == "BASELINE" else tuple(range(64, 128))
    if observed != expected or any(row["record"]["depth"] != 1 for row in rows):
        raise ValueError("BAMF_C13_SOLVER_PROBE_SOURCE_SPLIT_DRIFT")
    instruments = tuple(
        factory_evaluation_instrument(
            context,
            candidate,
            str(artifact),
            row,
            source_seed=0,
            source_each=source_each,
        )
        for row in rows
    )
    solver, generation = factory_complete_solver(
        context, candidate, str(artifact), instruments)
    correct = neural_calls = source_only_correct = 0
    for instrument in instruments:
        result, _contract = solver.evaluate(instrument.case.goal, generation)
        matched = result.answer == instrument.case.gold
        correct += int(matched)
        neural_calls += result.neural_calls
        source_only_correct += int(matched and result.neural_calls == 0)
    return SolverProbeReceipt(
        split, 1, correct, len(instruments), neural_calls,
        source_only_correct, generation)


__all__ = ("complete_solver_probe",)
