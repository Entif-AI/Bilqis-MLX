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


@pytest.mark.parametrize("fresh_counts,reference_counts,peer_counts", [
    ((4, 6), (5, 4), ((2, 4), (6, 5), (5, 4), (5, 4), (6, 4))),
    ((1, 3), (4, 4), ((4, 4), (5, 5), (4, 6), (4, 3), (4, 3))),
])
def test_fresh_gain_cannot_hide_negative_reference_utility(
        fresh_counts, reference_counts, peer_counts):
    target, _, template = _target_pair(measured=True, gain=True, group="grade")
    peers = tuple(f"peer-{index}" for index in range(len(peer_counts)))
    groups = tuple((cap, "grade") for cap in (target, *peers))
    ids = tuple(cap for cap, _ in groups)
    fresh, fresh_context = _cases(target, "grade", 6, "fresh")
    fixed_cases, fixed_context = (), {}
    for cap in ids:
        cases, contexts = _cases(cap, "grade", 6, f"reference-{cap}")
        fixed_cases += cases
        fixed_context.update(contexts)
    coverage = BaselineCoverage(
        ids, (), (("grade", len(ids), len(ids)),), len(ids), len(ids), "e" * 64)
    policy = FoundationRetentionPolicy(
        groups, ("grade",), tuple((cap, 1) for cap in peers), 6,
        case_census_digest(fixed_cases), coverage)

    def pair(cases, contexts, scope, kind, counts):
        cohort = replace(
            template.parent.cohort, kind=kind, cases=cases,
            capability_groups=scope, expected_case_digest=case_census_digest(cases),
            policy_sha256=policy.digest())
        selected = tuple({
            case.case_id for (cap, _), count in zip(scope, limits)
            for case in tuple(c for c in cases if c.capability_id == cap)[:count]
        } for limits in zip(*counts))
        return AssessmentPair(
            evaluate_capabilities(_solver(contexts, selected[0]), cohort, PARENT),
            evaluate_capabilities(_solver(contexts, selected[1]), cohort, CANDIDATE))

    fresh_pair = pair(fresh, fresh_context, groups[:1], EvidenceKind.FRESH_TARGET,
                      (fresh_counts,))
    reference = pair(fixed_cases, fixed_context, groups, EvidenceKind.FIXED_SCHOOL,
                     (reference_counts, *peer_counts))
    decision = finalize_target_first_local_candidate(
        target, policy, reference.parent.cohort, fresh_pair, reference,
        retention_protection_plan_sha256="1" * 64, evaluated_capability_ids=ids)
    assert decision.reason == "PROTECTED_CAPABILITY_REGRESSION"
    assert decision.outcome_scores[0] == (target, *fresh_counts, 6)
    assert decision.fixed_reference_scores == tuple(
        (cap, *counts, 6) for cap, counts in zip(ids, (reference_counts, *peer_counts)))
