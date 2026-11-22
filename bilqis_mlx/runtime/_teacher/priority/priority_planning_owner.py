"""Accepted A09 planning projection consumed by C03.4 priority authority."""
from dataclasses import dataclass, field
from pathlib import Path

from bilqis_mlx.errors import BilqisError, ErrorBus, SCHOOL


def _invalid(reason):
    ErrorBus.Raise(SCHOOL.BAMF_CURRICULUM.INVALID, reason=reason)


def _emit_progress(progress, message):
    if progress is not None:
        progress(message)


@dataclass(frozen=True)
class PriorityPlanningEpoch:
    current_release: object
    candidate_set: object
    snapshot: object
    closure: object
    requested_keys: tuple
    accepted_credit: object | None
    autonomy_plan: object
    evidence_ledger: object
    checkpoint: object
    source_authority: object


@dataclass
class PriorityPlanningCache:
    """Process-live derived planning products with exact invalidation keys.

    This cache owns no authority. Cold resume starts empty, every visit still
    binds current B13/C09 custody, and final lawful-frontier sealing rebinds the
    current autonomy/active-grade witnesses. Each layer retains exactly one
    current derived value; replacement publishes only after full derivation.
    """

    run_dir: Path
    static_hits: int = 0
    static_misses: int = 0
    snapshot_hits: int = 0
    snapshot_misses: int = 0
    closure_hits: int = 0
    closure_misses: int = 0
    planning_hits: int = 0
    planning_misses: int = 0
    _static_key: tuple | None = field(default=None, init=False, repr=False)
    _candidate_set: object | None = field(default=None, init=False, repr=False)
    _candidate_frontier: object | None = field(default=None, init=False, repr=False)
    _staged_candidates: tuple | None = field(default=None, init=False, repr=False)
    _autonomy_plan: object | None = field(default=None, init=False, repr=False)
    _snapshot_key: tuple | None = field(default=None, init=False, repr=False)
    _snapshot: object | None = field(default=None, init=False, repr=False)
    _closure_key: tuple | None = field(default=None, init=False, repr=False)
    _closure: object | None = field(default=None, init=False, repr=False)
    _planning_key: tuple | None = field(default=None, init=False, repr=False)
    _planning: object | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self.run_dir = Path(self.run_dir).resolve()

    def metrics(self) -> dict[str, int]:
        return {
            "static_hits": self.static_hits,
            "static_misses": self.static_misses,
            "snapshot_hits": self.snapshot_hits,
            "snapshot_misses": self.snapshot_misses,
            "closure_hits": self.closure_hits,
            "closure_misses": self.closure_misses,
            "planning_hits": self.planning_hits,
            "planning_misses": self.planning_misses,
        }


def _require_cache(cache, run_dir):
    if cache is None:
        return None
    if (type(cache) is not PriorityPlanningCache
            or cache.run_dir != Path(run_dir).resolve()):
        _invalid("BAMF_PRIORITY_PLANNING_CACHE_INVALID")
    return cache


def _static_key(
        current, selection, feature_receipt, source, frontier_trust_identity):
    from bilqis_mlx.semantics.domains import contract_digest

    return (
        current.release_sha256,
        selection.bundle_id,
        selection.release_sha256,
        selection.source_bundle_id,
        feature_receipt.source_atlas_bundle_id,
        feature_receipt.source_release_sha256,
        feature_receipt.source_source_bundle_id,
        contract_digest(source.frontier),
        contract_digest(source.policy),
        source.authority_registry_sha256,
        frontier_trust_identity,
    )


def _closure_key(snapshot, current, plan, checkpoint, ledger):
    from bilqis_mlx.factory.autonomy import evidence_complete_capabilities

    mastered = evidence_complete_capabilities(
        current, ledger, plan=plan,
        current_checkpoint_sha256=checkpoint.sha256,
        current_optimizer_step=checkpoint.optimizer_step,
    )
    return (
        snapshot.snapshot_sha256,
        current.release_sha256,
        plan.digest(),
        checkpoint.sha256,
        checkpoint.optimizer_step,
        mastered,
    )


def _snapshot_key(static_key, feature_receipt):
    return (
        static_key,
        feature_receipt.generation_manifest_sha256,
        feature_receipt.acceptance_sha256,
    )


def _accepted_credit_key(accepted_credit):
    if accepted_credit is None:
        return None
    accepted_credit.__post_init__()
    from bilqis_mlx.semantics.domains import contract_digest
    return contract_digest((
        "bilqis.bamf.priority-accepted-credit-key/v1",
        accepted_credit.schema,
        accepted_credit.factory_release_sha256,
        accepted_credit.acceptance_sha256,
        accepted_credit.obligation_keys,
    ))


def _planning_key(epoch):
    return (
        epoch.current_release.release_sha256,
        epoch.snapshot.snapshot_sha256,
        epoch.closure.closure_sha256,
        epoch.requested_keys,
        _accepted_credit_key(epoch.accepted_credit),
    )


def build_priority_planning_epoch(
        run_dir, source_context, atlas_artifact_path, progress=None, *,
        authenticated_features=None, planning_cache=None):
    """Derive the exact accepted A09 epoch once for planning/frontier consumers."""
    from bilqis_mlx.factory.atlas_delta_adapter import (
        AtlasCoverageEpoch, _accepted_requested_keys,
    )
    from bilqis_mlx.factory.atlas_frontier import PlannerBudget
    from bilqis_mlx.factory.atlas_frontier_closure import resolve_frontier_closure
    from bilqis_mlx.factory.atlas_runtime_snapshot import build_accepted_executable_snapshot
    from bilqis_mlx.factory.skos_curriculum import (
        LearnedFrontier, SOURCE_FAMILY_ADAPTERS,
        _compile_semantic_curriculum_snapshot, compile_semantic_curriculum,
        issue_source_context_transition_authority,
    )
    from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_obligation_credit
    from bilqis_mlx.runtime.atlas_flywheel_runtime import (
        _accepted_checkpoint, _accepted_selection, _candidate_frontier,
        _candidate_frontier_trust_identity, _persist_ready_realizations,
    )
    from bilqis_mlx.runtime._autonomy_live.planning import (
        build_live_autonomy_plan, reconcile_live_autonomy_state,
    )

    planning_cache = _require_cache(planning_cache, run_dir)
    _emit_progress(progress, "planner: resolving accepted atlas selection")
    if authenticated_features is None:
        selection, feature_receipt = _accepted_selection(run_dir)
        atlas_snapshot = None
    else:
        selection = authenticated_features.selection
        feature_receipt = authenticated_features.receipt
        atlas_snapshot = authenticated_features.snapshot
    if Path(selection.path).resolve() != Path(atlas_artifact_path).resolve():
        _invalid("BAMF_PRIORITY_ATLAS_SELECTION_DRIFT")
    current = source_context.release
    if selection.release_sha256 != feature_receipt.source_release_sha256:
        _invalid("BAMF_PRIORITY_ATLAS_RELEASE_DRIFT")
    source = issue_source_context_transition_authority(selection)
    frontier_trust_identity = (
        _candidate_frontier_trust_identity(current.release_sha256)
        if planning_cache is not None else None)
    key = (
        _static_key(
            current, selection, feature_receipt, source,
            frontier_trust_identity)
        if planning_cache is not None else None)
    if (planning_cache is not None
            and frontier_trust_identity[3] is not None
            and frontier_trust_identity[4] is not None
            and planning_cache._static_key == key):
        planning_cache.static_hits += 1
        candidate = planning_cache._candidate_set
        frontier = planning_cache._candidate_frontier
        staged = planning_cache._staged_candidates
        plan = planning_cache._autonomy_plan
        if (candidate is None or frontier is None or staged is None
                or plan is None
                or frontier_trust_identity is None
                or frontier.release_sha256 != frontier_trust_identity[3]):
            _invalid("BAMF_PRIORITY_PLANNING_CACHE_INVALID")
        _emit_progress(progress, "planner: reusing source/release planning products")
    else:
        if planning_cache is not None:
            planning_cache.static_misses += 1
        _emit_progress(progress, "planner: compiling semantic curriculum")
        frontier_state = LearnedFrontier(selection.release_sha256)
        candidate = (_compile_semantic_curriculum_snapshot(
            atlas_snapshot, SOURCE_FAMILY_ADAPTERS, frontier_state)
            if atlas_snapshot is not None else compile_semantic_curriculum(
                selection, SOURCE_FAMILY_ADAPTERS, frontier_state))
        frontier = _candidate_frontier(
            run_dir, current.release_sha256, progress=progress)
        _emit_progress(progress, "planner: staging source-valid candidate realizations")
        staged = _persist_ready_realizations(
            run_dir, current, candidate, frontier, source_context.graph)
        plan = build_live_autonomy_plan(current, source_context.source_root)
        if planning_cache is not None:
            frontier_trust_identity = _candidate_frontier_trust_identity(
                current.release_sha256)
            if (frontier_trust_identity[3] is None
                    or frontier_trust_identity[4] is None
                    or frontier.release_sha256 != frontier_trust_identity[3]):
                _invalid("BAMF_PRIORITY_PLANNING_CACHE_INVALID")
            key = _static_key(
                current, selection, feature_receipt, source,
                frontier_trust_identity)
            planning_cache._static_key = key
            planning_cache._candidate_set = candidate
            planning_cache._candidate_frontier = frontier
            planning_cache._staged_candidates = staged
            planning_cache._autonomy_plan = plan
            planning_cache._snapshot_key = None
            planning_cache._snapshot = None
            planning_cache._closure_key = None
            planning_cache._closure = None
            planning_cache._planning_key = None
            planning_cache._planning = None
    snapshot_key = _snapshot_key(key, feature_receipt) if planning_cache is not None else None
    if planning_cache is not None and planning_cache._snapshot_key == snapshot_key:
        planning_cache.snapshot_hits += 1
        snapshot = planning_cache._snapshot
        if snapshot is None:
            _invalid("BAMF_PRIORITY_PLANNING_CACHE_INVALID")
        _emit_progress(progress, "planner: reusing bounded executable snapshot")
    else:
        if planning_cache is not None:
            planning_cache.snapshot_misses += 1
        _emit_progress(progress, "planner: building bounded executable snapshot")
        snapshot = build_accepted_executable_snapshot(
            candidate, source.frontier, source.policy, frontier, current, staged,
            budget=PlannerBudget(9, 16, 1000),
            admission_receipt_sha256=feature_receipt.acceptance_sha256,
            grade_labels=tuple(
                grade.grade_id for grade in current.execution_plan.grades),
        )
        if planning_cache is not None:
            planning_cache._snapshot_key = snapshot_key
            planning_cache._snapshot = snapshot
            planning_cache._closure_key = None
            planning_cache._closure = None
            planning_cache._planning_key = None
            planning_cache._planning = None
    _emit_progress(progress, "planner: reconciling accepted planning state")
    ledger = reconcile_live_autonomy_state(run_dir, current, plan)
    checkpoint = _accepted_checkpoint(run_dir)
    closure_key = _closure_key(snapshot, current, plan, checkpoint, ledger)
    if planning_cache is not None and planning_cache._closure_key == closure_key:
        planning_cache.closure_hits += 1
        closure = planning_cache._closure
        if closure is None:
            _invalid("BAMF_PRIORITY_PLANNING_CACHE_INVALID")
        _emit_progress(progress, "planner: reusing learner frontier closure")
    else:
        if planning_cache is not None:
            planning_cache.closure_misses += 1
        _emit_progress(progress, "planner: resolving frontier closure")
        closure = resolve_frontier_closure(
            snapshot, candidate.census, current_release=current,
            evidence_ledger=ledger, autonomy_plan=plan,
            checkpoint_sha256=checkpoint.sha256,
            optimizer_step=checkpoint.optimizer_step,
        )
        if planning_cache is not None:
            planning_cache._closure_key = closure_key
            planning_cache._closure = closure
            planning_cache._planning_key = None
            planning_cache._planning = None
    accepted_credit = read_accepted_atlas_obligation_credit(run_dir)
    epoch = AtlasCoverageEpoch(
        snapshot, closure, frontier, current, staged,
        accepted_credit=accepted_credit)
    epoch.verify()
    return PriorityPlanningEpoch(
        current, candidate, snapshot, closure, _accepted_requested_keys(epoch),
        accepted_credit, plan, ledger, checkpoint, source)


def priority_planning_from_epoch(epoch, *, progress=None, planning_cache=None):
    """Project C03 planning from one already-derived accepted A09 epoch."""
    from bilqis_mlx.factory import candidate_realizations
    from bilqis_mlx.factory.atlas_frontier_progress import plan_frontier_progress
    from bilqis_mlx.factory.atlas_frontier_selection import (
        ranked_frontier_target, select_frontier_delta_for_projection,
    )
    from bilqis_mlx.runtime.priority_qualification import (
        _issue_internal_priority_planning,
    )

    if type(epoch) is not PriorityPlanningEpoch:
        _invalid("BAMF_PRIORITY_PLANNING_EPOCH_INVALID")
    if planning_cache is not None and type(planning_cache) is not PriorityPlanningCache:
        _invalid("BAMF_PRIORITY_PLANNING_CACHE_INVALID")
    key = _planning_key(epoch) if planning_cache is not None else None
    if planning_cache is not None and planning_cache._planning_key == key:
        planning_cache.planning_hits += 1
        planning = planning_cache._planning
        if planning is None:
            _invalid("BAMF_PRIORITY_PLANNING_CACHE_INVALID")
        _emit_progress(progress, "planner: reusing ranked bounded target")
        return planning
    if planning_cache is not None:
        planning_cache.planning_misses += 1
    current = epoch.current_release
    candidate = epoch.candidate_set
    snapshot = epoch.snapshot
    closure = epoch.closure
    requested = epoch.requested_keys
    selected = projection = None
    _emit_progress(progress, "planner: ranking next bounded target")
    try:
        semantic_id, rows = ranked_frontier_target(snapshot, closure, requested)
    except BilqisError as error:
        if error.context.get("reason") != "BAMF_PLANNER_NO_BOUNDED_READY_DELTA":
            raise
    else:
        try:
            projection = candidate_realizations.project_authoritative_target(
                semantic_id, current, rows)
        except ValueError:
            _invalid("BAMF_PRIORITY_A09_REALIZATION_MISSING")
        selected = select_frontier_delta_for_projection(
            snapshot, closure, current, projection, requested)
    if selected is None and epoch.accepted_credit is not None:
        from bilqis_mlx.factory.atlas_delta_adapter import (
            plan_frontier_progress_with_accepted_credit,
        )
        planning_progress = plan_frontier_progress_with_accepted_credit(
            snapshot, closure, epoch.accepted_credit)
    else:
        planning_progress = plan_frontier_progress(
            snapshot, closure, selected,
            current_release=current if selected is not None else None,
            selected_projection=projection)
    _emit_progress(progress, "planner: candidate frontier ready")
    planning = _issue_internal_priority_planning(
        planning_progress, closure, selected, projection)
    if planning_cache is not None:
        planning_cache._planning_key = key
        planning_cache._planning = planning
    return planning


def priority_planning(run_dir, source_context, atlas_artifact_path, *, progress=None):
    """Project current A09 state from accepted custody without requiring a C07 lease."""
    epoch = build_priority_planning_epoch(
        Path(run_dir), source_context, atlas_artifact_path, progress)
    return priority_planning_from_epoch(epoch, progress=progress)


__all__ = (
    "PriorityPlanningCache",
    "PriorityPlanningEpoch",
    "build_priority_planning_epoch",
    "priority_planning",
    "priority_planning_from_epoch",
)
