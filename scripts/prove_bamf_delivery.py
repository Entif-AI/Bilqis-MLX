"""C13.1 disposable integrated-delivery harness.

The public API composes existing B13/C16 owners and never targets the retained
human learner. Source fixtures stay gold-blind; owner receipts remain authority.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bilqis_mlx.runtime.bamf_first_student import preflight_bamf_foundation

from scripts.bamf.c13_delivery_contracts import (
    DeliveryConfig, DeliveryReceipt, EpisodeSourceRelease, FoundationLaunchInput,
    MAX_STEPS, fail,
)
from scripts.bamf.c13_delivery_runtime import run_candidate_attempts
from scripts.bamf.c13_episode_fixtures import (
    EpisodeBindingCase, EpisodeEvent, check_episode_binding, episode_binding_case,
    episode_task_goal, fixture_manifest,
)


def _disposable(path: Path) -> Path:
    root = path.expanduser().resolve()
    retained = (Path(__file__).resolve().parents[1] / "runs").resolve()
    if root == retained or retained in root.parents:
        fail("BAMF_C13_RETAINED_RUN_PATH_FORBIDDEN")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _behaviors(attempts) -> tuple[tuple[str, ...], tuple[str, ...]]:
    outcomes = {item.outcome for item in attempts}
    exercised = ["SOURCE_FIXTURES", "DISPOSABLE_CREATION"]
    if outcomes & {"ACCEPTED", "REJECTED"}:
        exercised.extend(("SOURCE_BOUND_GRADIENTS", "PAIRED_EVALUATION"))
    if "ACCEPTED" in outcomes:
        exercised.append("ACCEPTED_CANDIDATE")
    if "REJECTED" in outcomes:
        exercised.append("REJECTED_CANDIDATE")
    required = (
        "SOURCE_BOUND_GRADIENTS", "PAIRED_EVALUATION", "ACCEPTED_CANDIDATE",
        "REJECTED_CANDIDATE", "COLD_RESTART", "APPEND_ONLY_SEMANTIC_DELTA",
    )
    return tuple(exercised), tuple(item for item in required if item not in exercised)


def prove_bamf_delivery(config, source_release, disposable_dir, max_steps) -> DeliveryReceipt:
    """Run as much of the bounded C13.1 witness as supplied authority permits."""
    if (type(config) is not DeliveryConfig
            or type(source_release) is not EpisodeSourceRelease
            or type(max_steps) is not int or not 0 <= max_steps <= MAX_STEPS):
        fail("BAMF_C13_DELIVERY_ARGUMENT_INVALID")
    root = _disposable(Path(disposable_dir))
    manifest_path = root / "c13-source-fixtures.json"
    manifest_path.write_text(
        json.dumps(fixture_manifest(config, source_release), sort_keys=True, indent=2)
        + "\n")
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if source_release.foundation is None:
        return DeliveryReceipt(
            source_release.release_sha256, source_release.semantic_release, digest,
            64, 64, max_steps, "PREPARED", ("SOURCE_FIXTURES",),
            ("DISPOSABLE_CREATION", "SOURCE_BOUND_GRADIENTS", "PAIRED_EVALUATION",
             "ACCEPTED_CANDIDATE", "REJECTED_CANDIDATE", "COLD_RESTART",
             "APPEND_ONLY_SEMANTIC_DELTA"))

    target = root / "run"
    launch = preflight_bamf_foundation(
        source_release.foundation.config,
        source_release.foundation.admitted_release,
        target)
    attempts = run_candidate_attempts(target, max_steps) if max_steps else ()
    exercised, remaining = _behaviors(attempts)
    status = "CANDIDATE_EXERCISED" if attempts else "FOUNDATION_CREATED"
    return DeliveryReceipt(
        source_release.release_sha256, source_release.semantic_release, digest,
        64, 64, max_steps, status, exercised, remaining, launch,
        str(target.resolve()), attempts)


__all__ = (
    "DeliveryConfig", "DeliveryReceipt", "EpisodeBindingCase", "EpisodeEvent",
    "EpisodeSourceRelease", "check_episode_binding", "episode_binding_case",
    "episode_task_goal", "FoundationLaunchInput", "prove_bamf_delivery",
)
