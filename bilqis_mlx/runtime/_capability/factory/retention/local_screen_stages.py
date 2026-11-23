"""Target and protected stages for local FOUNDATION retention."""
import time

from bilqis_mlx.learning._atlas_candidate.identity_binding import (
    candidate_identity_for_canonical_consumer,
)
from bilqis_mlx.runtime._factory_parent_assessment_cache import (
    factory_parent_assessment_identity,
    use_parent_assessment,
)
from bilqis_mlx.runtime._factory_retention_support import (
    C05_FRESH_TARGET_SEED_OFFSET,
    C05_PROBE_EACH,
    _cohort,
    _fresh_rows,
    _instruments,
    _owner_seed,
)
from bilqis_mlx.runtime.baseline.currentness import baseline_coverage
from bilqis_mlx.runtime.baseline.lifecycle import BaselineLedger
from bilqis_mlx.runtime.capability_retention import (
    AssessmentPair,
    EvidenceKind,
    evaluate_capabilities,
)
from bilqis_mlx.runtime.capability_retention_foundation_runtime import (
    observed_assessment,
)
from bilqis_mlx.runtime.factory_complete_solver import factory_complete_solver

from .local_evaluation import evaluate_target_gate
from .local_screen_support import (
    cached_instruments,
    comparison_epoch,
    coverage_for_groups,
    elapsed,
    foundation_policy,
    local_coverage,
    observe,
    solver_profile,
    split_cached_rows,
)


def target_stage(
        source_context, parent, candidate_bundle, candidate_state, artifact_path,
        release, plan, target_plan, training, cached_rows, cache, observer=None, *,
        authenticated=None, mastery_debt_min_utility=0.05):
    started = time.perf_counter()
    target = target_plan.target_capability_id
    (reference_seed, reference_rows), protected_rows = split_cached_rows(
        cached_rows, target_plan)
    reference_target = tuple(_instruments(
        source_context, candidate_bundle, artifact_path, reference_rows,
        seed=reference_seed, release_prevalidated=True, authenticated=authenticated))
    epoch = comparison_epoch(
        release, plan, target_plan, reference_target, parent, cache)
    ledger = BaselineLedger.from_optional_record(parent.baseline_evidence)
    target_group = ((target, target_plan.target_grade_id),)
    target_coverage = baseline_coverage(ledger, epoch, target_group)
    candidate_sha256 = candidate_identity_for_canonical_consumer(candidate_state)
    fresh_seed = _owner_seed(
        release.release_sha256, cache, target, candidate_sha256)
    target_draw = _fresh_rows(
        source_context, (target,), seed=fresh_seed + C05_FRESH_TARGET_SEED_OFFSET,
        training=training, require_independent=False)
    target_instruments = tuple(_instruments(
        source_context, candidate_bundle, artifact_path, target_draw.rows,
        seed=target_draw.seed, each=C05_PROBE_EACH,
        release_prevalidated=True, authenticated=authenticated))
    target_cases = tuple(item.case for item in target_instruments)
    target_policy = foundation_policy(
        target_group, (), target_cases, target_coverage,
        mastery_debt_min_utility)
    target_cohort = _cohort(
        EvidenceKind.FRESH_TARGET, target_instruments, target_group,
        release, target_policy, training,
        rubric_sha256=plan.rubric_sha256,
        scope_sha256=target_plan.comparison_scope_sha256,
        source_sha256=plan.source_sha256)
    observe(observer, retention_target_case_count=len(target_cases))
    elapsed(observer, "retention_target_prepare_wall_seconds", started)

    started = time.perf_counter()
    parent_solver, parent_generation = factory_complete_solver(
        source_context, parent, artifact_path, target_instruments,
        execution_cache=cache)
    candidate_solver, candidate_generation = factory_complete_solver(
        source_context, candidate_bundle, artifact_path, target_instruments)
    elapsed(observer, "retention_target_solver_wall_seconds", started)

    started = time.perf_counter()
    total_assessments = 2 + (2 if target_plan.protected_capability_ids else 0)
    parent_assessment = observed_assessment(
        parent_solver, target_cohort, parent_generation, observer, 0,
        total_assessments, target, "parent", evaluator=evaluate_capabilities)
    elapsed(observer, "retention_target_parent_wall_seconds", started)
    started = time.perf_counter()
    candidate_assessment = observed_assessment(
        candidate_solver, target_cohort, candidate_generation, observer, 1,
        total_assessments, target, "candidate", evaluator=evaluate_capabilities)
    elapsed(observer, "retention_target_candidate_wall_seconds", started)
    solver_profile(observer, "retention_target", parent_solver, candidate_solver)
    target_pair = AssessmentPair(parent_assessment, candidate_assessment)
    decision = evaluate_target_gate(
        target, target_policy, target_pair,
        retention_protection_plan_sha256=plan.digest)
    comparison = epoch.identity(target)
    return (
        target, protected_rows, target_instruments, target_pair,
        target_coverage, comparison, decision,
    )


def protected_stage(
        source_context, parent, candidate_bundle, artifact_path,
        release, plan, target_plan, training, protected_rows, cache,
        target_coverage, observer=None, *, authenticated=None,
        mastery_debt_min_utility=0.05):
    started = time.perf_counter()
    protected_instruments = cached_instruments(
        source_context, candidate_bundle, artifact_path, protected_rows,
        authenticated=authenticated)
    protected_pair = parent_cache = None
    coverage = local_coverage(target_coverage, target_plan, plan.digest)
    observe(observer, retention_protected_case_count=len(protected_instruments))
    elapsed(observer, "retention_protected_prepare_wall_seconds", started)
    if not protected_instruments:
        return protected_pair, parent_cache, protected_instruments, coverage

    groups = target_plan.evaluated_capability_groups
    protected_groups = tuple(
        pair for pair in groups if pair[0] in target_plan.protected_capability_ids)
    protected_coverage = coverage_for_groups(coverage, protected_groups)
    protected_cases = tuple(item.case for item in protected_instruments)
    protected_policy = foundation_policy(
        protected_groups, target_plan.protected_capability_ids,
        protected_cases, protected_coverage, mastery_debt_min_utility)
    protected_cohort = _cohort(
        EvidenceKind.FIXED_SCHOOL, protected_instruments, protected_groups,
        release, protected_policy, training,
        rubric_sha256=plan.rubric_sha256,
        scope_sha256=target_plan.evaluation_scope_sha256,
        source_sha256=plan.source_sha256)
    started = time.perf_counter()
    protected_parent_solver, protected_parent_generation = factory_complete_solver(
        source_context, parent, artifact_path, protected_instruments,
        execution_cache=cache)
    parent_identity = factory_parent_assessment_identity(
        source_context, parent, cache, protected_cohort,
        protected_parent_solver, protected_parent_generation)
    elapsed(observer, "retention_protected_parent_solver_wall_seconds", started)
    started = time.perf_counter()
    observe(
        observer, retention_completed=2, retention_total=4,
        retention_subject="fixed_school", retention_role="parent")
    protected_parent, parent_cache = use_parent_assessment(
        parent_identity, protected_parent_solver, protected_cohort,
        protected_parent_generation, scope=cache)
    observe(
        observer, retention_completed=3, retention_total=4,
        retention_subject="fixed_school", retention_role="parent",
        retention_stage_timing={
            "subject": "fixed_school", "role": "parent",
            "wall_seconds": max(0.0, time.perf_counter() - started),
        })
    elapsed(observer, "retention_protected_parent_wall_seconds", started)
    observe(observer, retention_parent_cache_reused=parent_cache.reused)

    started = time.perf_counter()
    protected_candidate_solver, protected_candidate_generation = factory_complete_solver(
        source_context, candidate_bundle, artifact_path, protected_instruments)
    elapsed(observer, "retention_protected_candidate_solver_wall_seconds", started)
    started = time.perf_counter()
    protected_candidate = observed_assessment(
        protected_candidate_solver, protected_cohort, protected_candidate_generation,
        observer, 3, 4, "fixed_school", "candidate",
        evaluator=evaluate_capabilities)
    elapsed(observer, "retention_protected_candidate_wall_seconds", started)
    solver_profile(
        observer, "retention_protected",
        protected_parent_solver, protected_candidate_solver)
    protected_pair = AssessmentPair(protected_parent, protected_candidate)
    return protected_pair, parent_cache, protected_instruments, coverage
