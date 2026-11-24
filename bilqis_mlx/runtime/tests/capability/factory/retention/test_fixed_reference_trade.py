"""Fresh gains cannot pay for damage on a different preservation cohort."""
from dataclasses import replace

import pytest

from bilqis_mlx.runtime.baseline.currentness import BaselineCoverage
from bilqis_mlx.runtime.capability_retention import (
    AssessmentPair, EvidenceKind, case_census_digest, evaluate_capabilities,
)
from bilqis_mlx.runtime.capability_retention_foundation import FoundationRetentionPolicy
from bilqis_mlx.runtime.retention.local_evaluation import finalize_target_first_local_candidate
from bilqis_mlx.runtime.tests.capability.capability_retention_helpers import (
    CANDIDATE, PARENT, _cases, _solver,
)
from .test_target_first_retention import _target_pair


@pytest.mark.parametrize("reference_before,reference_after,reason", [
    (2, 2, "PROTECTED_CAPABILITY_REGRESSION"),
    (3, 2, "PROTECTED_CAPABILITY_REGRESSION"),
    (0, 2, "PAIRED_SCREEN_WITHIN_BUDGET"),
])
def test_fixed_reference_trade_requires_real_reference_gain(
        reference_before, reference_after, reason):
    target, _, fresh_pair = _target_pair(measured=True, gain=True, group="grade")
    reference, a = _cases(target, "grade", 3, "stable-target")
    protected, b = _cases("protected", "grade", 6, "stable-peer")
    cases = reference + protected
    groups = ((target, "grade"), ("protected", "grade"))
    coverage = BaselineCoverage(
        (target, "protected"), (), (("grade", 2, 2),), 2, 2, "e" * 64)
    policy = FoundationRetentionPolicy(
        groups, ("grade",), (("protected", 1),), 6,
        case_census_digest(cases), coverage)
    fixed = replace(
        fresh_pair.parent.cohort, kind=EvidenceKind.FIXED_SCHOOL,
        cases=cases, capability_groups=groups,
        expected_case_digest=case_census_digest(cases),
        policy_sha256=policy.digest())
    contexts = {**a, **b}
    before = {c.case_id for c in reference[:reference_before] + protected}
    after = {c.case_id for c in reference[:reference_after] + protected[:5]}
    fixed_pair = AssessmentPair(
        evaluate_capabilities(_solver(contexts, before), fixed, PARENT),
        evaluate_capabilities(_solver(contexts, after), fixed, CANDIDATE))
    decision = finalize_target_first_local_candidate(
        target, policy, fixed, fresh_pair, fixed_pair,
        retention_protection_plan_sha256="1" * 64,
        evaluated_capability_ids=(target, "protected"))
    assert decision.reason == reason
    assert decision.outcome_scores[0] == (target, 0, 3, 3)
    assert decision.fixed_reference_cohort_sha256 == fixed.expected_case_digest
    assert decision.fixed_reference_scores == (
        (target, reference_before, reference_after, 3), ("protected", 6, 5, 6))
