"""Native FOUNDATION C05 requires material utility for regression trades."""
from fractions import Fraction
from types import SimpleNamespace
from unittest.mock import patch

from bilqis_mlx.runtime.capability_retention_foundation import (
    FoundationRetentionPolicy,
    mastery_debt_utility_margin_units,
)
from bilqis_mlx.runtime.capability_retention_foundation_runtime import (
    final_fixed_school_decision,
)


SCORES = {
    "A.LINK": {"before": 2, "after": 3, "total": 6},
    "A.MAPS": {"before": 3, "after": 4, "total": 6},
    "A.EDGE": {"before": 5, "after": 3, "total": 6},
    "A.MEMBER": {"before": 5, "after": 4, "total": 6},
    "A.IDENTITY": {"before": 4, "after": 4, "total": 6},
    "A.PARENT": {"before": 4, "after": 4, "total": 6},
}


def _decision(margin):
    groups = tuple((capability, "A") for capability in SCORES)
    protected = tuple(capability for capability in SCORES if capability != "A.LINK")
    policy = FoundationRetentionPolicy(
        groups, ("A",), tuple((capability, 1) for capability in protected),
        6, "f" * 64,
        mastery_debt_min_utility_units=mastery_debt_utility_margin_units(margin))
    pair = SimpleNamespace(
        delta=lambda capability: SCORES[capability]["after"] - SCORES[capability]["before"])
    context = (
        pair, dict(groups), None, tuple(SCORES), set(SCORES), SCORES, 1)
    with patch(
            "bilqis_mlx.runtime.capability_retention_foundation_runtime._fixed_school_score_context",
            return_value=context):
        return final_fixed_school_decision(
            "A.LINK", "A", dict(policy.protected_reference_losses), policy,
            object(), "a" * 64, "b" * 64,
            lambda _pairs, _blocking: "e" * 64, (), {}, {}, {}, {},
            ordinary=True)


def test_native_default_rejects_recent_one_over_36_trade():
    decision = _decision(0.05)
    assert decision.status.value == "REJECT"
    assert decision.reason == "PROTECTED_CAPABILITY_REGRESSION"


def test_native_explicit_lower_margin_can_admit_same_trade():
    decision = _decision(0.02)
    assert decision.status.value == "ELIGIBLE"
    assert decision.reason == "PAIRED_SCREEN_WITHIN_BUDGET"


def test_native_margin_is_strictly_exceeded_not_merely_met():
    groups = (("A.LINK", "A"), ("A.MAPS", "A"))
    policy = FoundationRetentionPolicy(
        groups, ("A",), (("A.MAPS", 1),), 6, "f" * 64)
    assert policy.mastery_debt_utility_exceeds_margin(Fraction(1, 20)) is False
