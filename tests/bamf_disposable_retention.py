"""Disposable C05/B13 fixture issuance. This module is excluded from the wheel.

It deliberately uses the private issuer sentinel to test positive B13 custody
mechanics while the production C05/Factory source owner remains unavailable.
Never import this module from a production runtime path.
"""
from __future__ import annotations

from bilqis_mlx.learning import atlas_retention_decision as owner
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.runtime.capability_retention import (
    DecisionStatus, evaluate_retention_candidate,
)


def issue_disposable_screen(screen, parent_state, candidate_state):
    parent_id = candidate_identity_digest(parent_state)
    candidate_id = candidate_identity_digest(candidate_state)
    result = evaluate_retention_candidate(
        screen[0], screen[1], screen[2], screen[3], screen[4],
        parent_id, candidate_id,
    )
    decision = object.__new__(owner.CandidateRetentionDecision)
    for name, value in (
            ("decision", owner.ACCEPTED_DECISION
             if result.status is DecisionStatus.ELIGIBLE else owner.REJECTED_DECISION),
            ("reason", result.reason),
            ("parent_generation", parent_id),
            ("candidate_generation", candidate_id),
            ("evidence_sha256", result.evidence_sha256),
            ("policy_sha256", result.policy_sha256),
            ("schema_version", owner.DECISION_SCHEMA),
            ("_issuance", owner._DECISION_ISSUER)):
        object.__setattr__(decision, name, value)
    decision.__post_init__()
    return decision
