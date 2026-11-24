"""Qualify signed C06 priorities against admitted source offers and A09 planning."""
from dataclasses import dataclass
from bilqis_mlx.factory import candidate_realizations
from bilqis_mlx.learning.atlas_salience import (
    derive_salience, rank_attention_options, verify_salience_inputs,
)
from bilqis_mlx.learning.salience_contracts import ActionKind
from bilqis_mlx.learning.salience_history import completed_windows
from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import _accepted_correction_registry
from bilqis_mlx.semantics.domains import contract_digest
from .priority_qualification_planning import (
    _PLANNING_OWNER,
    PriorityPlanningInput, _has_current_planning_verification,
    _issue_internal_priority_planning, _mint_planning_verification,
    _invalid, _planning, _planning_fingerprint,
)

PRIORITY_OFFER_PAIR_WIDTH = 2

@dataclass(frozen=True)
class QualifiedPriority:
    ranked: object
    offers: tuple
    holds: tuple


def _planning_hold(option, selection):
    if option.downstream_unlocks == 0:
        return False
    try:
        identity = candidate_realizations.realized_atlas_semantic_id(option.context.capability_id)
    except ValueError:
        return True
    return (selection is None or identity != selection.selected_semantic_id
            or option.downstream_unlocks != selection.downstream_unlocks)


def _grade(program, school, capability):
    grades = tuple(grade.id for grade in program.grades
                   if any(item.id == capability for item in grade.capabilities))
    return grades[0] if len(grades) == 1 else None


def _verify_planning(planning, release, observer):
    def verify():
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
            strict_mode_enabled,
        )
        if (not strict_mode_enabled()
                and type(planning) is PriorityPlanningInput
                and getattr(planning, '_owner', None) is _PLANNING_OWNER):
            progress = planning.progress
            closure = planning.closure
            selection = planning.selection
            projection = planning.selected_projection
            expected = (
                id(planning),
                id(progress),
                id(progress.input_snapshot),
                progress.input_snapshot_sha256,
                id(closure),
                closure.closure_sha256,
                release.release_sha256,
                None if selection is None else (
                    id(selection), selection.selection_sha256),
                None if projection is None else (
                    id(projection), projection.projection_sha256),
            )
            if getattr(planning, '_verification', None) != expected:
                _invalid('BAMF_PRIORITY_PLANNING_VERIFICATION_INVALID')
            return
        if _has_current_planning_verification(planning, release):
            return
        _planning(planning, release)
        if getattr(planning, '_owner', None) is _PLANNING_OWNER:
            _mint_planning_verification(planning, release)

    if observer is None:
        verify()
        return
    from bilqis_mlx.factory.atlas_frontier_progress_metrics import (
        frontier_verification_measurement,
    )
    with frontier_verification_measurement(observer):
        verify()


def _lawful_priority_context(
        run_dir, source_context, parent, lawful_frontier,
        planning_generation):
    from bilqis_mlx.runtime.lawful_teaching_frontier import (
        require_bound_lawful_teaching_frontier,
    )
    if planning_generation is None:
        source_context.require_accepted_runtime(run_dir)
        cache, registry = _accepted_correction_registry(run_dir)
    else:
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
            strict_mode_enabled,
        )
        from bilqis_mlx.runtime.priority_source_offer import (
            _require_planning_generation,
            _require_planning_generation_identity,
        )
        require_generation = (
            _require_planning_generation
            if strict_mode_enabled() else _require_planning_generation_identity)
        cache, _authenticated = require_generation(
            planning_generation, source_context, parent)
        registry = cache._correction_registry
        if getattr(lawful_frontier, "_planning_generation", None) is not planning_generation:
            _invalid('BAMF_PRIORITY_LAWFUL_FRONTIER_BINDING_DRIFT')
        if not strict_mode_enabled():
            if (getattr(lawful_frontier, '_source_context', None) is not source_context
                    or getattr(lawful_frontier, '_parent', None) is not parent
                    or lawful_frontier.accepted_manifest_sha256
                       != planning_generation.accepted_manifest_sha256
                    or lawful_frontier.candidate_identity_sha256
                       != planning_generation.parent_candidate_identity_sha256
                    or lawful_frontier.admitted_release_sha256
                       != source_context.release.release_sha256):
                _invalid('BAMF_PRIORITY_LAWFUL_FRONTIER_BINDING_DRIFT')
            return cache, registry, set(lawful_frontier.ready_capability_ids)
        from bilqis_mlx.runtime.bamf_bundle.currentness_transaction import (
            refresh_accepted_currentness,
        )
        currentness_step = refresh_accepted_currentness(
            planning_generation._accepted_currentness, parent)
        require_bound_lawful_teaching_frontier(
            lawful_frontier, source_context, parent,
            currentness_step=currentness_step)
        return cache, registry, set(lawful_frontier.ready_capability_ids)
    require_bound_lawful_teaching_frontier(lawful_frontier, source_context, parent)
    return cache, registry, set(lawful_frontier.ready_capability_ids)


def _verify_frontier_evidence(frontier, history):
    completed_windows(history)
    evidence = dict(frontier.evidence)
    for item in evidence.values():
        basis = item.basis
        verified = verify_salience_inputs(
            basis.facts, basis.policy, frontier.snapshot, basis.context)
        if derive_salience(verified) != item:
            _invalid('BAMF_PRIORITY_EVIDENCE_DRIFT')
    rank_attention_options(frontier.options, evidence, frontier.snapshot)
    return evidence


def _validate_priority_offers(offers, frontier, lawful_ids, offer_type):
    if (type(offers) is not tuple
            or any(type(pair) is not tuple
            or len(pair) != PRIORITY_OFFER_PAIR_WIDTH
            or not isinstance(pair[0], str) or type(pair[1]) is not offer_type
            for pair in offers) or len(dict(offers)) != len(offers)
            or not set(dict(offers)).issubset({option.stable_id for option in frontier.options})
            or any(pair[1].capability_id not in lawful_ids for pair in offers)):
        _invalid('BAMF_PRIORITY_OFFERS_INVALID')


def requalify_priority(run_dir, source_context, parent, frontier, history,
                       planning, offers, program, school, teacher_epoch, *, now,
                       lawful_frontier, planning_generation=None,
                       planning_observer=None):
    from bilqis_mlx.runtime.priority_source_offer import PreparedPrioritySourceOffer
    cache, registry, lawful_ids = _lawful_priority_context(
        run_dir, source_context, parent, lawful_frontier, planning_generation)
    if (frontier.snapshot.registry.digest != registry.digest
            or frontier.snapshot.as_of != now or school.course_digest != program.digest()):
        _invalid('BAMF_PRIORITY_AUTHORITY_DRIFT')
    _verify_planning(planning, source_context.release, planning_observer)
    evidence = _verify_frontier_evidence(frontier, history)
    _validate_priority_offers(
        offers, frontier, lawful_ids, PreparedPrioritySourceOffer)
    by_id = dict(offers)
    eligible, holds = [], []
    release = source_context.release
    exclusions = {
        item.capability_id: item.code.value
        for item in lawful_frontier.exclusions
    }
    if len(exclusions) != len(lawful_frontier.exclusions):
        _invalid('BAMF_PRIORITY_LAWFUL_FRONTIER_BINDING_DRIFT')
    for option in frontier.options:
        cap, context = option.context.capability_id, option.context
        if (cap not in release.execution_plan.capability_map
                or cap not in release.curriculum.capability_map):
            holds.append((option.stable_id, 'CAPABILITY_NOT_ADMITTED'))
            continue
        if cap not in lawful_ids:
            exclusion = exclusions.get(cap)
            if exclusion is None:
                _invalid('BAMF_PRIORITY_LAWFUL_FRONTIER_BINDING_DRIFT')
            holds.append((option.stable_id, exclusion))
            continue
        if option.action_kind in (ActionKind.CORRECTION, ActionKind.PROCEDURE_REPAIR):
            eligible.append(option)
            continue
        if cap not in release.source_bindings.by_capability:
            holds.append((option.stable_id, 'SOURCE_OFFER_HELD'))
            continue
        offer = by_id.get(option.stable_id)
        if offer is None:
            holds.append((option.stable_id, 'SOURCE_OFFER_MISSING'))
            continue
        if (context.semantic_release != release.release_sha256
                or context.generation_digest != cache.generation_binding
                or context.teacher_epoch_digest != contract_digest(teacher_epoch)
                or context.source_binding_digest != contract_digest(release.source_bindings.by_capability[cap])
                or context.source_binding_digest != offer.source_binding_digest
                or context.source_family_id != offer.source_family_id
                or offer.source_family_id != offer.source_authority.source_family_id
                or offer.source_seed != offer.source_authority.seed
                or offer.source_each != offer.source_authority.each
                or cap != offer.capability_id or cap != offer.source_authority.capability_id
                or offer.release_sha256 != release.release_sha256
                or offer.accepted_manifest_sha256 != cache.accepted_manifest_sha256
                or offer.generation_binding != cache.generation_binding):
            _invalid('BAMF_PRIORITY_OFFER_IDENTITY_DRIFT')
        if _planning_hold(option, planning.selection):
            holds.append((option.stable_id, 'A09_PLANNING_UNAVAILABLE'))
            continue
        try:
            offer.require_qualified_current(source_context, parent)
        except ValueError:
            holds.append((option.stable_id, 'SOURCE_OFFER_HELD'))
            continue
        eligible.append(option)
    ranked = rank_attention_options(tuple(eligible),
        {option.stable_id: evidence[option.stable_id] for option in eligible}, frontier.snapshot)
    holds.extend(ranked.held)
    return QualifiedPriority(ranked, tuple((option.stable_id, by_id[option.stable_id])
        for option in eligible if option.stable_id in by_id), tuple(sorted(holds)))
