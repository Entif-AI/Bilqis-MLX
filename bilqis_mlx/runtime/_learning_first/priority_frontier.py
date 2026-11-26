"""Metadata-only ordinary teaching priority."""
from dataclasses import dataclass
from pathlib import Path

from bilqis_mlx.learning.atlas_salience import DispatchTier
from bilqis_mlx.learning.salience_contracts import ActionKind
from bilqis_mlx.runtime.priority_competence import (
    CapabilityCompetence, UNKNOWN_COMPETENCE,
)


@dataclass(frozen=True)
class LearningFirstPriorityContext:
    capability_id: str
    scope: str = "factory/foundation"


@dataclass(frozen=True)
class LearningFirstPriorityOption:
    stable_id: str
    context: LearningFirstPriorityContext
    eligible_since: int
    downstream_unlocks: int
    dispatch_tier: DispatchTier
    salience_inputs_digest: str
    action_kind: ActionKind = ActionKind.TEACHING
    competence: CapabilityCompetence = UNKNOWN_COMPETENCE


@dataclass(frozen=True)
class LearningFirstPriorityFrontier:
    options: tuple[LearningFirstPriorityOption, ...]
    evidence: tuple = ()




def can_reuse_learning_first_phase_authority(run_dir, frontier) -> bool:
    """Reuse phase-start legality while the current cadence still has a move.

    A retained learner publication changes accepted model/optimizer identity, but it
    does not change the active generated-grade/source topology.  The persisted
    cadence journal is the authority for which phase members were already attempted.
    Once that phase is exhausted we force a fresh learner-relative frontier so
    completion and recovery ranking can observe the new learner.
    """
    if frontier is None:
        return False
    from bilqis_mlx.runtime.active_grade_cadence_custody import read_current_cadence
    state = read_current_cadence(Path(run_dir))
    if state is None:
        return False
    if (state.active_grade_activation_sha256
            != frontier.active_grade_activation_sha256
            or state.active_grade_definition_sha256
            != frontier.active_grade_definition_sha256):
        return False
    attempted = set(state.attempted_capability_ids)
    complete = {
        item.capability_id for item in frontier.capabilities
        if getattr(item.disposition, "value", item.disposition) == "EVIDENCE_COMPLETE"
    }
    ready = set(frontier.ready_capability_ids)
    return any(
        capability in ready
        and capability not in attempted
        and capability not in complete
        for capability in state.phase_capability_ids
    )

def planning_unlocks(capability_id, planning):
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


def learning_first_priority_frontier(
        release_sha256, offers, planning, counter, last_selected,
        rejection_count, rejection_positions, *, competence=None):
    now = counter + rejection_count
    rejection_recency = {
        capability: counter + position
        for capability, position in rejection_positions.items()
    }
    ranked = []
    competence = competence or {}
    for stable_id, intent in offers:
        unlocks = planning_unlocks(stable_id, planning)
        tier = (DispatchTier.DOWNSTREAM_UNLOCK
                if unlocks > 0 else DispatchTier.FAIR_ROTATION)
        eligible_since = max(
            last_selected.get(stable_id, 0),
            rejection_recency.get(stable_id, 0))
        option = LearningFirstPriorityOption(
            stable_id, LearningFirstPriorityContext(stable_id), eligible_since,
            unlocks, tier, "", competence=competence.get(
                stable_id, UNKNOWN_COMPETENCE))
        ranked.append((option.competence.priority, tier, eligible_since,
                       stable_id, option))
    ranked.sort(key=lambda item: item[:-1])
    return now, LearningFirstPriorityFrontier(tuple(item[-1] for item in ranked))


__all__ = (
    'LearningFirstPriorityContext', 'LearningFirstPriorityOption',
    'LearningFirstPriorityFrontier', 'can_reuse_learning_first_phase_authority',
    'planning_unlocks',
    'learning_first_priority_frontier',
)
