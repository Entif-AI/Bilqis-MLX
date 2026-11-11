"""Production C02 composition for one source-qualified BAMF candidate step."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import time

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_engram import MOTIF_PAGE_STATE_BYTES, MotifBudget
from bilqis_mlx.runtime.atlas_model import bamf_value_and_grad
from bilqis_mlx.runtime.atlas_resources import (
    FrameStats, MemoryBudget, ResourceRow, plan_microbatches,
)
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle import (
    CompleteStudent, authenticate_bamf_execution_feature_context,
    seal_source_qualified_motifs_from_bundle,
    stage_source_qualified_motif_allocation,
)
from bilqis_mlx.runtime.bamf_bundle.admission import (
    admit_uninterrupted_candidate_step, bind_accepted_execution_cache,
)
from bilqis_mlx.runtime.factory_task_authority import (
    bind_factory_task_compiled_batch, factory_task_authority,
    factory_task_training_goal,
)
from bilqis_mlx.runtime.model_topology_v2 import bamf_parameter_census
from bilqis_mlx.runtime.task_goal_readout import (
    task_goal_route_plan, task_goal_training_targets,
)
from bilqis_mlx.semantics.frame_compiler import PositionKind

from .atlas_training_delivery import capture_realized_delivery
from .factory_training_bridge import (
    PreparedFactoryTrainingBatch, prepare_factory_training_batch,
)
from .atlas_visit_provenance import BamfVisitProvenance


def _invalid(reason: str):
    ErrorBus.raise_(SCHOOL.BAMF_TRAINING_ADAPTER.INVALID, reason=reason)


@dataclass(frozen=True)
class FactoryDeliveryObservation:
    """Existing #333 capture coordinates for one realized C02 delivery."""

    capture: object
    step: int
    option_rows: tuple
    seed: int
    priority: tuple = ()
    preservation: tuple = ()
    support: tuple = ()
    enrichment: tuple = ()
    guidance: object = None
    controls: dict = field(default_factory=dict)
    prior: tuple = ()
    mentors: object = None

    def __post_init__(self):
        if (type(self.step) is not int or self.step < 1
                or type(self.seed) is not int or self.seed < 0
                or type(self.option_rows) is not tuple or not self.option_rows
                or not isinstance(self.controls, dict)):
            _invalid("FACTORY_TRAINING_OBSERVATION_INVALID")


@dataclass(frozen=True)
class FactoryCandidateStep:
    """One non-published BAMF candidate step plus its C02/C08 evidence."""

    prepared: PreparedFactoryTrainingBatch
    resource_plan: object
    task_authority: object
    route_targets: tuple
    gradient_execution: object
    transaction: object
    realized_cost: dict


def _frame_stats(compiled_batch) -> FrameStats:
    row = compiled_batch.compiled.compiled.rows[0]
    compiled_batch.compiled.packed_frame_artifact_owner.require_row(row)
    closures = tuple(
        position for position in row.positions
        if position.kind is PositionKind.CLOSURE)
    frame_lengths = tuple(
        max(1, position.packed.sidecar.source_span.end
            - position.packed.sidecar.source_span.start)
        for position in closures)
    if not frame_lengths:
        frame_lengths = (1,) * len(row.positions)
    return FrameStats(
        compiled_positions=len(row.positions),
        frame_lengths=frame_lengths,
        constituent_expansions=sum(
            len(position.packed.sidecar.constituents) for position in closures),
        # Every visible neural position retains one summary per configured depth
        # group; C08 multiplies this position count by topology.depth_groups.
        depth_summaries=len(row.positions),
    )


def _resource_plan(prepared, parent, memory_budget):
    if memory_budget is None:
        memory_budget = MemoryBudget(
            bamf_parameter_census(parent.topology, parent.extents))
    elif not isinstance(memory_budget, MemoryBudget):
        _invalid("FACTORY_TRAINING_MEMORY_BUDGET_INVALID")
    rows = tuple(
        ResourceRow.from_training_row(
            training_row, _frame_stats(compiled),
            generation_binding=prepared.training_batch.generation_binding,
            delivered_content_sha256=prepared.training_batch.delivered_content_sha256,
        )
        for training_row, compiled in zip(
            prepared.training_batch.rows, prepared.compiled_rows))
    return plan_microbatches(rows, parent.topology, memory_budget), memory_budget


def _stage_retained_motifs(run_dir, parent, cache, transaction, prepared,
                           resource_plan, memory_budget):
    if len(prepared.motif_inputs) != 1:
        _invalid("FACTORY_CANDIDATE_STEP_MOTIF_ACCUMULATION_REQUIRED")
    motif = prepared.motif_inputs[0]
    spare = max(0, memory_budget.allocation_bytes - resource_plan.estimated_peak_bytes)
    budget = MotifBudget(
        64,
        page_growth_bytes=(MOTIF_PAGE_STATE_BYTES
                           if spare >= MOTIF_PAGE_STATE_BYTES else 0))
    bundle_root = Path(run_dir) / "bamf-bundles" / cache.accepted_manifest_sha256
    result = seal_source_qualified_motifs_from_bundle(
        motif.source_adapter, motif.row, motif.atlas_selection,
        retained_bundle_root=bundle_root,
        expected_manifest_sha256=cache.accepted_manifest_sha256,
        source_root=motif.source_root, graph=motif.source_graph,
        task_scope=motif.task, source_frontier=motif.frontier,
        policy=motif.policy, source_seed=motif.source_seed,
        source_each=motif.source_each, budget=budget,
        source_profile_parameters=motif.source_profile_parameters,
        course=motif.course)
    from bilqis_mlx.semantics.context_eligibility import ContextHold
    if isinstance(result, ContextHold):
        _invalid("FACTORY_CANDIDATE_STEP_MOTIF_CONTEXT_HELD")
    continuation, _ = result
    if continuation.approved.candidate.proposed.digest == parent.retained_state.allocations.digest:
        return transaction
    return stage_source_qualified_motif_allocation(
        Path(run_dir), transaction, continuation)


def _execute_prepared_candidate(
        run_dir, source_context, parent, atlas_artifact_path, delivered_rows, *,
        capability, teacher_hparams, max_norm, observation, memory_budget,
        cache, generation, prepared, start) -> FactoryCandidateStep:
    resource_plan, memory_budget = _resource_plan(prepared, parent, memory_budget)
    if (len(prepared.compiled_rows) != 1
            or resource_plan.groups != ((0,),)):
        _invalid("FACTORY_CANDIDATE_STEP_C08_ACCUMULATION_REQUIRED")

    compiled = prepared.compiled_rows[0]
    authority = factory_task_authority(source_context, compiled)
    compiled = bind_factory_task_compiled_batch(compiled, authority)
    resolved = factory_task_training_goal(source_context, compiled, authority)
    targets, mask = task_goal_training_targets(authority.goal, resolved)
    feature_context = authenticate_bamf_execution_feature_context(
        parent, atlas_artifact_path, source_context.run_dir)
    plan = task_goal_route_plan(
        authority.goal, compiled, feature_context.snapshot, generation)
    gradient = bamf_value_and_grad(
        dict(parent.retained_state.optimizer.parameters),
        compiled, plan, targets, mask, cache)
    transaction = admit_uninterrupted_candidate_step(
        Path(run_dir), parent, loss_bearing_target=True,
        gradient_execution=gradient, teacher_hparams=teacher_hparams,
        max_norm=max_norm)
    transaction = _stage_retained_motifs(
        run_dir, parent, cache, transaction, prepared, resource_plan, memory_budget)
    cost = {
        "wall_seconds": time.perf_counter() - start,
        "loss_total": float(gradient.loss_total.item()),
        "c08_estimated_peak_bytes": resource_plan.estimated_peak_bytes,
        "optimizer_steps": transaction.update_steps,
    }
    capture_realized_delivery(
        prepared.training_batch, source_context, observation.capture,
        capability, observation.step, tuple(delivered_rows),
        generation_binding=generation, option_rows=observation.option_rows,
        priority=observation.priority, preservation=observation.preservation,
        support=observation.support, enrichment=observation.enrichment,
        guidance=observation.guidance, controls=observation.controls,
        seed=observation.seed, cost=cost, prior=observation.prior,
        mentors=observation.mentors)
    return FactoryCandidateStep(
        prepared, resource_plan, authority, targets,
        gradient, transaction, cost)


def execute_factory_candidate_step(
    run_dir: Path,
    source_context,
    parent: CompleteStudent,
    atlas_artifact_path: str,
    feature_artifact_path: str,
    delivered_rows,
    *,
    capability: str,
    delivery,
    requested_count: int,
    source_seed: int,
    source_each: int,
    optimizer_step_seed: int,
    visit_provenance: BamfVisitProvenance,
    teacher_strategy: dict,
    teacher_hparams,
    max_norm: float,
    observation: FactoryDeliveryObservation,
    rehearsal_by_id: dict | None = None,
    memory_budget: MemoryBudget | None = None,
) -> FactoryCandidateStep:
    """Compose C02→C08→B10/B11→candidate custody without publishing state.

    B11 currently issues one source-qualified compiled row per gradient witness.
    C08 planning therefore runs over the complete delivered batch first, but a
    multi-row or split plan fails closed before neural execution until the C08/B11
    tree-gradient accumulator owns that one-logical-batch/one-AdamW-step seam.
    """
    if (not isinstance(parent, CompleteStudent)
            or not isinstance(observation, FactoryDeliveryObservation)):
        _invalid("FACTORY_CANDIDATE_STEP_INPUT_INVALID")
    source_context.require_accepted_runtime(Path(run_dir))
    start = time.perf_counter()
    cache = bind_accepted_execution_cache(Path(run_dir))
    generation = execution_generation_digest(
        parent.retained_state.optimizer.parameters,
        spec=parent.topology, extents=parent.extents)
    if cache.generation_binding != generation:
        _invalid("FACTORY_CANDIDATE_STEP_GENERATION_DRIFT")
    prepared = prepare_factory_training_batch(
        source_context, parent, atlas_artifact_path, feature_artifact_path,
        delivered_rows, generation, capability=capability, delivery=delivery,
        requested_count=requested_count, source_seed=source_seed,
        source_each=source_each, optimizer_step_seed=optimizer_step_seed,
        visit_provenance=visit_provenance,
        teacher_strategy=teacher_strategy,
        rehearsal_by_id=rehearsal_by_id)
    return _execute_prepared_candidate(
        run_dir, source_context, parent, atlas_artifact_path, delivered_rows,
        capability=capability, teacher_hparams=teacher_hparams,
        max_norm=max_norm, observation=observation, memory_budget=memory_budget,
        cache=cache, generation=generation, prepared=prepared, start=start)


__all__ = (
    "FactoryCandidateStep", "FactoryDeliveryObservation",
    "execute_factory_candidate_step",
)
