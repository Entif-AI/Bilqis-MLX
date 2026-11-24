"""Accepted C03 priority selection and one Factory candidate execution."""
from dataclasses import replace
from bilqis_mlx.errors import ErrorBus, SCHOOL
import json
from pathlib import Path
import time
from bilqis_mlx.learning._atlas_candidate.identity_binding import (
    candidate_identity_for_canonical_consumer,
)
from bilqis_mlx.learning.atlas_salience import salience_priority_features
from bilqis_mlx.learning.salience_contracts import ActionKind
from bilqis_mlx.learning.salience_teacher import _teacher
from bilqis_mlx.learning.learning_experiment import Settings
from bilqis_mlx.learning.teacher_lineage import restore_teacher_lineage
from bilqis_mlx.learning.teacher_visit_identity import (
    derive_teacher_visit_identity, record_teacher_visit_authority,
    record_teacher_visit_identity,
)
from bilqis_mlx.runtime.atlas_memory_retry import OOM_EXHAUSTED
from bilqis_mlx.runtime._learning_first.accepted_priority_selection import (
    select_learning_first_priority_visit,
)
from bilqis_mlx.runtime.priority_source_offer import (
    PrioritySourceIntent, expand_selected_priority_source_offer,
    materialize_priority_source_intent,
)
from bilqis_mlx.runtime.teacher_policy_selection import select_visit_policy
from bilqis_mlx.runtime.priority_lesson import (
    LessonShapeUnavailable, prepare_lesson_pool, shape_priority_lesson,
)
from bilqis_mlx.semantics.domains import contract_digest
from .accepted_teacher_custody import (
    _accepted_parent, _c03_projection, _issue_bound_visit, _require_current_visit,
    _selection_projection, current_teacher_projection,
)
from .priority_qualification import _grade, _planning_hold, requalify_priority
from bilqis_mlx.runtime.outcomes.issuance import context_for_selection
from .accepted_priority_candidate import (
    execute_accepted_priority_candidate,
    prepare_accepted_priority_candidate_visit,
)
from .accepted_priority_learning_first import execute_learning_first_priority_candidate
from .accepted_priority_visit_contracts import (
    PriorityVisitResult,
    _issue_result,
    accepted_priority_school,
)

def _invalid(reason):
    ErrorBus.Raise(SCHOOL.BAMF_CURRICULUM.INVALID, reason=reason)


def _action_required_hold_reason(action_kind):
    return ('CORRECTION_ACTION_REQUIRED'
            if action_kind == ActionKind.CORRECTION
            else 'PROCEDURE_REPAIR_ACTION_REQUIRED')

def _selected_priority_result(
        run_dir, source_context, parent, cache, projection, epoch, teacher,
        dispatch_tier, option, offer, school, engine, rng, learning_settings,
        program, grade, salience_evidence, holds, lawful_frontier, total_capabilities,
        plasticity_escape, priority_features, cadence_authorization,
        planning_offer, source_materialization_wall_seconds,
        planning_offer_fanout_wall_seconds):
    capability = option.context.capability_id
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_mode_enabled,
    )
    strict = strict_mode_enabled()
    pool_started = time.monotonic() if strict else None
    lesson_pool = prepare_lesson_pool(source_context, offer)
    pool_wall = time.monotonic() - pool_started if strict else 0.0
    prepared_context = None
    if strict:
        diagnostics = {'teacher_epoch_digest': contract_digest(epoch)}
    else:
        from bilqis_mlx.runtime.structural_weakness_replay import recorded_weakness_debt
        from bilqis_mlx.runtime.teacher_policy_selection import ordinary_previsit_diagnostics
        from bilqis_mlx.runtime.outcomes.issuance import selection_context
        prepared_context = selection_context(
            source_context.release, program, grade, school.stage,
            option.context.scope, {}, capability)
        debt = recorded_weakness_debt(
            teacher, prepared_context, lawful_frontier, capability)
        diagnostics = ordinary_previsit_diagnostics(option, structural_debt=debt)
    if salience_evidence is not None:
        diagnostics['salience_evidence'] = salience_evidence
    key, policy, metadata = select_visit_policy(
        engine, teacher, capability, school, rng, learning_settings,
        option.context.scope, diagnostics,
        grade, total_capabilities=total_capabilities,
        plasticity_escape=plasticity_escape)
    shape_started = time.monotonic() if strict else None
    offer, primary_lesson = shape_priority_lesson(
        source_context, parent, offer, lesson_pool, policy)
    if strict and source_materialization_wall_seconds is not None:
        source_materialization_wall_seconds += pool_wall + time.monotonic() - shape_started
    metadata = {**metadata, 'primary_lesson': primary_lesson}
    metadata = {**metadata, 'how_context': context_for_selection(
        source_context.release, program, grade, school, option, teacher, metadata,
        total_capabilities, **({} if strict else {"prepared_context": prepared_context}))}
    if cadence_authorization is not None:
        metadata = {**metadata, 'cadence': cadence_authorization.to_record()}
    selected_epoch = replace(
        epoch, current_json=json.dumps(teacher, sort_keys=True, allow_nan=False))
    selected = _selection_projection(projection, selected_epoch)
    identity = derive_teacher_visit_identity(
        selected.teacher_state,
        run_identity_sha256=parent.run_identity.digest,
        run_seed=parent.run_identity.run_seed,
        generation=parent.generation,
        accepted_manifest_sha256=cache.accepted_manifest_sha256,
        capability_id=capability,
        policy_key=key)
    recorded = record_teacher_visit_identity(selected.teacher_state, identity)
    ranking_evidence = None
    if strict:
        planning_authority = getattr(planning_offer, 'source_authority', None)
        planning_receipt = getattr(planning_authority, 'content_sha256', None)
        ranking_evidence = {
            **priority_features,
            'dispatch_tier': int(dispatch_tier),
            'eligible_since': option.eligible_since,
            'downstream_unlocks': option.downstream_unlocks,
            'stable_id': option.stable_id,
            'salience_inputs_digest': option.salience_inputs_digest,
            'planning_source_receipt_sha256': planning_receipt,
            'planning_source_each': planning_offer.source_each,
            'selected_source_receipt_sha256': offer.source_authority.content_sha256,
            'selected_source_each': offer.source_each,
        }
    recorded = record_teacher_visit_authority(recorded, identity)
    visit = _issue_bound_visit(recorded, identity)
    return _issue_result(
        'TEACHER_SELECTED', option.stable_id, offer, visit, policy,
        metadata, grade, sorted(holds), run_dir, lawful_frontier,
        ranking_evidence=ranking_evidence,
        source_materialization_wall_seconds=source_materialization_wall_seconds,
        planning_offer_fanout_wall_seconds=planning_offer_fanout_wall_seconds,
        cadence_authorization=cadence_authorization)


def _accepted_context(run_dir, source_context, school, lawful_frontier,
                      accepted_parent, planning_generation):
    if planning_generation is None:
        parent, cache = _accepted_parent(Path(run_dir))
        expected = candidate_identity_for_canonical_consumer(parent.retained_state)
    else:
        from bilqis_mlx.runtime.priority_source_offer import (
            _require_planning_generation, _require_planning_generation_identity,
        )
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
            strict_mode_enabled,
        )
        parent = accepted_parent
        require_generation = (
            _require_planning_generation
            if strict_mode_enabled() else _require_planning_generation_identity)
        cache, _authenticated = require_generation(
            planning_generation, source_context, parent)
        if getattr(lawful_frontier, '_planning_generation', None) is not planning_generation:
            if strict_mode_enabled():
                _invalid('BAMF_PRIORITY_LAWFUL_FRONTIER_BINDING_DRIFT')
            from bilqis_mlx.runtime._learning_first.priority_frontier import (
                can_reuse_learning_first_phase_authority,
            )
            if (getattr(lawful_frontier, 'admitted_release_sha256', None)
                    != source_context.release.release_sha256
                    or not can_reuse_learning_first_phase_authority(
                        run_dir, lawful_frontier)):
                _invalid('BAMF_PRIORITY_LAWFUL_FRONTIER_BINDING_DRIFT')
        expected = planning_generation.parent_candidate_identity_sha256
    if getattr(getattr(school, 'current_student', None), 'sha256', None) != expected:
        _invalid('BAMF_PRIORITY_STUDENT_DRIFT')
    return parent, cache


def _cadence_context(cadence_authorization, lawful_frontier):
    if cadence_authorization is None:
        return None, None
    from bilqis_mlx.runtime.active_grade_cadence_contracts import (
        ActiveGradeCadenceAuthorization,
    )
    if not isinstance(cadence_authorization, ActiveGradeCadenceAuthorization):
        _invalid('BAMF_ACTIVE_GRADE_CADENCE_AUTHORITY_INVALID')
    cadence_ids = tuple(cadence_authorization.authorized_capability_ids)
    if not set(cadence_ids) <= set(lawful_frontier.ready_capability_ids):
        _invalid('BAMF_ACTIVE_GRADE_CADENCE_AUTHORITY_DRIFT')
    return cadence_ids, {'cadence': cadence_authorization.to_record()}


def _empty_priority_result(run_dir, source_context, parent, frontier, history,
                           lawful_frontier, cadence_authorization,
                           cadence_ids, cadence_metadata):
    from bilqis_mlx.runtime.lawful_teaching_frontier import (
        require_bound_lawful_teaching_frontier,
    )
    require_bound_lawful_teaching_frontier(lawful_frontier, source_context, parent)
    if (frontier is not None or history is not None
            or (lawful_frontier.ready_capability_ids and cadence_ids is None)
            or cadence_ids):
        _invalid('BAMF_PRIORITY_EMPTY_AUTHORITY_DRIFT')
    holds = sorted(
        (item.capability_id, item.code.value) for item in lawful_frontier.exclusions)
    if cadence_authorization is not None:
        disposition = cadence_authorization.disposition.value
        if disposition != 'TEACHING':
            holds.append(('__active_grade__', 'CADENCE_' + disposition))
    return _issue_result(
        'NO_ADMISSIBLE_TEACHING', None, None, None, None, cadence_metadata, None,
        holds, run_dir, lawful_frontier,
        cadence_authorization=cadence_authorization)


def _qualified_priority_context(
        run_dir, source_context, parent, cache, frontier, history, planning,
        offers, program, school, learning_settings, lawful_frontier,
        planning_generation, now, legacy_receipt, adaptation, prior_region):
    projection = _c03_projection(
        parent, legacy_receipt=legacy_receipt,
        adaptation=adaptation, prior_region=prior_region)
    projection = current_teacher_projection(run_dir, parent, cache, projection)
    epoch = restore_teacher_lineage(projection.teacher_state)
    teacher = _teacher(epoch, school)
    if not isinstance(learning_settings, Settings):
        _invalid('BAMF_SALIENCE_CONTEXTUAL_SETTINGS_REQUIRED')
    qualified = requalify_priority(
        run_dir, source_context, parent, frontier, history, planning, offers,
        program, school, epoch, now=now, lawful_frontier=lawful_frontier,
        planning_generation=planning_generation)
    holds = [
        (item.capability_id, item.code.value)
        for item in lawful_frontier.exclusions
    ]
    holds.extend(qualified.holds)
    return (
        projection, epoch, teacher, qualified,
        dict(qualified.offers), dict(frontier.evidence), holds,
    )


def _select_strict_priority_visit(
        run_dir, source_context, parent, cache, frontier, history, planning, offers,
        engine, school, rng, learning_settings, program, now, lawful_frontier,
        cadence_authorization, cadence_ids, cadence_metadata, selected_source_each,
        planning_offer_fanout_wall_seconds, total_capabilities, plasticity_escape,
        legacy_receipt, adaptation, prior_region, planning_generation, resource_holds):
    (projection, epoch, teacher, qualified, by_id, evidence, holds) = (
        _qualified_priority_context(
            run_dir, source_context, parent, cache, frontier, history, planning,
            offers, program, school, learning_settings, lawful_frontier,
            planning_generation, now, legacy_receipt, adaptation, prior_region))
    if cadence_ids is not None and not set(dict(qualified.offers)) <= set(cadence_ids):
        _invalid('BAMF_ACTIVE_GRADE_CADENCE_OFFER_DRIFT')
    action_required_option_id = None
    for option in qualified.ranked.ordered:
        priority_features = salience_priority_features(
            evidence[option.stable_id], option.context.capability_id,
            option.context.scope, contract_digest(epoch))
        if option.action_kind in (ActionKind.CORRECTION, ActionKind.PROCEDURE_REPAIR):
            holds.append((option.stable_id, _action_required_hold_reason(option.action_kind)))
            if action_required_option_id is None:
                action_required_option_id = option.stable_id
            continue
        if option.context.capability_id in resource_holds:
            holds.append((option.stable_id, OOM_EXHAUSTED))
            continue
        planning_offer = by_id[option.stable_id]
        offer = planning_offer
        materialization_started = time.perf_counter()
        try:
            offer.require_current(source_context, parent)
        except ValueError:
            holds.append((option.stable_id, 'SOURCE_OFFER_HELD'))
            continue
        grade = _grade(program, school, option.context.capability_id)
        if grade is None:
            _invalid('BAMF_PRIORITY_PROGRAM_INVALID')
        if type(planning_offer) is PrioritySourceIntent:
            try:
                offer = materialize_priority_source_intent(
                    planning_offer, source_context, parent,
                    source_each=(planning_offer.source_each
                                 if selected_source_each is None
                                 else selected_source_each))
            except ValueError:
                holds.append((option.stable_id, 'SOURCE_OFFER_HELD'))
                continue
        elif selected_source_each is not None:
            try:
                offer = expand_selected_priority_source_offer(
                    planning_offer, source_context, parent,
                    source_each=selected_source_each)
            except ValueError:
                holds.append((option.stable_id, 'SOURCE_OFFER_HELD'))
                continue
        materialization_wall = max(
            0.0, time.perf_counter() - materialization_started)
        try:
            return _selected_priority_result(
                run_dir, source_context, parent, cache, projection, epoch, teacher,
                dict(qualified.ranked.tiers)[option.stable_id], option, offer, school,
                engine, rng, learning_settings, program, grade,
                evidence[option.stable_id], holds, lawful_frontier, total_capabilities,
                plasticity_escape, priority_features, cadence_authorization,
                planning_offer, materialization_wall,
                planning_offer_fanout_wall_seconds)
        except LessonShapeUnavailable:
            holds.append((option.stable_id, 'SOURCE_LESSON_HELD'))
            continue
    if action_required_option_id is not None:
        return _issue_result(
            'ACTION_REQUIRED', action_required_option_id, None, None, None,
            cadence_metadata, None, sorted(holds), run_dir, lawful_frontier,
            cadence_authorization=cadence_authorization)
    return _issue_result(
        'NO_ADMISSIBLE_TEACHING', None, None, None, None, cadence_metadata,
        None, sorted(holds), run_dir, lawful_frontier,
        cadence_authorization=cadence_authorization)


def select_accepted_priority_visit(
        run_dir, source_context, frontier, history, planning, offers,
        engine, school, rng, learning_settings, *, program, now,
        lawful_frontier,
        cadence_authorization=None,
        selected_source_each=None,
        planning_offer_fanout_wall_seconds=None,
        total_capabilities=None, plasticity_escape=None,
        legacy_receipt=None, adaptation=None, prior_region=None,
        accepted_parent=None, planning_generation=None, resource_holds=frozenset()):
    parent, cache = _accepted_context(
        run_dir, source_context, school, lawful_frontier,
        accepted_parent, planning_generation)
    cadence_ids, cadence_metadata = _cadence_context(
        cadence_authorization, lawful_frontier)
    if not offers and frontier is None:
        return _empty_priority_result(
            run_dir, source_context, parent, frontier, history, lawful_frontier,
            cadence_authorization, cadence_ids, cadence_metadata)
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_mode_enabled,
    )
    strict = strict_mode_enabled()
    if not strict:
        return select_learning_first_priority_visit(
            run_dir, source_context, parent, cache, frontier, offers, school,
            learning_settings, lawful_frontier, legacy_receipt, adaptation, prior_region,
            cadence_ids, planning, resource_holds, program, selected_source_each,
            engine, rng, total_capabilities, plasticity_escape, cadence_authorization,
            cadence_metadata, planning_offer_fanout_wall_seconds,
            invalid=_invalid, selected_result=_selected_priority_result,
            issue_result=_issue_result)
    return _select_strict_priority_visit(
        run_dir, source_context, parent, cache, frontier, history, planning, offers,
        engine, school, rng, learning_settings, program, now, lawful_frontier,
        cadence_authorization, cadence_ids, cadence_metadata, selected_source_each,
        planning_offer_fanout_wall_seconds, total_capabilities, plasticity_escape,
        legacy_receipt, adaptation, prior_region, planning_generation, resource_holds)

