"""Production C06 authority for ordinary grade-neutral BAMF teaching priority."""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_salience import derive_salience, verify_salience_inputs
from bilqis_mlx.learning.salience_contracts import (
    ActionKind, AttentionOption, AuthoritySnapshot, FactOrigin, Metric, MetricRule,
    NoveltyState, Ordinal, SalienceContext, SaliencePolicy, Signal, SignedFact,
)
from bilqis_mlx.learning.salience_history import (
    EventKind, SalienceEvent, SalienceHistory, WindowPolicy,
)
from bilqis_mlx.learning.salience_teacher import AttentionFrontier
from bilqis_mlx.learning.teacher_lineage import priority_rotation_state
from bilqis_mlx.runtime.priority_source_offer import prepare_priority_source_offer
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef
from bilqis_mlx.semantics.domains import contract_digest


_SCOPE = "factory/foundation"
_SOURCE_EACH = 1
_REJECTION_JOURNAL_INVALID = "BAMF_PRIORITY_REJECTION_JOURNAL_INVALID"


@dataclass(frozen=True)
class AcceptedPriorityAuthority:
    frontier: AttentionFrontier
    history: SalienceHistory
    planning: object
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
    correction = parent.correction_frontier
    rights_epoch = correction.get("rights_epoch")
    correction_generation = correction.get("correction_generation")
    if (type(rights_epoch) is not int or rights_epoch < 0
            or type(correction_generation) is not int
            or correction_generation < 0):
        raise ValueError("BAMF_PRIORITY_CORRECTION_FRONTIER_INVALID")
    return SalienceContext(
        offer.release_sha256, binding, rights_epoch, correction_generation,
        offer.capability_id, capability_epoch,
        _SCOPE, offer.source_family_id, offer.generation_binding, teacher_epoch_digest)


def _offer_seed(next_seed: int, capability_id: str) -> int:
    raw = f"bilqis.bamf.c03.4-source-seed/v1|{next_seed}|{capability_id}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def _priority_planning(run_dir, source_context, atlas_artifact_path):
    """Project current A09 state from accepted custody without requiring a C07 lease."""
    from bilqis_mlx.factory import candidate_realizations
    from bilqis_mlx.factory.atlas_delta_adapter import (
        AtlasCoverageEpoch, _accepted_requested_keys,
    )
    from bilqis_mlx.factory.atlas_frontier import PlannerBudget
    from bilqis_mlx.factory.atlas_frontier_closure import resolve_frontier_closure
    from bilqis_mlx.factory.atlas_frontier_progress import plan_frontier_progress
    from bilqis_mlx.factory.atlas_frontier_selection import (
        ranked_frontier_target, select_frontier_delta_for_projection,
    )
    from bilqis_mlx.factory.atlas_runtime_snapshot import build_accepted_executable_snapshot
    from bilqis_mlx.factory.skos_curriculum import (
        LearnedFrontier, SOURCE_FAMILY_ADAPTERS, compile_semantic_curriculum,
        issue_source_context_transition_authority,
    )
    from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_obligation_credit
    from bilqis_mlx.runtime.atlas_flywheel_runtime import (
        _accepted_checkpoint, _accepted_selection, _candidate_frontier,
        _persist_ready_realizations,
    )
    from bilqis_mlx.runtime.autonomy_live import (
        build_live_autonomy_plan, reconcile_live_autonomy_state,
    )
    from bilqis_mlx.runtime.priority_qualification import PriorityPlanningInput

    run_dir = Path(run_dir)
    selection, feature_receipt = _accepted_selection(run_dir)
    if Path(selection.path).resolve() != Path(atlas_artifact_path).resolve():
        raise ValueError("BAMF_PRIORITY_ATLAS_SELECTION_DRIFT")
    current = source_context.release
    if selection.release_sha256 != feature_receipt.source_release_sha256:
        raise ValueError("BAMF_PRIORITY_ATLAS_RELEASE_DRIFT")
    candidate = compile_semantic_curriculum(
        selection, SOURCE_FAMILY_ADAPTERS,
        LearnedFrontier(selection.release_sha256))
    source = issue_source_context_transition_authority(selection)
    frontier = _candidate_frontier()
    staged = _persist_ready_realizations(
        run_dir, current, candidate, frontier, source_context.graph)
    plan = build_live_autonomy_plan(current, source_context.source_root)
    ledger = reconcile_live_autonomy_state(run_dir, current, plan)
    checkpoint = _accepted_checkpoint(run_dir)
    snapshot = build_accepted_executable_snapshot(
        candidate, source.frontier, source.policy, frontier, current, staged,
        budget=PlannerBudget(9, 16, 1000),
        admission_receipt_sha256=feature_receipt.acceptance_sha256,
        grade_labels=tuple(grade.grade_id for grade in current.execution_plan.grades),
    )
    closure = resolve_frontier_closure(
        snapshot, candidate.census, current_release=current,
        evidence_ledger=ledger, autonomy_plan=plan,
        checkpoint_sha256=checkpoint.sha256,
        optimizer_step=checkpoint.optimizer_step,
    )
    epoch = AtlasCoverageEpoch(
        snapshot, closure, frontier, current, staged,
        accepted_credit=read_accepted_atlas_obligation_credit(run_dir))
    epoch.verify()
    requested = _accepted_requested_keys(epoch)
    selected = projection = None
    try:
        semantic_id, rows = ranked_frontier_target(snapshot, closure, requested)
    except BilqisError as error:
        if error.context.get("reason") != "BAMF_PLANNER_NO_BOUNDED_READY_DELTA":
            raise
    else:
        try:
            projection = candidate_realizations.project_authoritative_target(
                semantic_id, current, rows)
        except ValueError as error:
            raise ValueError("BAMF_PRIORITY_A09_REALIZATION_MISSING") from error
        selected = select_frontier_delta_for_projection(
            snapshot, closure, current, projection, requested)
    progress = plan_frontier_progress(
        snapshot, closure, selected,
        current_release=current if selected is not None else None,
        selected_projection=projection)
    return PriorityPlanningInput(progress, closure, selected, projection)


def _current_rejections(run_dir, parent, cache):
    """Replay only rejections bound to the exact currently accepted B13 parent."""
    journal = Path(run_dir) / "events.jsonl"
    if not journal.exists():
        return ()
    if journal.is_symlink() or not journal.is_file():
        raise ValueError(_REJECTION_JOURNAL_INVALID)
    rows, seen = [], set()
    for raw in journal.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError(_REJECTION_JOURNAL_INVALID) from error
        if not isinstance(event, dict) or event.get("event") != "BAMF_CANDIDATE_REJECTED":
            continue
        if event.get("generation") != cache.generation:
            continue
        if (event.get("student_manifest_sha256") != cache.accepted_manifest_sha256
                or event.get("optimizer_step") != parent.retained_state.optimizer_step):
            raise ValueError("BAMF_PRIORITY_REJECTION_IDENTITY_DRIFT")
        evidence = event.get("evidence")
        if not isinstance(evidence, dict) or evidence.get("schema") != "bilqis.bamf.c16.3-rejection/v2":
            continue
        selected = evidence.get("selected_option_id")
        visit_id = evidence.get("visit_id")
        candidate_step = evidence.get("candidate_optimizer_step")
        retained_step = evidence.get("retained_optimizer_step")
        reason = evidence.get("retention_reason")
        if (not isinstance(selected, str) or not selected
                or not isinstance(visit_id, str) or not visit_id
                or type(candidate_step) is not int
                or candidate_step <= parent.retained_state.optimizer_step
                or retained_step != parent.retained_state.optimizer_step
                or not isinstance(reason, str) or not reason):
            raise ValueError("BAMF_PRIORITY_REJECTION_EVIDENCE_INVALID")
        receipt_sha256 = contract_digest(event)
        if receipt_sha256 in seen:
            continue
        seen.add(receipt_sha256)
        rows.append((selected, visit_id, reason, receipt_sha256))
    return tuple(rows)


def _planning_unlocks(capability_id, planning):
    selection = planning.selection
    if selection is None:
        return 0
    from bilqis_mlx.factory import candidate_realizations
    try:
        semantic_id = candidate_realizations.realized_atlas_semantic_id(capability_id)
    except ValueError:
        return 0
    return (selection.downstream_unlocks
            if semantic_id == selection.selected_semantic_id else 0)


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
    planning = _priority_planning(run_dir, source_context, atlas_artifact_path)
    offers = tuple((capability.id, prepare_priority_source_offer(
        source_context, parent, atlas_artifact_path,
        capability=capability.id,
        source_seed=_offer_seed(next_seed, capability.id), source_each=_SOURCE_EACH))
        for capability in source_context.release.execution_plan.capabilities)
    rejections = _current_rejections(run_dir, parent, cache)
    option_ids = {capability for capability, _ in offers}
    if any(capability not in option_ids for capability, *_ in rejections):
        raise ValueError("BAMF_PRIORITY_REJECTION_OPTION_DRIFT")
    rejection_recency = {}
    for offset, (capability, *_rest) in enumerate(rejections, start=1):
        rejection_recency[capability] = counter + offset
    now = counter + len(rejections)
    policy = _policy(source_context.release.release_sha256,
                     (offer.source_family_id for _, offer in offers), now, signer)
    teacher_digest = contract_digest(teacher_epoch)
    contexts = tuple(_context(parent, offer, teacher_digest) for _, offer in offers)
    snapshot = AuthoritySnapshot(contexts, now, registry)
    options, evidence_rows = [], []
    for context, (stable_id, offer) in zip(contexts, offers, strict=True):
        facts = tuple(_unknown_fact(metric, context, policy,
                                    offer.source_authority.content_sha256,
                                    now, signer)
                      for metric in (Metric.IMPACT_UNKNOWN,
                                     Metric.EXIGENCY_UNKNOWN,
                                     Metric.NOVELTY_UNKNOWN))
        evidence = derive_salience(verify_salience_inputs(
            facts, policy, snapshot, context))
        option = AttentionOption(
            stable_id, context, evidence.basis.digest(), ActionKind.TEACHING,
            max(last_selected.get(stable_id, 0), rejection_recency.get(stable_id, 0)),
            True, True, True, True, _planning_unlocks(stable_id, planning),
            False, False, signer.owner_id, "0" * 128)
        option = _signed(option, signer, DependencyKind.ARTIFACT,
                         "salience-option:" + stable_id)
        options.append(option)
        evidence_rows.append((stable_id, evidence))
    window = WindowPolicy(
        "bamf-foundation-window", "v1", policy.digest(),
        source_context.release.release_sha256, 2, now,
        signer.owner_id, "0" * 128)
    window = _signed(window, signer, DependencyKind.POLICY,
                     "salience-policy:" + window.policy_id)
    evidence_by_id = dict(evidence_rows)
    history_events = []
    for stable_id, visit_id, reason, receipt_sha256 in rejections:
        raw = SalienceEvent(
            "bamf-rejection:" + receipt_sha256, EventKind.OBSERVATION,
            f"{cache.run_id}:{cache.generation}:{cache.accepted_manifest_sha256}",
            visit_id,
            contract_digest(("bilqis.bamf.c16.3-rejection-observation/v1",
                             stable_id, reason)),
            None, evidence_by_id[stable_id], now, receipt_sha256,
            None, None, None, None, None, None,
            signer.owner_id, "0" * 128)
        history_events.append(_signed(
            raw, signer, DependencyKind.ARTIFACT,
            "salience-event:" + raw.event_id))
    return AcceptedPriorityAuthority(
        AttentionFrontier(tuple(options), tuple(evidence_rows), snapshot),
        SalienceHistory(window, tuple(history_events)), planning, offers, now)


__all__ = ("AcceptedPriorityAuthority", "issue_foundation_priority_authority")
