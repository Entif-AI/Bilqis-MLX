"""Teacher context for metadata-only ordinary priority selection."""
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.learning_experiment import Settings
from bilqis_mlx.learning.salience_teacher import _teacher
from bilqis_mlx.learning.teacher_lineage import restore_teacher_lineage
from bilqis_mlx.runtime.accepted_teacher_custody import (
    _c03_projection,
    current_teacher_projection,
)
from .priority_frontier import LearningFirstPriorityFrontier


def _invalid(reason):
    ErrorBus.Raise(SCHOOL.BAMF_CURRICULUM.INVALID, reason=reason)


def learning_first_priority_context(
        run_dir, source_context, parent, cache, frontier, offers, school,
        learning_settings, lawful_frontier, legacy_receipt, adaptation, prior_region):
    if type(frontier) is not LearningFirstPriorityFrontier:
        _invalid('BAMF_PRIORITY_LEARNING_FIRST_FRONTIER_INVALID')
    projection = _c03_projection(
        parent, legacy_receipt=legacy_receipt,
        adaptation=adaptation, prior_region=prior_region)
    projection = current_teacher_projection(run_dir, parent, cache, projection)
    epoch = restore_teacher_lineage(projection.teacher_state)
    teacher = _teacher(epoch, school)
    if not isinstance(learning_settings, Settings):
        _invalid('BAMF_SALIENCE_CONTEXTUAL_SETTINGS_REQUIRED')
    by_id = dict(offers)
    if (len(by_id) != len(offers)
            or set(by_id) != {option.stable_id for option in frontier.options}
            or any(option.context.capability_id != option.stable_id
                   for option in frontier.options)):
        _invalid('BAMF_PRIORITY_LEARNING_FIRST_FRONTIER_INVALID')
    holds = [
        (item.capability_id, item.code.value)
        for item in lawful_frontier.exclusions
    ]
    return projection, epoch, teacher, by_id, holds


__all__ = ('learning_first_priority_context',)
