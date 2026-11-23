"""#1329 target-first C05 evidence resolves before broader protection work."""
from dataclasses import replace
from types import SimpleNamespace as N
from unittest.mock import ANY, Mock, patch

import bilqis_mlx.runtime.retention.local_screen as local_screen
import bilqis_mlx.runtime.retention.local_screen_stages as local_stages
import bilqis_mlx.runtime.retention.local_screen_support as local_support
from bilqis_mlx.runtime.capability_retention import (
    AssessmentPair,
    EvidenceStage,
    case_census_digest,
    evaluate_capabilities,
)
from bilqis_mlx.runtime.capability_retention_foundation import FoundationRetentionPolicy
from bilqis_mlx.runtime.baseline.currentness import BaselineCoverage
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.retention.local_evaluation import (
    evaluate_target_gate,
    finalize_target_first_local_candidate,
)
from bilqis_mlx.runtime.tests.capability.capability_retention_helpers import (
    CANDIDATE,
    PARENT,
    _screen_inputs,
)


def _target_pair(*, measured: bool, gain: bool, group: str = "Z"):
    parent_solver, candidate_solver, target, base_policy, cohorts = _screen_inputs(
        protected_loss=0, labels=(group, "other"))
    source = cohorts[0]
    coverage = BaselineCoverage(
        (target,) if measured else (),
        () if measured else (target,),
        ((group, int(measured), 1),),
        int(measured), 1, "e" * 64)
    policy = FoundationRetentionPolicy(
        ((target, group),), (group,), (), base_policy.probe_each,
        source.expected_case_digest, coverage)
    cohort = replace(
        source,
        capability_groups=((target, group),),
        evidence_stage=EvidenceStage.FOUNDATION_ACQUISITION,
        policy_sha256=policy.digest(),
    )
    candidate = candidate_solver if gain else parent_solver
    return target, policy, AssessmentPair(
        evaluate_capabilities(parent_solver, cohort, PARENT),
        evaluate_capabilities(candidate, cohort, CANDIDATE))


def test_comparable_zero_delta_target_rejects_before_broader_scope():
    target, policy, pair = _target_pair(measured=True, gain=False)

    decision = evaluate_target_gate(
        target, policy, pair,
        retention_protection_plan_sha256="1" * 64)

    assert decision is not None
    assert decision.reason == "NO_MEASURABLE_TARGET_GAIN"
    assert decision.evaluated_capability_ids == (target,)
    assert decision.outcome_scores == ((target, 0, 0, 3),)


def test_unmeasured_zero_delta_target_continues_and_grade_identity_is_opaque():
    target, policy, pair = _target_pair(measured=False, gain=False, group="future-grade-z")

    decision = evaluate_target_gate(
        target, policy, pair,
        retention_protection_plan_sha256="2" * 64)

    assert decision is None


def test_unmeasured_target_still_rejects_fresh_paired_regression():
    target, policy, improving = _target_pair(measured=False, gain=True)
    regressing = AssessmentPair(improving.candidate, improving.parent)

    decision = evaluate_target_gate(
        target, policy, regressing,
        retention_protection_plan_sha256="9" * 64)

    assert decision is not None
    assert decision.reason == "TARGET_BASELINE_REGRESSION"
    assert decision.blocking_capability == target
    before, after, total = decision.outcome_scores[0][1:]
    assert after < before
    assert total > 0


def test_comparable_positive_target_continues():
    target, policy, pair = _target_pair(measured=True, gain=True)

    decision = evaluate_target_gate(
        target, policy, pair,
        retention_protection_plan_sha256="3" * 64)

    assert decision is None


def test_local_coverage_combines_exact_target_state_with_compiled_protection():
    target_plan = N(
        target_capability_id="future.target",
        protected_capability_ids=("established.prerequisite",),
        evaluated_capability_groups=(
            ("future.target", "future-grade-z"),
            ("established.prerequisite", "prior-grade"),
        ),
    )
    target_coverage = BaselineCoverage(
        (), ("future.target",), (("future-grade-z", 0, 1),),
        0, 1, "a" * 64)

    coverage = local_support.local_coverage(
        target_coverage, target_plan, "b" * 64)

    assert coverage.measured_capabilities == ("established.prerequisite",)
    assert coverage.unmeasured_capabilities == ("future.target",)
    assert coverage.group_denominators == (
        ("future-grade-z", 0, 1), ("prior-grade", 1, 1))


def test_unmeasured_target_still_allows_established_protected_veto():
    parent_solver, candidate_solver, target, base_policy, cohorts = _screen_inputs(
        protected_loss=12, labels=("future-grade-z", "prior-grade"))
    protected = "protected"
    target_cases = cohorts[0].cases
    protected_cases = tuple(
        case for case in cohorts[2].cases if case.capability_id == protected)
    groups = ((target, "future-grade-z"), (protected, "future-grade-z"))
    coverage = BaselineCoverage(
        (protected,), (target,), (("future-grade-z", 1, 2),),
        1, 2, "e" * 64)
    final_policy = FoundationRetentionPolicy(
        groups, ("future-grade-z",), ((protected, 1),),
        base_policy.probe_each, case_census_digest(target_cases + protected_cases),
        coverage)
    fixed = replace(
        cohorts[2],
        cases=target_cases + protected_cases,
        capability_groups=groups,
        expected_case_digest=case_census_digest(target_cases + protected_cases),
        evidence_stage=EvidenceStage.FOUNDATION_ACQUISITION,
        policy_sha256=final_policy.digest(),
    )
    target_pair = AssessmentPair(
        evaluate_capabilities(parent_solver, cohorts[0], PARENT),
        evaluate_capabilities(parent_solver, cohorts[0], CANDIDATE))
    protected_cohort = replace(
        fixed,
        cases=protected_cases,
        capability_groups=((protected, "future-grade-z"),),
        expected_case_digest=case_census_digest(protected_cases),
    )
    protected_pair = AssessmentPair(
        evaluate_capabilities(parent_solver, protected_cohort, PARENT),
        evaluate_capabilities(candidate_solver, protected_cohort, CANDIDATE))

    decision = finalize_target_first_local_candidate(
        target, final_policy, fixed, target_pair, protected_pair,
        retention_protection_plan_sha256="4" * 64,
        evaluated_capability_ids=(target, protected))

    assert decision.reason == "PROTECTED_CAPABILITY_REGRESSION"
    assert decision.blocking_capability == protected
    assert decision.outcome_scores[0] == (target, 0, 0, 3)
