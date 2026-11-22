"""Planning/custody helpers for the accepted Atlas flywheel runtime."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

from bilqis_mlx.compatibility.source_adapter_resume import (
    predecessor_compatible_source_registry,
)
from bilqis_mlx.factory import candidate_realizations
from bilqis_mlx.factory.candidate_frontier import (
    candidate_frontier_source_identity,
    load_candidate_frontier,
)
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.paths import LEGACY_SOURCE
from bilqis_mlx.semantics.atlas.snapshot import (
    AtlasArtifactIdentity,
)
from bilqis_mlx.runtime.bamf_bundle import (
    load_bamf_generation_authority,
    read_current_accepted_generation_feature_receipt,
)
from bilqis_mlx.runtime.candidate_staging import (
    load_staged_candidates,
    persist_staged_candidate,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _frontier_progress(progress, message):
    if progress is not None:
        progress(message)


@dataclass(frozen=True)
class CandidateFrontierTrustIdentity:
    builder_sha256: str
    input_digest: str
    factory_release_sha256: str
    frontier_release_sha256: str | None
    receipt_sha256: str | None


def _candidate_frontier_trust_identity(
        factory_release_sha256: str) -> CandidateFrontierTrustIdentity:
    """Return the current builder/input/trust identity for planning reuse."""
    root = _repo_root()
    builder = root / "lib/ithkuil/src/build_curriculum_frontier.py"
    source_dir = root / "lib/ithkuil/_data/csv"
    builder_sha256, input_digest = candidate_frontier_source_identity(
        source_dir, builder)
    from bilqis_mlx.runtime.planner_frontier_trust import (
        load_planner_frontier_trust,
    )
    trust = load_planner_frontier_trust(
        builder_sha256, input_digest, factory_release_sha256)
    return CandidateFrontierTrustIdentity(
        builder_sha256=builder_sha256,
        input_digest=input_digest,
        factory_release_sha256=factory_release_sha256,
        frontier_release_sha256=(
            None if trust is None else trust.frontier_release_sha256),
        receipt_sha256=None if trust is None else trust.receipt_sha256,
    )


def _candidate_frontier(
        run_dir: Path, factory_release_sha256: str, *, progress=None):
    root = _repo_root()
    builder = root / "lib/ithkuil/src/build_curriculum_frontier.py"
    source_dir = root / "lib/ithkuil/_data/csv"
    output = Path(run_dir) / "candidate-frontier"
    builder_sha256, input_digest = candidate_frontier_source_identity(
        source_dir, builder)
    from bilqis_mlx.runtime.planner_frontier_trust import (
        load_planner_frontier_trust,
        planner_frontier_trust_matches,
        publish_planner_frontier_trust,
    )
    trust = load_planner_frontier_trust(
        builder_sha256, input_digest, factory_release_sha256)
    if trust is not None:
        try:
            release = load_candidate_frontier(
                output, source_dir, expected_builder_sha256=builder_sha256)
        except ValueError as error:
            if not str(error).startswith("CANDIDATE_FRONTIER_"):
                raise
        else:
            if planner_frontier_trust_matches(trust, release):
                _frontier_progress(
                    progress, "planner: reusing source candidate frontier")
                return release
    _frontier_progress(progress, "planner: rebuilding source candidate frontier")
    subprocess.run(
        [sys.executable, str(builder)], check=True, capture_output=True, text=True,
        env={**os.environ, "BILQIS_CURRICULUM_FRONTIER_OUT": str(output)},
    )
    release = load_candidate_frontier(
        output, source_dir, expected_builder_sha256=builder_sha256)
    if trust is None:
        trust = publish_planner_frontier_trust(release, factory_release_sha256)
    if not planner_frontier_trust_matches(trust, release):
        from bilqis_mlx.runtime.planner_frontier_trust import (
            _invalid as _invalid_frontier_trust,
        )
        _invalid_frontier_trust("BAMF_PLANNER_FRONTIER_TRUST_CONFLICT")
    return release


def _accepted_selection(run_dir: Path):
    receipt = read_current_accepted_generation_feature_receipt(run_dir)
    identity = AtlasArtifactIdentity(
        receipt.source_atlas_bundle_id,
        receipt.source_release_sha256,
        receipt.source_source_bundle_id,
    )
    from bilqis_mlx.runtime import atlas_flywheel_runtime as runtime
    return runtime.resolve_atlas_artifact_selection(identity), receipt


def _accepted_checkpoint(run_dir: Path) -> Checkpoint:
    from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
        load_accepted_generation_with_pointer_if_cached,
    )
    cached = load_accepted_generation_with_pointer_if_cached(run_dir)
    if cached is None:
        student, manifest_sha256 = load_bamf_generation_authority(
            run_dir / "bamf-state.json")
    else:
        pointer, student = cached
        manifest_sha256 = pointer["manifest_sha256"]
    from bilqis_mlx.learning._atlas_candidate.identity_binding import (
        candidate_identity_for_canonical_consumer,
    )
    return Checkpoint(
        candidate_identity_for_canonical_consumer(student.retained_state),
        f"bamf-bundles/{manifest_sha256}",
        student.retained_state.optimizer_step,
        True,
    )


def _replay_current_graph(current, parent_graph: dict) -> dict:
    from bilqis_mlx.source_adapters import copular_curriculum, event_frames

    events = tuple(
        item.capability_id for item in current.execution_plan.capabilities
        if item.capability_id in event_frames.SOURCE_SPECS)
    if events:
        graph = parent_graph
        for capability in events:
            graph = event_frames.projected_graph(graph, (capability,))
    elif copular_curriculum.PROJECTION_ADMISSION_TOKEN in current.semantic_catalog:
        graph = copular_curriculum.expanded_graph(parent_graph)
    else:
        graph = parent_graph
    current.verify_semantic_catalog(graph)
    return graph


def _persist_ready_realizations(
        run_dir: Path, current, candidate, frontier, graph: dict) -> tuple:
    from bilqis_mlx.runtime import atlas_flywheel_runtime as runtime
    sources, answers = runtime.live_source_registry(), runtime.live_answer_registry()
    staging_sources = predecessor_compatible_source_registry(current, sources)
    staged = load_staged_candidates(
        run_dir, frontier, current,
        source_registry=sources, answer_registry=answers)
    known = {item.candidate_id for item in staged}
    known_capabilities = {item.target_capability_id for item in staged}
    for semantic_id in candidate.source_eligible_concept_ids:
        try:
            capability_id = candidate_realizations.realized_capability_id(semantic_id)
        except ValueError:
            continue
        if capability_id in known_capabilities:
            continue
        try:
            candidate_realizations.project_realized_target(semantic_id, current)
        except ValueError:
            continue
        realized = candidate_realizations.prepare_realized_candidate(
            frontier, current, graph, semantic_id,
            source_root=LEGACY_SOURCE,
            source_registry=staging_sources,
            answer_registry=answers,
        )
        if realized.candidate_id not in known:
            persist_staged_candidate(run_dir, realized, frontier, current)
            known.add(realized.candidate_id)
            known_capabilities.add(realized.target_capability_id)
    return load_staged_candidates(
        run_dir, frontier, current,
        source_registry=sources, answer_registry=answers)


__all__ = (
    "_accepted_checkpoint",
    "_accepted_selection",
    "_candidate_frontier",
    "_candidate_frontier_trust_identity",
    "_persist_ready_realizations",
    "_replay_current_graph",
)
