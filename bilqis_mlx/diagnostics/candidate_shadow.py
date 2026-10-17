"""Unratified, source-only experiments for paired whole-student retention.

Explicit experiment tolerances produce observations and proposed decisions.
No candidate, optimizer, teacher reward, or training policy is mutated.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from ..generated_assessment import compare_on_same_cohort, digest
from .health_shadow import ShadowContext, ShadowPhase


class TrialShadowStatus(str, Enum):
    NOT_MEASURED = "NOT_MEASURED"
    ACQUISITION_OBSERVATION_ONLY = "ACQUISITION_OBSERVATION_ONLY"
    WOULD_REJECT = "WOULD_REJECT"
    WOULD_RETAIN = "WOULD_RETAIN"


@dataclass(frozen=True)
class TrialShadowPolicy:
    experiment_id: str
    version: str
    maximum_loss_by_capability: tuple[tuple[str, int], ...]

    def __post_init__(self):
        limits = dict(self.maximum_loss_by_capability)
        if (not self.experiment_id or not self.version or not limits or
                len(limits) != len(self.maximum_loss_by_capability) or
                any(not isinstance(cap, str) or not cap or type(limit) is not int or limit < 0
                    for cap, limit in limits.items())):
            raise ValueError("SHADOW_TRIAL_EXPLICIT_POLICY_REQUIRED")


@dataclass(frozen=True)
class CandidateShadowReview:
    status: TrialShadowStatus
    blockers: tuple[str, ...]
    regressions: tuple[tuple[str, int], ...]
    improvements: tuple[str, ...]
    policy_sha256: str
    evidence_sha256: str
    teacher_credit: str
    teacher_reward: None = None
    actual_veto: bool = False
    actual_teacher_reward_updates: int = 0
    unratified: bool = True


def review_candidate_shadow(parent: dict, candidate: dict, *, policy: TrialShadowPolicy,
                            context: ShadowContext, required_capabilities: tuple[str, ...],
                            trial_parent_sha256: str,
                            decision_receipts: tuple[str, ...]) -> CandidateShadowReview:
    """Compare one declared parent trial on exactly the same scored cohort.

    A single recorded action is eligible for controlled credit research, not
    proof of causality. Multiple actions remain explicitly unattributed.
    """
    blockers, gains, regressions = [], (), ()
    limits = dict(policy.maximum_loss_by_capability)
    try:
        gains = compare_on_same_cohort(candidate, parent)
        old, new = parent["checkpoint"], candidate["checkpoint"]
        if (not old.get("model_and_native_adamw") or not new.get("model_and_native_adamw") or
                not old.get("sha256") or not new.get("sha256") or
                old["sha256"] != trial_parent_sha256 or old["sha256"] == new["sha256"] or
                type(old.get("optimizer_step")) is not int or
                type(new.get("optimizer_step")) is not int or
                new["optimizer_step"] <= old["optimizer_step"]):
            blockers.append("SHADOW_TRIAL_PARENT_OR_COMPLETE_CHECKPOINT_UNVERIFIED")
        required = set(required_capabilities)
        if (not required or len(required) != len(required_capabilities) or
                set(parent["scores"]) != required or set(limits) != required):
            blockers.append("SHADOW_TRIAL_REQUIRED_CAPABILITIES_OR_LIMITS_MISSING")
        for receipt in (parent, candidate):
            for value in receipt["scores"].values():
                if (type(value["correct"]) is not int or type(value["total"]) is not int or
                        not 0 <= value["correct"] <= value["total"] or value["total"] < 1):
                    blockers.append("SHADOW_TRIAL_SCORE_INVALID")
        regressions = tuple(sorted((capability,
            parent["scores"][capability]["correct"] - result["correct"])
            for capability, result in candidate["scores"].items()
            if parent["scores"][capability]["correct"] > result["correct"]))
    except (KeyError, TypeError, ValueError):
        blockers.append("SHADOW_TRIAL_NOT_COMPARABLE")
    if blockers:
        status = TrialShadowStatus.NOT_MEASURED
    elif context.phase is ShadowPhase.ACQUISITION:
        status = TrialShadowStatus.ACQUISITION_OBSERVATION_ONLY
    else:
        status = (TrialShadowStatus.WOULD_REJECT if any(loss > limits[cap] for cap, loss in regressions)
                  else TrialShadowStatus.WOULD_RETAIN)
    credit = ("NOT_MEASURED" if blockers or not decision_receipts else
              "NOT_MEASURED_MULTIPLE_ACTIONS" if len(decision_receipts) != 1 else
              "SINGLE_RECORDED_DECISION_REQUIRES_CONTROLLED_VALIDATION")
    return CandidateShadowReview(status, tuple(dict.fromkeys(blockers)), regressions, gains,
        digest(asdict(policy)), digest({"parent": parent, "candidate": candidate,
            "trial_parent": trial_parent_sha256, "decisions": decision_receipts,
            "context": asdict(context)}), credit)
