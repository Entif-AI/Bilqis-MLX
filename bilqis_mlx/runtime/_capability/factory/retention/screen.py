"""Private Factory-owned C05 screening and baseline issuance."""
from dataclasses import replace

from bilqis_mlx.data_plane import SHA256_HEX_LENGTH
from bilqis_mlx.learning._atlas_candidate.identity_binding import (
    bind_candidate_identity_or_fallback, candidate_identity_binding_for_state,
    candidate_identity_for_canonical_consumer,
)
from bilqis_mlx.runtime.candidate.step_authority import (
    current_learning_first_step_authority_for_parameters,
)
from bilqis_mlx.runtime.capability_retention import (
    DecisionStatus, EvidenceKind, case_census_digest, evaluate_retention_candidate,
)

from bilqis_mlx.runtime.capability_evaluation import _invalid
from bilqis_mlx.runtime.capability_retention_foundation import (
    FoundationRetentionPolicy,
    evaluate_foundation_fixed_school_candidate_with_evidence,
    mastery_debt_utility_margin_units,
)
from bilqis_mlx.runtime._factory_parent_assessment_cache import (
    ParentAssessmentCacheReceipt, factory_parent_assessment_identity,
    use_parent_assessment,
)
from bilqis_mlx.runtime._factory_retention_support import (
    C05_FRESH_LESSON_SEED_OFFSET, C05_FRESH_TARGET_SEED_OFFSET,
    C05_PROBE_EACH, C05_PROTECTED_REFERENCE_LOSS, _cohort,
    _fresh_rows, _instruments, _owner_seed,
)
from bilqis_mlx.runtime._factory_identity_evaluation import _require_factory_evaluation
from bilqis_mlx.runtime.baseline.lifecycle import (
    BaselineComparisonIdentity, BaselineLedger, _issue_factory_baseline_transition,
    apply_factory_baseline_transition,
)
from bilqis_mlx.runtime.baseline.currentness import (
    BaselineComparisonEpoch,
    baseline_coverage,
)
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.runtime.factory_complete_solver import factory_complete_solver
from bilqis_mlx.semantics.domains import contract_digest

from .local_screen import foundation_local_retention_screen
from .policy import policy_and_cohorts
from .protection_plan import BroadCertificationTrigger
from .protection_plan_compiler import policy_epoch_sha256


def _comparison_epoch(
        release, groups, fixed_instruments, parent, cache, evidence_stage):
    fixed_cases = tuple(item.case for item in fixed_instruments)
    rubric = contract_digest(tuple(
        (item.grade_id, item.assessment_blueprint_sha256)
        for item in release.execution_plan.grades))
    scope = contract_digest((
        release.execution_plan.curriculum_sha256,
        release.execution_plan.profile_id,
        groups,
    ))
    return BaselineComparisonEpoch(
        release.release_sha256,
        release.semantic_catalog_sha256,
        rubric,
        scope,
        policy_epoch_sha256(evidence_stage),
        release.execution_plan.projection_digests.source,
        cache.source_authority_registry_sha256,
        contract_digest(parent.correction_frontier),
        contract_digest(parent.evaluation_contract),
        case_census_digest(fixed_cases),
        evidence_stage.value,
    )


def broad_foundation_retention_screen(
    source_context, parent, candidate_bundle, artifact_path, target_capability,
    release, groups, training, fixed_instruments, cache, evidence_stage, *,
    broad_certification_trigger, observer=None, mastery_debt_min_utility=0.05,
):
    if not isinstance(broad_certification_trigger, BroadCertificationTrigger):
        _invalid("BAMF_C05_BROAD_CERTIFICATION_TRIGGER_REQUIRED")
    fixed_cases = tuple(item.case for item in fixed_instruments)
    ledger = BaselineLedger.from_optional_record(parent.baseline_evidence)
    epoch = _comparison_epoch(
        release, groups, fixed_instruments, parent, cache, evidence_stage)
    coverage = baseline_coverage(ledger, epoch, groups)
    protected = coverage.protected_capabilities(target_capability)
    admitted = {capability for capability, _ in groups}
    if not set(protected) <= admitted - {target_capability}:
        _invalid("BAMF_C05_EARNED_PROTECTION_NOT_ADMITTED")
    policy = FoundationRetentionPolicy(
        groups, tuple(dict.fromkeys(group for _, group in groups)),
        tuple((capability, C05_PROTECTED_REFERENCE_LOSS) for capability in protected),
        C05_PROBE_EACH, case_census_digest(fixed_cases), coverage,
        mastery_debt_min_utility_units=mastery_debt_utility_margin_units(
            mastery_debt_min_utility))
    fixed_cohort = _cohort(
        EvidenceKind.FIXED_SCHOOL, fixed_instruments, groups, release, policy, training,
        evidence_stage=evidence_stage)
    parent_solver, parent_generation = factory_complete_solver(
        source_context, parent, artifact_path, fixed_instruments)
    parent_identity = factory_parent_assessment_identity(
        source_context, parent, cache, fixed_cohort, parent_solver, parent_generation)
    parent_assessment, parent_assessment_cache = use_parent_assessment(
        parent_identity, parent_solver, fixed_cohort, parent_generation, scope=cache)
    comparison = epoch.identity(target_capability)
    candidate_solver, candidate_generation = factory_complete_solver(
        source_context, candidate_bundle, artifact_path, fixed_instruments)
    decision, championship_assessment = (
        evaluate_foundation_fixed_school_candidate_with_evidence(
        parent_solver, candidate_solver, target_capability, policy, fixed_cohort,
        parent_generation, candidate_generation, parent_assessment=parent_assessment,
        **({"observer": observer} if observer is not None else {})))
    decision = replace(
        decision,
        evaluated_capability_ids=tuple(capability for capability, _group in groups),
        broad_certification_trigger=broad_certification_trigger.value,
    )
    return (
        decision, parent, candidate_bundle, parent_assessment_cache, comparison,
        fixed_cohort if championship_assessment is not None else None,
        championship_assessment,
    )


def adaptive_retention_screen(
    source_context, parent, candidate_bundle, candidate_state, artifact_path,
    target_capability, target_group, lesson_capabilities, release, groups, training,
    fixed_instruments, cache, evidence_stage, *, protected_capabilities=None,
    retention_protection_plan_sha256=None, observer=None, plasticity_escape=None,
):
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_mode_enabled,
    )
    candidate_sha256 = (
        candidate_identity_for_canonical_consumer(candidate_state)
        if strict_mode_enabled() else contract_digest((
            "bilqis.bamf.learning-first-retention-seed/v1",
            candidate_bundle.run_id,
            candidate_bundle.generation,
            candidate_state.optimizer_step,
            candidate_bundle.topology.digest,
            candidate_bundle.extents.digest,
        )))
    fresh_seed = _owner_seed(release.release_sha256, cache, target_capability, candidate_sha256)
    target_draw = _fresh_rows(
        source_context, (target_capability,), seed=fresh_seed + C05_FRESH_TARGET_SEED_OFFSET,
        training=training)
    lesson_draw = _fresh_rows(
        source_context, lesson_capabilities, seed=fresh_seed + C05_FRESH_LESSON_SEED_OFFSET,
        training=training)
    target_instruments = _instruments(
        source_context, candidate_bundle, artifact_path, target_draw.rows,
        seed=target_draw.seed, each=C05_PROBE_EACH)
    lesson_instruments = _instruments(
        source_context, candidate_bundle, artifact_path, lesson_draw.rows,
        seed=lesson_draw.seed, each=C05_PROBE_EACH)
    ledger = BaselineLedger.from_optional_record(parent.baseline_evidence)
    epoch = _comparison_epoch(
        release, groups, fixed_instruments, parent, cache, evidence_stage)
    coverage = baseline_coverage(ledger, epoch, groups)
    protected = (
        coverage.protected_capabilities(target_capability)
        if protected_capabilities is None else tuple(protected_capabilities))
    policy, cohorts = policy_and_cohorts(
        release, groups, target_capability, target_group, training, target_instruments,
        lesson_instruments, fixed_instruments, coverage, protected,
        evidence_stage=evidence_stage)
    all_instruments = tuple(dict(
        (item.case.case_id, item)
        for item in (*target_instruments, *lesson_instruments, *fixed_instruments)).values())
    parent_solver, parent_generation = factory_complete_solver(
        source_context, parent, artifact_path, all_instruments)
    candidate_solver, candidate_generation = factory_complete_solver(
        source_context, candidate_bundle, artifact_path, all_instruments)
    decision = evaluate_retention_candidate(
        parent_solver, candidate_solver, target_capability, policy, cohorts,
        parent_generation, candidate_generation,
        plasticity_escape=plasticity_escape,
        **({"observer": observer} if observer is not None else {}))
    if retention_protection_plan_sha256 is not None:
        decision = replace(
            decision,
            evaluated_capability_ids=tuple(capability for capability, _group in groups),
            retention_protection_plan_sha256=retention_protection_plan_sha256,
        )
    return (
        decision, parent, candidate_bundle, cache, epoch.identity(target_capability),
        None, None,
    )


def _issue_factory_evaluation(
        raw_issue, result, *, parent_identity_sha256=None):
    from bilqis_mlx.runtime.bamf_bundle.genesis.records import (
        successor_candidate_identity_digest,
    )
    from bilqis_mlx.runtime.bamf_bundle.motif.transition import (
        is_motif_allocation_transition,
    )
    (decision, parent, candidate, cache, comparison,
     championship_cohort, championship_assessment, *observations) = result
    observation = observations[0] if observations else None
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_mode_enabled,
    )
    strict = strict_mode_enabled()
    accepted = decision.status is DecisionStatus.ELIGIBLE
    generation_authority = (
        successor_candidate_identity_digest(candidate)
        if (strict or accepted)
        and is_motif_allocation_transition(getattr(candidate, "transition", {}))
        else None)
    if strict:
        parent_identity = candidate_identity_for_canonical_consumer(parent.retained_state)
    else:
        cached_parent_identity = getattr(cache, "_candidate_identity_sha256", None)
        if (isinstance(parent_identity_sha256, str)
                and isinstance(cached_parent_identity, str)
                and parent_identity_sha256 != cached_parent_identity):
            _invalid("BAMF_C05_PARENT_IDENTITY_DRIFT")
        parent_identity = (
            parent_identity_sha256
            if isinstance(parent_identity_sha256, str)
            else cached_parent_identity)
    if (not isinstance(parent_identity, str)
            or len(parent_identity) != SHA256_HEX_LENGTH):
        _invalid("BAMF_C05_PARENT_IDENTITY_REQUIRED")
    if strict:
        candidate_identity = candidate_identity_for_canonical_consumer(
            candidate.retained_state)
        parent_binding = candidate_identity_binding_for_state(parent.retained_state)
        candidate_binding = candidate_identity_binding_for_state(candidate.retained_state)
    elif accepted:
        candidate_identity = bind_candidate_identity_or_fallback(
            candidate.retained_state, candidate.topology.digest, candidate.extents.digest)
        parent_binding = None
        candidate_binding = candidate_identity_binding_for_state(candidate.retained_state)
    else:
        parameters = candidate.retained_state.optimizer.parameters
        candidate_identity = current_learning_first_step_authority_for_parameters(
            parameters)
        if candidate_identity is None:
            _invalid("BAMF_C05_LEARNING_FIRST_STEP_AUTHORITY_REQUIRED")
        parent_binding = None
        candidate_binding = None
    baseline = BaselineLedger.from_optional_record(parent.baseline_evidence)
    baseline_transition = None
    if accepted and comparison is not None:
        baseline_transition = _issue_factory_baseline_transition(
            comparison, run_id=parent.run_id, accepted_generation=parent.generation + 1,
            accepted_parent_manifest_sha256=candidate.parent_manifest_sha256,
            accepted_candidate_sha256=candidate_identity,
            decision_evidence_sha256=decision.evidence_sha256,
            parent_ledger_sha256=baseline.digest)
        baseline = apply_factory_baseline_transition(baseline, baseline_transition)
    parent_assessment_cache = (
        cache if type(cache) is ParentAssessmentCacheReceipt else None)
    return raw_issue(
        decision, parent_identity, candidate_identity,
        generation_authority, parent_assessment_cache, parent_state=parent.retained_state,
        candidate_state=candidate.retained_state,
        parent_binding=parent_binding, candidate_binding=candidate_binding,
        baseline_transition=baseline_transition, baseline_ledger=baseline,
        championship_cohort=championship_cohort,
        championship_assessment=championship_assessment,
        target_weakness_observation=observation)


def bind_factory_evaluation_issuer(raw_issue, evidence_stage):
    """Bind issuance to Factory-owned screens without exporting a mint."""
    def issue(result, *, parent_identity_sha256=None):
        return _issue_factory_evaluation(
            raw_issue, result, parent_identity_sha256=parent_identity_sha256)

    def foundation(*args, parent_identity_sha256=None, **kwargs):
        return issue(
            foundation_local_retention_screen(*args, **kwargs),
            parent_identity_sha256=parent_identity_sha256)

    def adaptive(*args, parent_identity_sha256=None, **kwargs):
        return issue(
            adaptive_retention_screen(
                *args, evidence_stage=evidence_stage, **kwargs),
            parent_identity_sha256=parent_identity_sha256)

    def broad_foundation(*args, parent_identity_sha256=None, **kwargs):
        return issue(
            broad_foundation_retention_screen(
                *args, evidence_stage=evidence_stage, **kwargs),
            parent_identity_sha256=parent_identity_sha256)

    return foundation, adaptive, broad_foundation


def bind_factory_baseline_successor(evaluation, candidate):
    """Attach only the C05-owned prospective baseline result to its exact successor."""
    from dataclasses import replace
    from bilqis_mlx.runtime.bamf_bundle.records import BamfBundleCandidate

    _require_factory_evaluation(evaluation)
    evaluation.__post_init__()
    if type(candidate) is not BamfBundleCandidate:
        _invalid("BAMF_C05_BASELINE_SUCCESSOR_INVALID")
    transition = evaluation.baseline_transition
    if transition is not None:
        measurement = transition.measurement
        if (candidate.run_id != measurement.run_id
                or candidate.generation != measurement.accepted_generation
                or candidate.parent_manifest_sha256 != measurement.accepted_parent_manifest_sha256
                or candidate_identity_for_canonical_consumer(candidate.retained_state)
                != measurement.accepted_candidate_sha256):
            _invalid("BAMF_C05_BASELINE_SUCCESSOR_INVALID")
    return replace(candidate, baseline_evidence=evaluation.baseline_ledger.to_record())
