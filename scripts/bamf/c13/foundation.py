"""Build one truthful disposable C13 source authority and B13 launch input."""
from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path

import mlx.core as mx
import mlx.optimizers as optim

from bilqis_mlx.runtime.admission import _executable_factory_admission
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters
from bilqis_mlx.runtime.bamf_first_student import BamfFoundationConfig
from bilqis_mlx.runtime.checkpoints import _bundle_pointer as bundle_pointer
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactIdentity, load_atlas_snapshot
from bilqis_mlx.state_dag import persist

from scripts.bamf.c13.contracts import EpisodeSourceRelease, FoundationLaunchInput
from scripts.bamf.c13.episode_source import episode_factory_release


PRODUCTION_RESERVE_GIB = 100.0
C13_RUN_SEED = 52813
C13_LEARNING_RATE = 1e-6


def _source_origin(source_run: Path, graph: dict, reserve_gib: float):
    """Mint a real step-zero model+AdamW checkpoint solely for B13 provenance."""
    parameters = {
        "embedding.weight": mx.zeros((len(graph["tokens"]), 1), dtype=mx.float32),
    }
    optimizer = optim.AdamW(
        learning_rate=C13_LEARNING_RATE,
        betas=(.9, .95),
        eps=1e-8,
        weight_decay=.01,
        bias_correction=True,
    )
    optimizer.init(parameters)
    mx.eval(parameters, optimizer.state)
    return bundle_pointer(
        source_run,
        "origin",
        parameters,
        optimizer,
        graph,
        reserve_gib=reserve_gib,
    )


def prepare_episode_source_release(
    a01_artifact: str | Path,
    root: str | Path,
    *,
    run_seed: int = C13_RUN_SEED,
    reserve_gib: float = PRODUCTION_RESERVE_GIB,
) -> EpisodeSourceRelease:
    """Persist the live C13 release as B13-readable disposable source authority."""
    root = Path(root).expanduser().resolve()
    artifact = Path(a01_artifact).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("BAMF_C13_STUDIO_WITNESS_ROOT_NOT_EMPTY")
    root.mkdir(parents=True, exist_ok=True)
    snapshot = load_atlas_snapshot(artifact)
    os.environ["BILQIS_A01_ATLAS_BUNDLE"] = str(artifact)
    os.environ["BILQIS_ATLAS_REAL_ARTIFACT"] = str(artifact)
    os.environ.setdefault("BILQIS_DATA_PLANE", str(root / "plane.sqlite3"))

    release, graph, _sources, _answers = episode_factory_release(depths=(1,))
    source_run = root / "source-authority"
    source_run.mkdir()
    origin = _source_origin(source_run, graph, reserve_gib)
    _state, release_file, admission = _executable_factory_admission(
        source_run, release, origin, _fingerprint(graph), graph)
    persist(source_run, {
        "generation": 0,
        "factory_release_sha256": release.release_sha256,
        "factory_release_file": release_file,
        "factory_admission_v2": asdict(admission),
        "semantic_graph_sha256": _fingerprint(graph),
        "school": {"current_student": asdict(origin)},
        "result": "READY_FOR_BAMF_FOUNDATION",
    })
    identity = AtlasArtifactIdentity(
        snapshot.bundle_id, snapshot.release_sha256, snapshot.source_bundle_id)
    config = BamfFoundationConfig(
        str(source_run),
        "bamf-c13-528-disposable",
        run_seed,
        graph,
        identity,
        AdamWHyperparameters(C13_LEARNING_RATE, (.9, .95), 1e-8, .01),
    )
    return EpisodeSourceRelease(
        release.release_sha256,
        snapshot.release_sha256,
        FoundationLaunchInput(config, release),
    )


__all__ = (
    "C13_LEARNING_RATE", "C13_RUN_SEED", "PRODUCTION_RESERVE_GIB",
    "prepare_episode_source_release",
)
