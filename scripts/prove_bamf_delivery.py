"""C13.1 disposable integrated-delivery harness.

The public API composes existing B13/C16 owners and never targets the retained
human learner. Source fixtures stay gold-blind; owner receipts remain authority.
"""
from __future__ import annotations

import hashlib
import json
import argparse
from dataclasses import asdict
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bilqis_mlx.paths import active_run_dir
from bilqis_mlx.runtime.bamf_first_student import preflight_bamf_foundation

from scripts.bamf.c13.contracts import (
    DeliveryConfig, DeliveryReceipt, EpisodeSourceRelease, FoundationLaunchInput,
    MAX_STEPS, fail,
)
from scripts.bamf.c13.delivery_runtime import cold_restart_identity, run_candidate_attempts
from scripts.bamf.c13.probe_runtime import complete_solver_probe
from scripts.bamf.c13.episode_fixtures import (
    EpisodeBindingCase, EpisodeEvent, check_episode_binding, episode_binding_case,
    episode_task_goal, fixture_manifest,
)
from scripts.bamf.c13.enrollment_proposal import build_enrollment_proposal
from scripts.bamf.c13.foundation import prepare_episode_source_release


def _disposable(path: Path) -> Path:
    root = path.expanduser().resolve()
    retained = active_run_dir().expanduser().resolve()
    if root == retained or retained in root.parents or root in retained.parents:
        fail("BAMF_C13_RETAINED_RUN_PATH_FORBIDDEN")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _behaviors(attempts, *, baseline=None, fresh=None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    verified = tuple(item for item in attempts if item.owner_evidence_sha256 is not None)
    outcomes = {item.outcome for item in verified}
    exercised = ["SOURCE_FIXTURES", "DISPOSABLE_CREATION"]
    if baseline is not None:
        exercised.append("BASELINE_COMPLETE_SOLVER")
    if fresh is not None:
        exercised.append("FRESH_COMPLETE_SOLVER")
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
    baseline = complete_solver_probe(target, "BASELINE") if max_steps else None
    if baseline is not None and baseline.solved:
        exercised, remaining = _behaviors((), baseline=baseline)
        remaining = (*remaining, "DEPTH_ADVANCE")
        return DeliveryReceipt(
            source_release.release_sha256, source_release.semantic_release, digest,
            64, 64, max_steps, "BASELINE_SOLVED_ADVANCE_REQUIRED",
            exercised, remaining, launch, str(target.resolve()), (), None,
            baseline, None)
    attempts = run_candidate_attempts(target, max_steps) if max_steps else ()
    has_accepted = any(
        item.outcome == "ACCEPTED" and item.owner_evidence_sha256 is not None
        for item in attempts)
    fresh = complete_solver_probe(target, "FRESH") if has_accepted else None
    exercised, remaining = _behaviors(attempts, baseline=baseline, fresh=fresh)
    if any(item.owner_evidence_sha256 is not None for item in attempts) and cold_restart_identity(target):
        exercised = (*exercised, "COLD_RESTART")
        remaining = tuple(item for item in remaining if item != "COLD_RESTART")
    status = "CANDIDATE_EXERCISED" if attempts else "FOUNDATION_CREATED"
    return DeliveryReceipt(
        source_release.release_sha256, source_release.semantic_release, digest,
        64, 64, max_steps, status, exercised, remaining, launch,
        str(target.resolve()), attempts, None, baseline, fresh)


def _require_studio_host() -> None:
    hardware = subprocess.run(
        ["system_profiler", "SPHardwareDataType"],
        capture_output=True, text=True, check=True, timeout=30).stdout
    memory = int(subprocess.run(
        ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True,
        check=True, timeout=10).stdout.strip())
    if "Model Name: Mac Studio" not in hardware or memory < 96 * 1024 ** 3:
        raise RuntimeError("BAMF_C13_MAC_STUDIO_96G_REQUIRED")


def _main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the bounded C13.1 Studio witness")
    parser.add_argument("--a01", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-steps", type=int, default=2)
    args = parser.parse_args(argv)
    _require_studio_host()
    root = Path(args.out).expanduser().resolve()
    source = prepare_episode_source_release(args.a01, root)
    receipt = prove_bamf_delivery(DeliveryConfig(), source, root, args.max_steps)
    receipt_path = root / "c13-delivery-receipt.json"
    receipt_path.write_text(json.dumps(asdict(receipt), sort_keys=True, indent=2) + "\n")
    proposal_path = None
    if "APPEND_ONLY_SEMANTIC_DELTA" in receipt.remaining_behaviors:
        proposal_path = root / "c13-enrollment-proposal.json"
        proposal_path.write_text(
            json.dumps(
                build_enrollment_proposal(Path(receipt.run_dir)),
                sort_keys=True,
                indent=2,
            ) + "\n")
    print(json.dumps({
        "receipt": str(receipt_path),
        "enrollment_proposal": None if proposal_path is None else str(proposal_path),
        "status": receipt.status,
        "exercised": list(receipt.exercised_behaviors),
        "remaining": list(receipt.remaining_behaviors),
    }, sort_keys=True))
    return 0


__all__ = (
    "DeliveryConfig", "DeliveryReceipt", "EpisodeBindingCase", "EpisodeEvent",
    "EpisodeSourceRelease", "check_episode_binding", "episode_binding_case",
    "episode_task_goal", "FoundationLaunchInput", "prove_bamf_delivery",
)


if __name__ == "__main__":
    raise SystemExit(_main())
