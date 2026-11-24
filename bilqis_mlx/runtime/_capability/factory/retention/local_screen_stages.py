"""Target and protected stages for local FOUNDATION retention."""
import time

from bilqis_mlx.learning._atlas_candidate.identity_binding import (
    candidate_identity_for_canonical_consumer,
)
from bilqis_mlx.runtime._factory_parent_assessment_cache import (
    factory_parent_assessment_identity,
    lookup_parent_assessment,
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
from bilqis_mlx.runtime.factory_complete_solver import (
    factory_complete_solver,
    factory_evaluation_case_from_source,
)
from bilqis_mlx.semantics.domains import contract_digest

from .local_evaluation import evaluate_target_gate
from .local_screen_support import (
    cached_instruments,
    comparison_epoch,
    elapsed,
    foundation_policy,
    local_coverage,
    observe,
    solver_profile,
    split_cached_rows,
)


def _candidate_seed_identity(candidate_state, candidate_bundle) -> str:
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_mode_enabled,
    )
    if strict_mode_enabled():
        return candidate_identity_for_canonical_consumer(candidate_state)
    return contract_digest((
        "bilqis.bamf.learning-first-retention-seed/v1",
        candidate_bundle.run_id,
        candidate_bundle.generation,
        candidate_state.optimizer_step,
        candidate_bundle.topology.digest,
        candidate_bundle.extents.digest,
    ))


def target_stage(
        source_context, parent, candidate_bundle, candidate_state, artifact_path,
        release, plan, target_plan, training, cached_rows, cache, observer=None, *,
        authenticated=None, mastery_debt_min_utility=0.05):
    started = time.perf_counter() if observer is not None else None
    target = target_plan.target_capability_id
    (reference_seed, reference_rows), protected_rows = split_cached_rows(
        cached_rows, target_plan)
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    if strict_evidence_enabled():
        reference_cases = tuple(item.case for item in _instruments(
            source_context, candidate_bundle, artifact_path, reference_rows,
            seed=reference_seed, release_prevalidated=True,
            authenticated=authenticated))
    else:
        reference_cases = tuple(
            factory_evaluation_case_from_source(
                source_context, row,
                semantic_release=authenticated.features.semantic_release)
            for row in reference_rows)
    epoch = comparison_epoch(
        release, plan, target_plan, reference_cases, parent, cache)
    ledger = BaselineLedger.from_optional_record(parent.baseline_evidence)
    target_group = ((target, target_plan.target_grade_id),)
    target_coverage = baseline_coverage(ledger, epoch, target_group)
    candidate_seed_identity = _candidate_seed_identity(candidate_state, candidate_bundle)
    fresh_seed = _owner_seed(
        release.release_sha256, cache, target, candidate_seed_identity)
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

    started = time.perf_counter() if observer is not None else None
    parent_solver, parent_generation = factory_complete_solver(
        source_context, parent, artifact_path, target_instruments,
        execution_cache=cache)
    candidate_solver, candidate_generation = factory_complete_solver(
        source_context, candidate_bundle, artifact_path, target_instruments,
        authenticated=authenticated)
    elapsed(observer, "retention_target_solver_wall_seconds", started)

    started = time.perf_counter() if observer is not None else None
    total_assessments = 4
    parent_assessment = observed_assessment(
        parent_solver, target_cohort, parent_generation, observer, 0,
        total_assessments, target, "parent", evaluator=evaluate_capabilities)
    elapsed(observer, "retention_target_parent_wall_seconds", started)
    started = time.perf_counter() if observer is not None else None
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


def reference_stage(
        source_context, parent, candidate_bundle, artifact_path,
        release, plan, target_plan, training, reference_rows, cache,
        target_coverage, observer=None, *, authenticated=None,
        mastery_debt_min_utility=0.05):
    started = time.perf_counter() if observer is not None else None
    reference_instruments = cached_instruments(
        source_context, candidate_bundle, artifact_path, reference_rows,
        authenticated=authenticated)
    coverage = local_coverage(target_coverage, target_plan, plan.digest)
    observe(observer,
            retention_reference_case_count=len(reference_instruments),
            retention_protected_case_count=sum(
                item.case.capability_id in target_plan.protected_capability_ids
                for item in reference_instruments))
    elapsed(observer, "retention_protected_prepare_wall_seconds", started)
    groups = target_plan.evaluated_capability_groups
    reference_cases = tuple(item.case for item in reference_instruments)
    reference_policy = foundation_policy(
        groups, target_plan.protected_capability_ids,
        reference_cases, coverage, mastery_debt_min_utility)
    reference_cohort = _cohort(
        EvidenceKind.FIXED_SCHOOL, reference_instruments, groups,
        release, reference_policy, training,
        rubric_sha256=plan.rubric_sha256,
        scope_sha256=target_plan.evaluation_scope_sha256,
        source_sha256=plan.source_sha256)
    started = time.perf_counter() if observer is not None else None
    reference_parent_solver = None
    reference_parent_generation = cache.generation_binding
    parent_identity = factory_parent_assessment_identity(
        source_context, parent, cache, reference_cohort,
        None, reference_parent_generation)
    cached_parent = lookup_parent_assessment(
        parent_identity, reference_cohort, reference_parent_generation, scope=cache)
    if cached_parent is None:
        reference_parent_solver, reference_parent_generation = factory_complete_solver(
            source_context, parent, artifact_path, reference_instruments,
            execution_cache=cache)
    elapsed(observer, "retention_protected_parent_solver_wall_seconds", started)
    started = time.perf_counter() if observer is not None else None
    observe(
        observer, retention_completed=2, retention_total=4,
        retention_subject="fixed_school", retention_role="parent")
    if cached_parent is None:
        reference_parent, parent_cache = use_parent_assessment(
            parent_identity, reference_parent_solver, reference_cohort,
            reference_parent_generation, scope=cache)
    else:
        reference_parent, parent_cache = cached_parent
    observe(
        observer, retention_completed=3, retention_total=4,
        retention_subject="fixed_school", retention_role="parent",
        retention_stage_timing={
            "subject": "fixed_school", "role": "parent",
            "wall_seconds": (
                0.0 if started is None else max(0.0, time.perf_counter() - started)),
        })
    elapsed(observer, "retention_protected_parent_wall_seconds", started)
    observe(observer, retention_parent_cache_reused=parent_cache.reused)

    started = time.perf_counter() if observer is not None else None
    reference_candidate_solver, reference_candidate_generation = factory_complete_solver(
        source_context, candidate_bundle, artifact_path, reference_instruments,
        authenticated=authenticated)
    elapsed(observer, "retention_protected_candidate_solver_wall_seconds", started)
    started = time.perf_counter() if observer is not None else None
    reference_candidate = observed_assessment(
        reference_candidate_solver, reference_cohort, reference_candidate_generation,
        observer, 3, 4, "fixed_school", "candidate",
        evaluator=evaluate_capabilities)
    elapsed(observer, "retention_protected_candidate_wall_seconds", started)
    solver_profile(
        observer, "retention_protected",
        reference_parent_solver, reference_candidate_solver)
    reference_pair = AssessmentPair(reference_parent, reference_candidate)
    return reference_pair, parent_cache, reference_policy
