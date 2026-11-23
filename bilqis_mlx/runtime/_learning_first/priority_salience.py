"""Strict C06 salience evidence helpers kept off the learning-first path."""
from dataclasses import replace

from bilqis_mlx.learning.atlas_salience import derive_salience, verify_salience_inputs
from bilqis_mlx.learning.salience_contracts import (
    ActionKind, AttentionOption, AuthoritySnapshot, FactOrigin, Metric, MetricRule,
    NoveltyState, Ordinal, SalienceContext, SaliencePolicy, Signal, SignedFact,
)
from bilqis_mlx.learning.salience_history import (
    EventKind, SalienceEvent, SalienceHistory, WindowPolicy,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef
from bilqis_mlx.semantics.domains import contract_digest


def signed(record, signer, kind, key):
    dependency = DependencyRef(kind, key)
    return replace(record, signature_hex=signer.sign(dependency, record.signing_bytes()))


def policy(release_sha256, families, now, signer):
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
    return signed(raw, signer, DependencyKind.POLICY,
                  "salience-policy:" + raw.policy_id)


def unknown_fact(metric, context, salience_policy, receipt, now, signer):
    fact_id = f"{context.capability_id}:{metric.value}"
    raw = SignedFact(
        fact_id, metric, 0, FactOrigin.SOURCE, context,
        salience_policy.digest(), receipt, now, now, now, now,
        signer.owner_id, "0" * 128)
    return signed(raw, signer, DependencyKind.SOURCE, "salience-fact:" + fact_id)


def salience_context(parent, offer, teacher_epoch_digest, *, scope):
    binding = offer.source_binding_digest
    capability_epoch = contract_digest((
        "bilqis.bamf.c03.4-capability-epoch/v1", offer.release_sha256,
        offer.capability_id, binding))
    correction = parent.correction_frontier
    rights_epoch = correction.get("rights_epoch")
    correction_generation = correction.get("correction_generation")
    if (type(rights_epoch) is not int or rights_epoch < 0
            or type(correction_generation) is not int
            or correction_generation < 0):
        from bilqis_mlx.errors import ErrorBus, SCHOOL
        ErrorBus.Raise(
            SCHOOL.BAMF_CURRICULUM.INVALID,
            reason="BAMF_PRIORITY_CORRECTION_FRONTIER_INVALID")
    return SalienceContext(
        offer.release_sha256, binding, rights_epoch, correction_generation,
        offer.capability_id, capability_epoch, scope, offer.source_family_id,
        offer.generation_binding, teacher_epoch_digest)


def priority_options(parent, release_sha256, offers, teacher_epoch, counter,
                     last_selected, rejection_count, rejection_positions,
                     registry, signer, planning, *, scope, planning_unlocks):
    now = counter + rejection_count
    rejection_recency = {
        capability: counter + position
        for capability, position in rejection_positions.items()
    }
    salience_policy = policy(
        release_sha256, (offer.source_family_id for _, offer in offers), now, signer)
    teacher_digest = contract_digest(teacher_epoch)
    contexts = tuple(
        salience_context(parent, offer, teacher_digest, scope=scope)
        for _, offer in offers)
    snapshot = AuthoritySnapshot(contexts, now, registry)
    options, evidence_rows = [], []
    for context, (stable_id, offer) in zip(contexts, offers, strict=True):
        receipt = offer.source_authority.content_sha256
        facts = tuple(
            unknown_fact(metric, context, salience_policy, receipt, now, signer)
            for metric in (
                Metric.IMPACT_UNKNOWN, Metric.EXIGENCY_UNKNOWN, Metric.NOVELTY_UNKNOWN))
        evidence = derive_salience(verify_salience_inputs(
            facts, salience_policy, snapshot, context))
        option = AttentionOption(
            stable_id, context, evidence.basis.digest(), ActionKind.TEACHING,
            max(last_selected.get(stable_id, 0), rejection_recency.get(stable_id, 0)),
            True, True, True, True, planning_unlocks(stable_id, planning),
            False, False, signer.owner_id, "0" * 128)
        option = signed(
            option, signer, DependencyKind.ARTIFACT, "salience-option:" + stable_id)
        options.append(option)
        evidence_rows.append((stable_id, evidence))
    return now, salience_policy, snapshot, tuple(options), tuple(evidence_rows)


def priority_history(
        source_context, cache, signer, salience_policy, evidence_rows, rejections, now):
    window = WindowPolicy(
        "bamf-foundation-window", "v1", salience_policy.digest(),
        source_context.release.release_sha256, 2, now,
        signer.owner_id, "0" * 128)
    window = signed(
        window, signer, DependencyKind.POLICY, "salience-policy:" + window.policy_id)
    evidence_by_id = dict(evidence_rows)
    events = []
    for stable_id, visit_id, reason, receipt_sha256 in rejections[-window.window_size:]:
        raw = SalienceEvent(
            "bamf-rejection:" + receipt_sha256, EventKind.OBSERVATION,
            f"{cache.run_id}:{cache.generation}:{cache.accepted_manifest_sha256}",
            visit_id,
            contract_digest(("bilqis.bamf.c16.3-rejection-observation/v1",
                             stable_id, reason)),
            None, evidence_by_id[stable_id], now, receipt_sha256,
            None, None, None, None, None, None,
            signer.owner_id, "0" * 128)
        events.append(signed(
            raw, signer, DependencyKind.ARTIFACT, "salience-event:" + raw.event_id))
    return SalienceHistory(window, tuple(events))


__all__ = ('priority_history', 'priority_options')
