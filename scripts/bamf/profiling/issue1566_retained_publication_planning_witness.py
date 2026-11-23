#!/usr/bin/env python3
"""Disposable retained-publication planning witness for #1566.

Creates a temporary BAMF run, pays one ordinary planning pass, publishes the
source-trained candidate into that disposable lineage, advances the exact
cadence attempt, then measures the next ordinary planning pass in the same
process. The human learner is never opened or mutated.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mlx.core as mx

from bilqis_mlx.runtime.active_grade_cadence_custody import read_current_cadence
from bilqis_mlx.runtime.active_grade_cadence_projection import consume_attempt
from bilqis_mlx.runtime.bamf_operator.session import _SessionExecutionContext, prepare_bamf_visit
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.bamf_operator.session_parts.session_support import _execution_context
from bilqis_mlx.runtime.mlx_memory import training_memory_policy
from bilqis_mlx.runtime.priority_planning_owner import PriorityPlanningCache
from bilqis_mlx.runtime.teacher_observation_capture import ObservationCapture
from bilqis_mlx.runtime.tests.capability.factory.retention import retention_throughput_profile as profile
from bilqis_mlx.runtime.tests.capability.factory.retention.owner_live_support import (
    _publish_disposable_source_qualified_successor,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.teacher_custody_fixtures import (
    adaptation as fixture_adaptation,
    selection_teacher,
)

SCHEMA = "bilqis.bamf.issue1566-retained-publication-planning/v1"
ROWS = 32


class _Observer:
    def __init__(self):
        self.values = {}

    def bind_parent(self, _parent):
        return None

    def update(self, **kwargs):
        self.values.update(kwargs)


def _artifact(root: Path) -> Path:
    raw = os.environ.get("BILQIS_A01_ATLAS_BUNDLE")
    artifact = Path(raw).resolve() if raw else (
        root / "bilqis_mlx/bootstrap_assets/atlas"
        / "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7"
    ).resolve()
    if not artifact.is_dir():
        raise SystemExit(f"#1566 witness Atlas fixture is missing: {artifact}")
    return artifact


def _compatibility_delivery(original_delivery):
    def compatible_delivery(self, *args, fresh_support=(), **kwargs):
        if fresh_support:
            raise AssertionError("#1566 witness refuses non-empty fresh support")
        return original_delivery(self, *args, **kwargs)
    return compatible_delivery


def _prepare(run_dir, ordinary, planning_cache):
    observer = _Observer()
    started = time.perf_counter()
    prepared = prepare_bamf_visit(
        run_dir,
        steps_per_visit=1,
        batch_size=ROWS,
        reserve_gib=0.0,
        source_prefetch_workers=0,
        observer=observer,
        planning_cache=planning_cache,
        execution_context=ordinary,
    )
    mx.synchronize()
    return prepared, observer.values, max(0.0, time.perf_counter() - started)


def _run(root: Path, source: Path, artifact: Path) -> dict:
    compatible_delivery = _compatibility_delivery(ObservationCapture.delivery)
    bootstrap = SimpleNamespace(
        legacy_receipt={"teacher": selection_teacher()},
        adaptation=fixture_adaptation(),
        prior_region="issue1566-retained-publication-prior-region",
    )
    with training_memory_policy(mx), profile.host_source_authority_patch(), patch.object(
            ObservationCapture, "delivery", compatible_delivery), patch(
            "bilqis_mlx.runtime.foundation_teacher_owner.foundation_teacher_bootstrap",
            return_value=bootstrap), tempfile.TemporaryDirectory() as directory:
        stage = Path(directory)
        with patch.dict(os.environ, {
            "BILQIS_A01_ATLAS_BUNDLE": str(artifact),
            "BILQIS_ATLAS_REAL_ARTIFACT": str(artifact),
            "BILQIS_DATA_PLANE": str(stage / "plane.sqlite3"),
            "BILQIS_C05_PROFILE_CANDIDATE_HORIZON": "1",
        }):
            run_dir, _parent, _context = profile._prepare_run(stage, root, source, artifact)
            ordinary = _SessionExecutionContext(strict=False, loader=_execution_context)
            planning_cache = PriorityPlanningCache(run_dir)
            with evidence_mode(strict=False):
                first, first_observed, first_wall = _prepare(run_dir, ordinary, planning_cache)
                if first.selection is None or first.step is None:
                    raise AssertionError(f"first visit did not produce a candidate: {first.status}")
                cadence_record = (first.selection.metadata or {}).get("cadence")
                if not isinstance(cadence_record, dict):
                    raise AssertionError("first visit omitted cadence authorization")
                context = ordinary.snapshot[1]
                accepted_cache = context._accepted_runtime_host._accepted_cache
                published = _publish_disposable_source_qualified_successor(
                    run_dir, first.parent, accepted_cache, first.step.transaction,
                    visit=first.selection.visit,
                )[2]
                state = read_current_cadence(run_dir)
                if state is None:
                    raise AssertionError("cadence state missing after first visit")
                consume_attempt(
                    run_dir, state, cadence_record, first.capability, "RETAINED")
                ordinary.accepted_publication()
                second, second_observed, second_wall = _prepare(
                    run_dir, ordinary, planning_cache)
            if second.selection is None:
                raise AssertionError(f"second visit omitted selection: {second.status}")
            return {
                "schema": SCHEMA,
                "authorizing": False,
                "human_run_mutated": False,
                "published_disposable_generation": published["generation"],
                "first_status": first.status,
                "first_capability": first.capability,
                "first_planning_wall_seconds": first_observed.get("planning_wall_seconds"),
                "first_full_prepare_wall_seconds": first_wall,
                "second_status": second.status,
                "second_capability": second.capability,
                "second_planning_wall_seconds": second_observed.get("planning_wall_seconds"),
                "second_full_prepare_wall_seconds": second_wall,
                "planning_cache": planning_cache.metrics(),
            }


def main() -> int:
    if not mx.metal.is_available():
        raise SystemExit("#1566 witness requires Apple Metal")
    root = Path.cwd().resolve()
    source = (root / "vendor/legacy-v16").resolve()
    artifact = _artifact(root)
    previous = mx.default_device()
    mx.set_default_device(mx.gpu)
    try:
        receipt = _run(root, source, artifact)
        print("ISSUE1566_RETAINED_PUBLICATION_PLANNING " + json.dumps(receipt, sort_keys=True), flush=True)
        return 0
    finally:
        mx.set_default_device(previous)


if __name__ == "__main__":
    raise SystemExit(main())
