"""Live C05 authority must not own a completed candidate's numerical state."""
import weakref

import pytest

from bilqis_mlx.learning.atlas_retention_decision import issue_factory_retention_decision
from bilqis_mlx.runtime._factory_identity_evaluation import (
    _raw_issue_owner_evaluation,
    _require_factory_evaluation,
)
from bilqis_mlx.runtime.baseline.lifecycle import BaselineLedger
from bilqis_mlx.runtime.capability_retention import Decision, DecisionStatus


class _OptimizerPayload:
    """Stand-in for the native arrays held by an optimizer."""


class _Candidate:
    def __init__(self):
        self.optimizer = _OptimizerPayload()


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (DecisionStatus.REJECT, "NO_MEASURABLE_TARGET_GAIN"),
        (DecisionStatus.ELIGIBLE, "PAIRED_SCREEN_WITHIN_BUDGET"),
    ],
)
def test_completed_evaluation_releases_candidate_while_decision_survives(status, reason):
    candidate = _Candidate()
    candidate_ref = weakref.ref(candidate)
    optimizer_ref = weakref.ref(candidate.optimizer)
    evaluation = _raw_issue_owner_evaluation(
        Decision(status, reason, "a" * 64, "b" * 64, "c" * 64, "d" * 64),
        "e" * 64, "f" * 64, None,
        parent_state=object(), candidate_state=candidate,
        baseline_ledger=BaselineLedger.empty(),
    )
    evaluation_ref = weakref.ref(evaluation)
    decision = issue_factory_retention_decision(evaluation)
    del candidate
    assert candidate_ref() is evaluation.candidate_state
    assert _require_factory_evaluation(evaluation) is evaluation
    assert decision.accepted is (status is DecisionStatus.ELIGIBLE)

    del evaluation

    assert evaluation_ref() is None
    assert candidate_ref() is None
    assert optimizer_ref() is None
    assert decision.to_record()["reason"] == reason
    decision.__post_init__()
