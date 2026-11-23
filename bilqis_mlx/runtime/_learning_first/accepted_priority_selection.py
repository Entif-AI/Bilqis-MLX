"""Ordinary metadata-ranked priority selection and selected-source materialization."""

from bilqis_mlx.runtime.atlas_memory_retry import OOM_EXHAUSTED
from bilqis_mlx.runtime.priority_source_offer import materialize_priority_source_intent
from bilqis_mlx.runtime.priority_qualification import _grade, _planning_hold

from .accepted_priority_context import learning_first_priority_context


def select_learning_first_priority_visit(
        run_dir, source_context, parent, cache, frontier, offers, school,
        learning_settings, lawful_frontier, legacy_receipt, adaptation, prior_region,
        cadence_ids, planning, resource_holds, program, selected_source_each,
        engine, rng, total_capabilities, plasticity_escape, cadence_authorization,
        cadence_metadata, planning_offer_fanout_wall_seconds, *,
        invalid, selected_result, issue_result):
    projection, epoch, teacher, by_id, holds = learning_first_priority_context(
        run_dir, source_context, parent, cache, frontier, offers, school,
        learning_settings, lawful_frontier, legacy_receipt, adaptation, prior_region)
    if cadence_ids is not None and not set(by_id) <= set(cadence_ids):
        invalid('BAMF_ACTIVE_GRADE_CADENCE_OFFER_DRIFT')
    for option in frontier.options:
        if _planning_hold(option, planning.selection):
            holds.append((option.stable_id, 'A09_PLANNING_UNAVAILABLE'))
            continue
        if option.context.capability_id in resource_holds:
            holds.append((option.stable_id, OOM_EXHAUSTED))
            continue
        grade = _grade(program, school, option.context.capability_id)
        if grade is None:
            invalid('BAMF_PRIORITY_PROGRAM_INVALID')
        planning_offer = by_id[option.stable_id]
        try:
            offer = materialize_priority_source_intent(
                planning_offer, source_context, parent,
                source_each=(planning_offer.source_each
                             if selected_source_each is None
                             else selected_source_each))
        except ValueError:
            holds.append((option.stable_id, 'SOURCE_OFFER_HELD'))
            continue
        priority_features = {
            'schema': 'bilqis.bamf.learning-first-priority-features/v1',
            'known': [False, False, False],
        }
        return selected_result(
            run_dir, source_context, parent, cache, projection, epoch, teacher,
            option.dispatch_tier, option, offer, school, engine, rng,
            learning_settings, program, grade, None, holds, lawful_frontier,
            total_capabilities, plasticity_escape, priority_features,
            cadence_authorization, planning_offer, None, None)
    return issue_result(
        'NO_ADMISSIBLE_TEACHING', None, None, None, None, cadence_metadata,
        None, sorted(holds), run_dir, lawful_frontier,
        cadence_authorization=cadence_authorization)


__all__ = ('select_learning_first_priority_visit',)
