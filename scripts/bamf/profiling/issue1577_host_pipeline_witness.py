#!/usr/bin/env python3
"""Disposable M3 Ultra parity witness for issue #1577 host/Metal overlap."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import mlx.core as mx

from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.learning.atlas_retention_decision import issue_factory_retention_decision
from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache
from bilqis_mlx.runtime.bamf_operator.session import _execution_context
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.bamf_operator.session_parts.pipeline import (
    CandidateHostPreparationPipeline,
)
from bilqis_mlx.runtime.bamf_operator.source_prefetch import (
    CandidateLessonRows,
    SourcePrefetchMetrics,
)
from bilqis_mlx.runtime.factory_candidate_components import FactoryDeliveryObservation
from bilqis_mlx.runtime.factory_candidate_training import execute_factory_candidate_step
from bilqis_mlx.runtime.factory_retention_owner import (
    bind_current_retention_protection_plan,
    bind_current_retention_source_rows,
    evaluate_factory_retention_candidate,
)
from bilqis_mlx.runtime.factory_training_bridge import LearningFirstPreparationCache
from bilqis_mlx.runtime.factory_training_preparation import (
    prepare_learning_first_source_inputs_ahead,
)
from bilqis_mlx.runtime.priority_authority import _offer_seed
from bilqis_mlx.runtime.teacher_observation_capture import (
    ObservationCapture,
    store_sidecar,
)
from bilqis_mlx.runtime.tests.batch.training.visit_provenance_support import (
    visit_provenance,
)

SOURCE_RUN = Path("/Users/emilie/Code/bilqis-mlx-runs/aspirant")
CAPABILITY = "A.EDGE"
LOGICAL_ROWS = 32
HORIZON = 2
MAX_NORM = 1.0



def _passive_capture(run_dir: Path, capability: str, source_seed: int):
    """Build a contract-valid capture, then suppress observation persistence."""
    capture = ObservationCapture(run_dir, {})
    capture.attempt_id = f"issue1577:{capability}:{source_seed}"
    capture.proposal_id = store_sidecar(
        run_dir, {"attempt_id": capture.attempt_id})["sha256"]
    capture.select_option(capability, None)
    capture.enabled = False
    # Current main's capture_realized_delivery() supplies fresh_support, while
    # ObservationCapture.delivery() has not yet grown that keyword. This witness
    # is deliberately non-persistent, so adapt only this disposable instance.
    capture.delivery = lambda *_args, **_kwargs: None
    return capture


class _StaticLane:
    def __init__(self, rows):
        self.rows = tuple(rows)

    def lesson(self, ordinal):
        return CandidateLessonRows(
            self.rows,
            prefetch_identity=f"{ordinal:064x}",
        )


def _clone_run(destination: Path) -> None:
    subprocess.run(["cp", "-cR", str(SOURCE_RUN), str(destination)], check=True)


def _pipeline_kwargs(pipeline, ordinal):
    if pipeline is None:
        return {}
    host = pipeline.take(ordinal)
    pipeline.submit(ordinal + 1)
    return {
        "prepared_learning_first_source_inputs": host.prepared_source_inputs,
        "prepared_learning_first_source_identity": host.source_identity,
        "pipeline_host_preparation_wall_seconds": host.preparation_wall_seconds,
        "pipeline_host_overlap_wall_seconds": host.overlap_wall_seconds,
        "pipeline_host_wait_wall_seconds": host.host_wait_wall_seconds,
        "pipeline_accelerator_wait_for_host_wall_seconds":
            host.host_wait_wall_seconds,
    }


def _run_steps(
        run_dir, context, parent, atlas_path, feature_path, rows, source_seed,
        source_authority, delivery, visit, semantic_context, accepted_cache,
        learning_cache, capture, pipeline):
    candidate = None
    results = []
    with evidence_mode(strict=False):
        if pipeline is not None:
            pipeline.submit(1)
        try:
            for ordinal in range(1, HORIZON + 1):
                step_started = time.perf_counter()
                observation = FactoryDeliveryObservation(
                    capture, ordinal, rows, source_seed)
                result = execute_factory_candidate_step(
                    run_dir, context, parent, atlas_path, feature_path, rows,
                    capability=CAPABILITY, delivery=delivery,
                    requested_count=len(rows), source_seed=source_seed,
                    source_each=LOGICAL_ROWS, optimizer_step_seed=234 + ordinal,
                    visit_provenance=visit,
                    teacher_strategy={
                        "policy": "issue1577-host-pipeline",
                        "lr": parent.optimizer_hyperparameters.learning_rate,
                    },
                    teacher_hparams=parent.optimizer_hyperparameters,
                    max_norm=MAX_NORM, observation=observation,
                    candidate=candidate, finalize_candidate=(ordinal == HORIZON),
                    candidate_step_started_at=step_started,
                    semantic_context=semantic_context, accepted_cache=accepted_cache,
                    selected_source_authority=source_authority,
                    learning_first_cache=learning_cache,
                    **_pipeline_kwargs(pipeline, ordinal),
                )
                candidate = result.transaction
                results.append(result)
        finally:
            if pipeline is not None:
                pipeline.close()
    return candidate, tuple(results)


def _case(root: Path, *, pipelined: bool):
    run_dir = root / ("pipeline" if pipelined else "control")
    _clone_run(run_dir)
    parent, context, atlas_path, feature_path = _execution_context(run_dir)
    next_seed = parent.teacher_state["next_seed"]
    source_seed = _offer_seed(next_seed, CAPABILITY)
    rows, source_authority = context.draw_bound_rows(
        seed=source_seed, capability=CAPABILITY, each=LOGICAL_ROWS)
    rows = tuple(rows)
    execution = context.release.execution_plan.capability_map[CAPABILITY]
    delivery = describe_delivered_teaching(
        context.release, CAPABILITY, execution.teaching_option_ids[0], rows)
    visit = visit_provenance(
        CAPABILITY,
        run_seed=parent.run_identity.run_seed,
        generation=parent.generation,
        selection_seed=next_seed,
        policy_key="issue1577-host-pipeline",
    )
    accepted_cache = bind_accepted_execution_cache(run_dir)
    bind_current_retention_protection_plan(context, parent, accepted_cache)
    bind_current_retention_source_rows(context, accepted_cache, CAPABILITY)
    semantic_context = context._accepted_feature_context
    learning_cache = LearningFirstPreparationCache()
    metrics = SourcePrefetchMetrics()
    capture = _passive_capture(run_dir, CAPABILITY, source_seed)
    pipeline = None
    if pipelined:
        lane = _StaticLane(rows)

        def prepare(_ordinal, lesson):
            return prepare_learning_first_source_inputs_ahead(
                context, semantic_context, lesson.delivered,
                source_seed=source_seed, source_each=LOGICAL_ROWS,
                source_identity=lesson.prefetch_identity)

        pipeline = CandidateHostPreparationPipeline(
            lane, HORIZON, prepare, metrics)

    candidate, results = _run_steps(
        run_dir, context, parent, atlas_path, feature_path, rows, source_seed,
        source_authority, delivery, visit, semantic_context, accepted_cache,
        learning_cache, capture, pipeline)

    evaluation = evaluate_factory_retention_candidate(
        context, candidate, atlas_path, CAPABILITY, run_dir=run_dir)
    decision = issue_factory_retention_decision(evaluation)
    return {
        "parent": parent,
        "results": results,
        "candidate": candidate,
        "metrics": metrics,
        "decision": decision.to_record(),
    }


def main() -> int:
    if not SOURCE_RUN.is_dir():
        raise RuntimeError(f"missing accepted aspirant run: {SOURCE_RUN}")
    root = Path(tempfile.mkdtemp(prefix="bilqis-1577-host-pipeline-"))
    try:
        control = _case(root, pipelined=False)
        pipeline = _case(root, pipelined=True)
        control_candidate = control["candidate"]
        pipeline_candidate = pipeline["candidate"]
        mx.eval(
            control_candidate.optimizer.parameters,
            pipeline_candidate.optimizer.parameters,
        )
        parameter_equal = all(
            bool(mx.array_equal(
                control_candidate.optimizer.parameters[name],
                pipeline_candidate.optimizer.parameters[name],
            ))
            for name in control_candidate.optimizer.parameters
        )
        update_counts_equal = all(
            bool(mx.array_equal(
                control_candidate.optimizer.update_counts[name],
                pipeline_candidate.optimizer.update_counts[name],
            ))
            for name in control_candidate.optimizer.update_counts
        )
        control_losses = tuple(
            float(result.realized_cost["loss_total"])
            for result in control["results"])
        pipeline_losses = tuple(
            float(result.realized_cost["loss_total"])
            for result in pipeline["results"])
        metrics = pipeline["metrics"]
        receipt = {
            "schema": "bilqis.issue1577.host-pipeline-witness/v1",
            "source_optimizer_step":
                control["parent"].retained_state.optimizer_step,
            "logical_rows": LOGICAL_ROWS,
            "horizon": HORIZON,
            "control_losses": control_losses,
            "pipeline_losses": pipeline_losses,
            "losses_equal": control_losses == pipeline_losses,
            "parameter_equal": parameter_equal,
            "update_counts_equal": update_counts_equal,
            "control_retention_decision": control["decision"],
            "pipeline_retention_decision": pipeline["decision"],
            "retention_decisions_equal":
                control["decision"] == pipeline["decision"],
            "control_step_wall_seconds": tuple(
                float(result.realized_cost["candidate_step_wall_seconds"])
                for result in control["results"]),
            "pipeline_step_wall_seconds": tuple(
                float(result.realized_cost["candidate_step_wall_seconds"])
                for result in pipeline["results"]),
            "pipeline_host_preparation_seconds":
                metrics.pipeline_host_preparation_seconds,
            "pipeline_host_overlap_seconds":
                metrics.pipeline_host_overlap_seconds,
            "pipeline_host_wait_seconds":
                metrics.pipeline_host_wait_seconds,
            "pipeline_accelerator_wait_for_host_seconds":
                metrics.pipeline_accelerator_wait_for_host_seconds,
            "pipeline_prepared_steps": metrics.pipeline_prepared_steps,
            "pipeline_discarded_steps": metrics.pipeline_discarded_steps,
            "control_update_steps": control_candidate.update_steps,
            "pipeline_update_steps": pipeline_candidate.update_steps,
        }
        print(json.dumps(receipt, sort_keys=True), flush=True)
        assert receipt["losses_equal"], receipt
        assert parameter_equal and update_counts_equal, receipt
        assert receipt["retention_decisions_equal"], receipt
        assert control_candidate.update_steps == HORIZON, receipt
        assert pipeline_candidate.update_steps == HORIZON, receipt
        assert metrics.pipeline_host_overlap_seconds > 0.0, receipt
        assert metrics.pipeline_prepared_steps == HORIZON, receipt
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
