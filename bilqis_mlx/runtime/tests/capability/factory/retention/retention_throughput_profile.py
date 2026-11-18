"""Disposable native C05 throughput profile for issue #1389.

This witness creates a temporary generation, performs one genuine source-owned
GPU candidate update, then invokes the production Factory C05 owner without
publishing the candidate.  It emits one machine-readable profile for comparable
before/after runs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import resource
import tempfile
import time

import mlx.core as mx

from bilqis_mlx.learning._retention.atlas_retention_decision import (
    issue_factory_retention_decision,
)
from bilqis_mlx.learning.source_atoms.tests.backbone_test_support import (
    SourceBackboneTestBase,
)
from bilqis_mlx.runtime.factory_retention_owner import (
    evaluate_factory_retention_candidate,
)
from bilqis_mlx.runtime.tests.capability.factory.retention.factory_retention_live_support import (
    live_factory_context,
)
from bilqis_mlx.runtime.tests.capability.factory.retention.owner_live_support import (
    TARGET, _initialize_generation,
    _teacher_selected_source_owned_candidate_step_evidence,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.publication.publication_helpers import (
    host_source_authority_patch,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import AUTHORITY


def _memory() -> dict[str, int]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "mlx_active_bytes": int(mx.get_active_memory()),
        "mlx_cache_bytes": int(mx.get_cache_memory()),
        "mlx_peak_bytes": int(mx.get_peak_memory()),
        "host_peak_rss_bytes": int(
            usage.ru_maxrss if os.uname().sysname == "Darwin" else usage.ru_maxrss * 1024),
    }


def main() -> int:
    artifact_raw = os.environ.get("BILQIS_A01_ATLAS_BUNDLE")
    if not artifact_raw:
        raise SystemExit("BILQIS_A01_ATLAS_BUNDLE is required")
    artifact = Path(artifact_raw).resolve()
    if not artifact.is_dir():
        raise SystemExit(f"BILQIS_A01_ATLAS_BUNDLE is not a directory: {artifact}")
    if not mx.metal.is_available():
        raise SystemExit("Apple Metal is required")

    previous_device = mx.default_device()
    mx.set_default_device(mx.gpu)
    fixture = SourceBackboneTestBase()
    try:
        fixture.setUp()
        root = Path.cwd()
        source = (root / "vendor/legacy-v16").resolve()
        if not source.is_dir():
            raise SystemExit("pinned vendor/legacy-v16 source fixture is required")
        with host_source_authority_patch(AUTHORITY), tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            source_context, _manifest = live_factory_context(root, source)
            parent, cache, source_context = _initialize_generation(
                run_dir, source_context, fixture.snapshot, artifact)

            mx.clear_cache()
            mx.reset_peak_memory()
            attempt_started = time.perf_counter()
            training_started = time.perf_counter()
            transaction, _gradient, _row, _targets, teacher = (
                _teacher_selected_source_owned_candidate_step_evidence(
                    run_dir, source_context, parent, cache, artifact))
            mx.synchronize()
            training_wall = max(0.0, time.perf_counter() - training_started)

            observed: list[dict] = []
            retention_started = time.perf_counter()
            evaluation = evaluate_factory_retention_candidate(
                source_context, transaction, str(artifact), TARGET,
                run_dir=run_dir, observer=observed.append)
            mx.synchronize()
            retention_wall = max(0.0, time.perf_counter() - retention_started)
            issued = issue_factory_retention_decision(evaluation)
            attempt_wall = max(0.0, time.perf_counter() - attempt_started)

            profile = {}
            for event in observed:
                profile.update(event)
            decision = evaluation.decision
            accepted = bool(issued.accepted)
            steps_per_hour = 3600.0 / attempt_wall if attempt_wall > 0 else None
            receipt = {
                "schema": "bilqis.mlx.c05-retention-throughput-profile/v1",
                "authorizing": False,
                "published": False,
                "target_capability": TARGET,
                "candidate_update_steps": transaction.update_steps,
                "teacher_policy_key": teacher["policy_key"],
                "training_wall_seconds": training_wall,
                "retention_wall_seconds": retention_wall,
                "attempt_wall_seconds": attempt_wall,
                "attempted_steps_per_hour": steps_per_hour,
                "retained_steps_per_hour": steps_per_hour if accepted else 0.0,
                "accepted": accepted,
                "decision_status": decision.status.value,
                "decision_reason": decision.reason,
                "outcome_scores": [list(item) for item in decision.outcome_scores],
                "evaluated_capability_ids": list(decision.evaluated_capability_ids),
                "evidence_sha256": decision.evidence_sha256,
                "policy_sha256": decision.policy_sha256,
                "retention_protection_plan_sha256": (
                    decision.retention_protection_plan_sha256),
                "parent_generation": decision.parent_generation,
                "candidate_generation": decision.candidate_generation,
                "parent_candidate_sha256": evaluation.parent_candidate_sha256,
                "candidate_candidate_sha256": evaluation.candidate_candidate_sha256,
                "parent_cache_receipt_reused": (
                    evaluation.parent_assessment_cache.reused
                    if evaluation.parent_assessment_cache is not None else None),
                "profile": profile,
                "memory": _memory(),
                "mlx_default_device": str(mx.default_device()),
            }
            print("C05_RETENTION_THROUGHPUT_PROFILE " + json.dumps(
                receipt, sort_keys=True), flush=True)
    finally:
        fixture.doCleanups()
        mx.set_default_device(previous_device)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
