"""Metadata-only ordinary teaching priority."""
from dataclasses import dataclass

from bilqis_mlx.learning.atlas_salience import DispatchTier
from bilqis_mlx.learning.salience_contracts import ActionKind
from bilqis_mlx.semantics.domains import contract_digest


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


@dataclass(frozen=True)
class LearningFirstPriorityFrontier:
    options: tuple[LearningFirstPriorityOption, ...]
    evidence: tuple = ()


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
        rejection_count, rejection_positions):
    now = counter + rejection_count
    rejection_recency = {
        capability: counter + position
        for capability, position in rejection_positions.items()
    }
    ranked = []
    for stable_id, intent in offers:
        unlocks = planning_unlocks(stable_id, planning)
        tier = (DispatchTier.DOWNSTREAM_UNLOCK
                if unlocks > 0 else DispatchTier.FAIR_ROTATION)
        eligible_since = max(
            last_selected.get(stable_id, 0),
            rejection_recency.get(stable_id, 0))
        inputs_digest = contract_digest((
            "bilqis.bamf.learning-first-priority/v1", release_sha256,
            intent.accepted_manifest_sha256, intent.generation_binding,
            intent.source_binding_digest, stable_id, eligible_since,
            unlocks, int(tier)))
        option = LearningFirstPriorityOption(
            stable_id, LearningFirstPriorityContext(stable_id), eligible_since,
            unlocks, tier, inputs_digest)
        ranked.append((tier, eligible_since, stable_id, option))
    ranked.sort(key=lambda item: item[:3])
    return now, LearningFirstPriorityFrontier(tuple(item[3] for item in ranked))


__all__ = (
    'LearningFirstPriorityContext', 'LearningFirstPriorityOption',
    'LearningFirstPriorityFrontier', 'planning_unlocks',
    'learning_first_priority_frontier',
)
