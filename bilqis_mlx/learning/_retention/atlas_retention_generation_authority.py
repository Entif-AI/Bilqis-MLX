"""Exact-generation rebinding for an already screened C05 retention decision."""
from __future__ import annotations


def bind_factory_retention_generation_authority(
        decision, owner_evaluation, successor):
    """Advance hidden motif authority to the final owner-composed B13 successor."""
    from bilqis_mlx.learning.atlas_retention_decision import (
        _invalid, _rebind_issued_decision_generation_authority,
        _require_issued_decision,
    )
    from bilqis_mlx.runtime.factory_retention_owner import (
        FactoryRetentionEvaluation, _require_factory_evaluation,
    )
    from bilqis_mlx.runtime.bamf_bundle.records import BamfBundleCandidate
    from bilqis_mlx.runtime.bamf_bundle.genesis.records import (
        successor_candidate_identity_digest,
    )
    from bilqis_mlx.runtime.bamf_bundle.motif.transition import (
        is_motif_allocation_transition,
    )
    from bilqis_mlx.learning._atlas_candidate.identity_binding import (
        candidate_identity_for_canonical_consumer,
    )

    _require_issued_decision(decision)
    if type(owner_evaluation) is not FactoryRetentionEvaluation:
        _invalid()
    _require_factory_evaluation(owner_evaluation)
    owner_evaluation.__post_init__()
    prior = owner_evaluation.candidate_generation_authority_sha256
    if prior is None:
        return decision
    if (type(successor) is not BamfBundleCandidate
            or not is_motif_allocation_transition(successor.transition)
            or successor.retained_state is not owner_evaluation.candidate_state
            or candidate_identity_for_canonical_consumer(successor.retained_state)
            != owner_evaluation.candidate_candidate_sha256
            or successor.baseline_evidence
            != owner_evaluation.baseline_ledger.to_record()):
        _invalid()
    return _rebind_issued_decision_generation_authority(
        decision, prior, successor_candidate_identity_digest(successor))
