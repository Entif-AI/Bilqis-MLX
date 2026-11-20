"""Factory-only issuance adapter for C05 retention decisions."""
from __future__ import annotations


def make_factory_retention_issuer(raw_issue):
    def issue_factory_retention_decision(owner_evaluation):
        from bilqis_mlx.learning.atlas_retention_decision import (
            ACCEPTED_DECISION, DECISION_SCHEMA, REJECTED_DECISION, _invalid,
        )
        from bilqis_mlx.runtime.factory_retention_owner import (
            FactoryRetentionEvaluation, _require_factory_evaluation,
        )
        from bilqis_mlx.runtime.capability_retention import DecisionStatus

        if type(owner_evaluation) is not FactoryRetentionEvaluation:
            _invalid()
        _require_factory_evaluation(owner_evaluation)
        owner_evaluation.__post_init__()
        result = owner_evaluation.decision
        status = (ACCEPTED_DECISION if result.status is DecisionStatus.ELIGIBLE
                  else REJECTED_DECISION)
        return raw_issue((
            ("decision", status),
            ("reason", result.reason),
            ("parent_generation", owner_evaluation.parent_candidate_sha256),
            ("candidate_generation", owner_evaluation.candidate_candidate_sha256),
            ("evidence_sha256", result.evidence_sha256),
            ("policy_sha256", result.policy_sha256),
            ("blocking_capability", result.blocking_capability),
            ("blocking_scope", result.blocking_scope),
            ("baseline_coverage", (
                result.baseline_coverage.to_record()
                if result.baseline_coverage is not None else None)),
            ("evaluated_capability_ids", result.evaluated_capability_ids),
            ("retention_protection_plan_sha256",
             result.retention_protection_plan_sha256),
            ("broad_certification_trigger", result.broad_certification_trigger),
            ("blocking_score_budget", result.blocking_score_budget),
            ("schema_version", DECISION_SCHEMA),
        ), generation_authority_sha256=(
            owner_evaluation.candidate_generation_authority_sha256),
            expected_baseline_ledger_sha256=owner_evaluation.baseline_ledger.digest)

    return issue_factory_retention_decision
