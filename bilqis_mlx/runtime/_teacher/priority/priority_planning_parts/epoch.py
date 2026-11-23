"""Accepted A09 epoch derivation for incremental priority planning."""
from pathlib import Path

from bilqis_mlx.runtime.priority_planning_parts.cache import (
    PriorityPlanningEpoch,
    _closure_key,
    _emit_progress,
    _invalid,
    _require_cache,
    _snapshot_key,
    _static_key,
)


def _semantic_candidate(
        run_dir, selection, atlas_snapshot, adapters, progress, *,
        persist_memo=True):
    from bilqis_mlx.factory.skos_curriculum import (
        LearnedFrontier, _compile_semantic_curriculum_snapshot,
        compile_semantic_curriculum,
    )
    from bilqis_mlx.runtime.priority_planning_parts.candidate_memo import (
        load_candidate_memo, persist_candidate_memo,
    )

    candidate = load_candidate_memo(run_dir, selection, adapters)
    if candidate is not None:
        _emit_progress(progress, "planner: reusing durable semantic curriculum")
        return candidate
    _emit_progress(progress, "planner: compiling semantic curriculum")
    frontier_state = LearnedFrontier(selection.release_sha256)
    candidate = (_compile_semantic_curriculum_snapshot(
        atlas_snapshot, adapters, frontier_state)
        if atlas_snapshot is not None else compile_semantic_curriculum(
            selection, adapters, frontier_state))
    if persist_memo:
        persist_candidate_memo(run_dir, selection, adapters, candidate)
    return candidate


def _static_planning_products(
        run_dir, source_context, current, selection, feature_receipt, source,
        atlas_snapshot, planning_cache, progress, *, learning_first=False):
    from bilqis_mlx.factory.skos_curriculum import SOURCE_FAMILY_ADAPTERS
    from bilqis_mlx.runtime.atlas_flywheel_runtime import (
        _candidate_frontier_from_trust_identity,
        _candidate_frontier_trust_identity,
        _persist_ready_realizations,
    )
    from bilqis_mlx.runtime._autonomy_live.planning import (
        build_live_autonomy_plan,
        build_live_autonomy_plan_prevalidated,
    )

    frontier_trust_identity = _candidate_frontier_trust_identity(
        current.release_sha256)
    key = (
        _static_key(
            current, selection, feature_receipt, source,
            frontier_trust_identity)
        if planning_cache is not None else None)
    cache_hit = (
        planning_cache is not None
        and frontier_trust_identity.frontier_release_sha256 is not None
        and frontier_trust_identity.receipt_sha256 is not None
        and planning_cache._static_key == key)
    if cache_hit:
        planning_cache.static_hits += 1
        candidate = planning_cache._candidate_set
        frontier = planning_cache._candidate_frontier
        staged = planning_cache._staged_candidates
        plan = planning_cache._autonomy_plan
        if (candidate is None or frontier is None or staged is None
                or plan is None
                or frontier.release_sha256
                != frontier_trust_identity.frontier_release_sha256):
            _invalid("BAMF_PRIORITY_PLANNING_CACHE_INVALID")
        _emit_progress(
            progress, "planner: reusing source/release planning products")
        return key, candidate, frontier, staged, plan

    if planning_cache is not None:
        planning_cache.static_misses += 1
    from contextlib import nullcontext
    if learning_first and atlas_snapshot is not None:
        from bilqis_mlx.semantics.atlas.snapshot import reuse_pinned_atlas_snapshot
        atlas_scope = reuse_pinned_atlas_snapshot(selection, atlas_snapshot)
    else:
        atlas_scope = nullcontext()
    with atlas_scope:
        candidate = _semantic_candidate(
            run_dir, selection, atlas_snapshot, SOURCE_FAMILY_ADAPTERS, progress,
            persist_memo=not learning_first)
        frontier, frontier_trust_identity = _candidate_frontier_from_trust_identity(
            run_dir, current.release_sha256, frontier_trust_identity, progress=progress)
        _emit_progress(
            progress, "planner: staging source-valid candidate realizations")
        staged = _persist_ready_realizations(
            run_dir, current, candidate, frontier, source_context.graph)
        plan_builder = (
            build_live_autonomy_plan_prevalidated if learning_first
            else build_live_autonomy_plan)
        plan = plan_builder(current, source_context.source_root)
    if planning_cache is None:
        return key, candidate, frontier, staged, plan

    if (frontier_trust_identity.frontier_release_sha256 is None
            or frontier_trust_identity.receipt_sha256 is None
            or frontier.release_sha256
            != frontier_trust_identity.frontier_release_sha256):
        _invalid("BAMF_PRIORITY_PLANNING_CACHE_INVALID")
    key = _static_key(
        current, selection, feature_receipt, source, frontier_trust_identity)
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
    return key, candidate, frontier, staged, plan


def _planning_snapshot(
        candidate, source, frontier, current, staged, feature_receipt, key,
        planning_cache, progress, *, learning_first=False):
    from bilqis_mlx.factory.atlas_frontier import PlannerBudget
    from bilqis_mlx.factory.atlas_runtime_snapshot import (
        build_accepted_executable_snapshot,
        build_accepted_executable_snapshot_prevalidated,
    )

    snapshot_key = (
        _snapshot_key(key, feature_receipt)
        if planning_cache is not None else None)
    if planning_cache is not None and planning_cache._snapshot_key == snapshot_key:
        planning_cache.snapshot_hits += 1
        snapshot = planning_cache._snapshot
        if snapshot is None:
            _invalid("BAMF_PRIORITY_PLANNING_CACHE_INVALID")
        _emit_progress(progress, "planner: reusing bounded executable snapshot")
        return snapshot

    if planning_cache is not None:
        planning_cache.snapshot_misses += 1
    _emit_progress(progress, "planner: building bounded executable snapshot")
    builder = (
        build_accepted_executable_snapshot_prevalidated
        if learning_first else build_accepted_executable_snapshot)
    snapshot = builder(
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
    return snapshot


def _planning_closure(
        snapshot, candidate, current, plan, checkpoint, ledger,
        planning_cache, progress, *, learning_first=False):
    from bilqis_mlx.factory.atlas_frontier_closure import (
        resolve_frontier_closure,
        resolve_frontier_closure_prevalidated,
    )

    closure_key = _closure_key(
        snapshot, current, plan, checkpoint, ledger,
        learning_first=learning_first)
    if planning_cache is not None and planning_cache._closure_key == closure_key:
        planning_cache.closure_hits += 1
        closure = planning_cache._closure
        if closure is None:
            _invalid("BAMF_PRIORITY_PLANNING_CACHE_INVALID")
        _emit_progress(progress, "planner: reusing learner frontier closure")
        return closure

    if planning_cache is not None:
        planning_cache.closure_misses += 1
    _emit_progress(progress, "planner: resolving frontier closure")
    resolver = (
        resolve_frontier_closure_prevalidated
        if learning_first else resolve_frontier_closure)
    closure = resolver(
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
    return closure


def build_priority_planning_epoch(
        run_dir, source_context, atlas_artifact_path, progress=None, *,
        authenticated_features=None, planning_cache=None,
        planning_generation=None):
    """Derive the exact accepted A09 epoch once for planning/frontier consumers."""
    from bilqis_mlx.factory.atlas_delta_adapter import (
        AtlasCoverageEpoch, _accepted_requested_keys,
    )
    from bilqis_mlx.factory.skos_curriculum import (
        issue_source_context_transition_authority,
    )
    from bilqis_mlx.runtime.atlas_admission import (
        read_accepted_atlas_obligation_credit,
    )
    from bilqis_mlx.runtime.atlas_flywheel_runtime import (
        _accepted_checkpoint,
        _accepted_selection,
    )
    from bilqis_mlx.runtime._autonomy_live.planning import (
        reconcile_live_autonomy_state,
    )

    planning_cache = _require_cache(planning_cache, run_dir)
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_mode_enabled,
    )
    learning_first = not strict_mode_enabled()
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
    key, candidate, frontier, staged, plan = _static_planning_products(
        run_dir, source_context, current, selection, feature_receipt, source,
        atlas_snapshot, planning_cache, progress, learning_first=learning_first)
    snapshot = _planning_snapshot(
        candidate, source, frontier, current, staged, feature_receipt, key,
        planning_cache, progress, learning_first=learning_first)
    _emit_progress(progress, "planner: reconciling accepted planning state")
    ledger = reconcile_live_autonomy_state(run_dir, current, plan)
    if learning_first and planning_generation is not None:
        from bilqis_mlx.learning.champions import Checkpoint
        checkpoint = Checkpoint(
            planning_generation.parent_candidate_identity_sha256,
            f"bamf-bundles/{planning_generation.accepted_manifest_sha256}",
            planning_generation._parent.retained_state.optimizer_step,
            True,
        )
    else:
        checkpoint = _accepted_checkpoint(run_dir)
    closure = _planning_closure(
        snapshot, candidate, current, plan, checkpoint, ledger,
        planning_cache, progress, learning_first=learning_first)
    accepted_credit = read_accepted_atlas_obligation_credit(run_dir)
    epoch = AtlasCoverageEpoch(
        snapshot, closure, frontier, current, staged,
        accepted_credit=accepted_credit)
    if not learning_first:
        epoch.verify()
    return PriorityPlanningEpoch(
        current, candidate, snapshot, closure, _accepted_requested_keys(epoch),
        accepted_credit, plan, ledger, checkpoint, source)
