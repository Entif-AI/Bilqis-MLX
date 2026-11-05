"""Strict-generalization paired C05 decision logic."""
from __future__ import annotations

from ..learning.retention_policy import retention_reason, scaled_loss_allowance
from .capability_evaluation import EvidenceStage, _invalid
from .capability_retention import (
    Decision, DecisionStatus, PairedRetentionEvidence,
)


def retain_candidate(parent, candidate, paired_assessment) -> Decision:
    evidence = paired_assessment
    if (not isinstance(evidence, PairedRetentionEvidence)
            or parent != evidence.target.parent.generation_digest
            or candidate != evidence.target.candidate.generation_digest):
        _invalid("BAMF_RETENTION_GENERATION_DRIFT")
    target = evidence.target_capability
    census = dict(evidence.policy.capability_groups)
    fixed = evidence.fixed_school

    def net(pair, capabilities):
        return sum(pair.delta(capability) for capability in capabilities)

    lesson = tuple(cap for cap, group in census.items() if group == census[target])
    stage = evidence.target.parent.cohort.evidence_stage
    protected_pairs = (
        (fixed,) if stage is EvidenceStage.FOUNDATION_ACQUISITION
        else (evidence.fresh_lesson, fixed))
    exceeded = tuple(
        capability
        for pair in protected_pairs
        for capability, reference in evidence.policy.protected_reference_losses
        if capability in dict(pair.parent.cohort.capability_groups)
        and -pair.delta(capability) > scaled_loss_allowance(
            pair.parent.score(capability)[1], reference, evidence.policy.probe_each))
    reason = retention_reason(
        no_target_gain=(stage is EvidenceStage.STRICT_GENERALIZATION
                        and evidence.target.delta(target) <= 0),
        same_grade_net_gain=(0 if stage is EvidenceStage.FOUNDATION_ACQUISITION
                             else net(evidence.fresh_lesson, lesson)),
        fixed_grade_regression=net(fixed, lesson) < 0,
        active_grade_regression=any(
            net(fixed, tuple(cap for cap, group in census.items() if group == protected)) < 0
            for protected in evidence.policy.protected_groups),
        whole_school_regression=net(fixed, census) < 0,
        frontier_measured=True, fragile_losses=False, exceeded=bool(exceeded))
    return Decision(
        DecisionStatus.ELIGIBLE if reason == "PAIRED_SCREEN_WITHIN_BUDGET"
        else DecisionStatus.REJECT,
        reason, parent, candidate, evidence.digest(), evidence.policy.digest(),
        blocking_capability=(exceeded[0]
                             if reason == "PROTECTED_CAPABILITY_REGRESSION"
                             and exceeded else None))


__all__ = ("retain_candidate",)
