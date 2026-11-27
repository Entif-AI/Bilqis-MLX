"""Ordinary C05 screen over one target's generation-bound protection plan."""
import time

from bilqis_mlx.runtime._factory_retention_support import _cohort
from bilqis_mlx.runtime.capability_retention import EvidenceKind
from bilqis_mlx.runtime.bamf_bundle import (
    authenticate_bamf_execution_feature_context,
)

from .local_evaluation import (
    finalize_target_first_local_candidate,
)
from .local_screen_stages import protected_stage, target_stage
from .local_screen_support import elapsed, foundation_policy
from ..capability_evaluation import _invalid


def foundation_local_retention_screen(
        source_context, parent, candidate_bundle, candidate_state, artifact_path,
        release, plan, target_plan, training, cached_rows, cache, *,
        observer=None, mastery_debt_min_utility=0.05, preflight=None):
    """Resolve a fresh target pair before any protected candidate inference."""
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    if strict_evidence_enabled():
        authenticated = authenticate_bamf_execution_feature_context(
            candidate_bundle, artifact_path, source_context.run_dir)
    else:
        authenticated = getattr(source_context, "_accepted_feature_context", None)
        if authenticated is None:
            _invalid("BAMF_C05_LEARNING_FIRST_FEATURE_CONTEXT_REQUIRED")
    (
        target, protected_rows, target_instruments, target_pair,
        target_coverage, comparison, decision,
    ) = target_stage(
        source_context, parent, candidate_bundle, candidate_state, artifact_path,
        release, plan, target_plan, training, cached_rows, cache, observer,
        authenticated=authenticated,
        mastery_debt_min_utility=mastery_debt_min_utility,
        **({"preflight": preflight} if preflight is not None else {}))
    if decision is not None:
        return decision, parent, candidate_bundle, cache, comparison, None, None

    protected_pair, parent_cache, protected_instruments, coverage = protected_stage(
        source_context, parent, candidate_bundle, artifact_path,
        release, plan, target_plan, training, protected_rows, cache,
        target_coverage, observer, authenticated=authenticated,
        mastery_debt_min_utility=mastery_debt_min_utility)
    groups = target_plan.evaluated_capability_groups

    all_instruments = (*target_instruments, *protected_instruments)
    policy = foundation_policy(
        groups, target_plan.protected_capability_ids,
        tuple(item.case for item in all_instruments), coverage,
        mastery_debt_min_utility)
    cohort = _cohort(
        EvidenceKind.FIXED_SCHOOL, all_instruments, groups, release, policy, training,
        rubric_sha256=plan.rubric_sha256,
        scope_sha256=target_plan.evaluation_scope_sha256,
        source_sha256=plan.source_sha256)
    started = time.perf_counter() if observer is not None else None
    decision = finalize_target_first_local_candidate(
        target, policy, cohort, target_pair, protected_pair,
        retention_protection_plan_sha256=plan.digest,
        evaluated_capability_ids=target_plan.evaluated_capability_ids,
        **({"observer": observer} if observer is not None else {}))
    elapsed(observer, "retention_decision_finalize_wall_seconds", started)
    return (
        decision, parent, candidate_bundle, parent_cache, comparison,
        None, None,
    )


__all__ = ("foundation_local_retention_screen",)
