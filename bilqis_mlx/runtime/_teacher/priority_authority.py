"""Production C06 authority for ordinary grade-neutral BAMF teaching priority."""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib

from bilqis_mlx.learning.atlas_salience import derive_salience, verify_salience_inputs
from bilqis_mlx.learning.salience_contracts import (
    ActionKind, AttentionOption, AuthoritySnapshot, FactOrigin, Metric, MetricRule,
    NoveltyState, Ordinal, SalienceContext, SaliencePolicy, Signal, SignedFact,
)
from bilqis_mlx.learning.salience_history import SalienceHistory, WindowPolicy
from bilqis_mlx.learning.salience_teacher import AttentionFrontier
from bilqis_mlx.learning.teacher_lineage import priority_rotation_state
from bilqis_mlx.runtime.priority_source_offer import prepare_priority_source_offer
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef
from bilqis_mlx.semantics.domains import contract_digest


_SCOPE = "factory/foundation"
_SOURCE_EACH = 1


@dataclass(frozen=True)
class AcceptedPriorityAuthority:
    frontier: AttentionFrontier
    history: SalienceHistory
    offers: tuple
    now: int


def _signed(record, signer, kind, key):
    dependency = DependencyRef(kind, key)
    return replace(record, signature_hex=signer.sign(dependency, record.signing_bytes()))


def _policy(release_sha256, families, now, signer):
    count_metrics = (Metric.DOWNSTREAM_COUNT, Metric.COVERAGE_COUNT,
                     Metric.BLOCKED_COUNT, Metric.REPAIR_COUNT)
    rules = (
        MetricRule(Metric.DECLARED_IMPACT, "ordinal-index", (1, 2, 3, 4),
                   tuple(Ordinal), "bamf/foundation/declared/v1"),
        MetricRule(Metric.DEADLINE_AT, "seconds-until-deadline", (1, 61, 3601),
                   (Ordinal.CRITICAL, Ordinal.HIGH, Ordinal.MODERATE, Ordinal.LOW),
                   "bamf/foundation/deadline/v1"),
        *(MetricRule(metric, "count", (1, 3, 8),
                    (Ordinal.LOW, Ordinal.MODERATE, Ordinal.HIGH, Ordinal.CRITICAL),
                    "bamf/foundation/" + metric.value + "/v1")
          for metric in count_metrics),
    )
    raw = SaliencePolicy(
        "bamf-foundation", "v1", release_sha256, tuple(sorted(set(families))), rules,
        ((NoveltyState.MATCHED, Ordinal.LOW),
         (NoveltyState.STRUCTURE_CHANGED, Ordinal.MODERATE),
         (NoveltyState.OUTCOME_CHANGED, Ordinal.HIGH),
         (NoveltyState.EXPECTED_MISSING, Ordinal.CRITICAL),
         (NoveltyState.REPORTED_NEGATIVE, Ordinal.LOW)),
        ((Signal.IMPACT, (Metric.DECLARED_IMPACT,)),
         (Signal.EXIGENCY, (Metric.BLOCKED_COUNT,)),
         (Signal.NOVELTY, (Metric.NOVELTY_COMPARISON,))),
        now, signer.owner_id, "0" * 128)
    return _signed(raw, signer, DependencyKind.POLICY,
                   "salience-policy:" + raw.policy_id)


def _unknown_fact(metric, context, policy, receipt, now, signer):
    fact_id = f"{context.capability_id}:{metric.value}"
    raw = SignedFact(
        fact_id, metric, 0, FactOrigin.SOURCE, context, policy.digest(), receipt,
        now, now, now, now, signer.owner_id, "0" * 128)
    return _signed(raw, signer, DependencyKind.SOURCE, "salience-fact:" + fact_id)


def _context(parent, offer, teacher_epoch_digest):
    binding = offer.source_binding_digest
    capability_epoch = contract_digest((
        "bilqis.bamf.c03.4-capability-epoch/v1", offer.release_sha256,
        offer.capability_id, binding))
    compiler = parent.compiler_features
    return SalienceContext(
        offer.release_sha256, binding, compiler["rights_epoch"],
        compiler["correction_generation"], offer.capability_id, capability_epoch,
        _SCOPE, offer.source_family_id, offer.generation_binding, teacher_epoch_digest)


def _offer_seed(next_seed: int, capability_id: str) -> int:
    raw = f"bilqis.bamf.c03.4-source-seed/v1|{next_seed}|{capability_id}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def issue_foundation_priority_authority(
        run_dir, source_context, parent, teacher_epoch, atlas_artifact_path):
    """Issue only signed UNKNOWN salience; C06 ranking owns the resulting order."""
    from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import _accepted_correction_registry
    from bilqis_mlx.runtime.bamf_bundle._darwin_salience_signer import (
        read_host_system_source_authority_signer,
    )
    cache, registry = _accepted_correction_registry(run_dir)
    signer = read_host_system_source_authority_signer(registry)
    next_seed = parent.teacher_state.get("next_seed")
    if type(next_seed) is not int or next_seed < 0:
        raise ValueError("BAMF_PRIORITY_TEACHER_SEED_INVALID")
    counter, last_selected = priority_rotation_state(parent.teacher_state)
    offers = tuple((capability.id, prepare_priority_source_offer(
        source_context, parent, atlas_artifact_path,
        capability=capability.id,
        source_seed=_offer_seed(next_seed, capability.id), source_each=_SOURCE_EACH))
        for capability in source_context.release.execution_plan.capabilities)
    policy = _policy(source_context.release.release_sha256,
                     (offer.source_family_id for _, offer in offers), counter, signer)
    teacher_digest = contract_digest(teacher_epoch)
    contexts = tuple(_context(parent, offer, teacher_digest) for _, offer in offers)
    snapshot = AuthoritySnapshot(contexts, counter, registry)
    options, evidence_rows = [], []
    for context, (stable_id, offer) in zip(contexts, offers, strict=True):
        facts = tuple(_unknown_fact(metric, context, policy,
                                    offer.source_authority.content_sha256,
                                    counter, signer)
                      for metric in (Metric.IMPACT_UNKNOWN,
                                     Metric.EXIGENCY_UNKNOWN,
                                     Metric.NOVELTY_UNKNOWN))
        evidence = derive_salience(verify_salience_inputs(
            facts, policy, snapshot, context))
        option = AttentionOption(
            stable_id, context, evidence.basis.digest(), ActionKind.TEACHING,
            last_selected.get(stable_id, 0), True, True, True, True, 0,
            False, False, signer.owner_id, "0" * 128)
        option = _signed(option, signer, DependencyKind.ARTIFACT,
                         "salience-option:" + stable_id)
        options.append(option)
        evidence_rows.append((stable_id, evidence))
    window = WindowPolicy(
        "bamf-foundation-window", "v1", policy.digest(),
        source_context.release.release_sha256, 2, counter,
        signer.owner_id, "0" * 128)
    window = _signed(window, signer, DependencyKind.POLICY,
                     "salience-policy:" + window.policy_id)
    return AcceptedPriorityAuthority(
        AttentionFrontier(tuple(options), tuple(evidence_rows), snapshot),
        SalienceHistory(window, ()), offers, counter)


__all__ = ("AcceptedPriorityAuthority", "issue_foundation_priority_authority")
