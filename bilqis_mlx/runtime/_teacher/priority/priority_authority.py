"""Production C06 authority for ordinary grade-neutral BAMF teaching priority."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import time

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.salience_teacher import AttentionFrontier
from bilqis_mlx.learning.teacher_lineage import priority_rotation_state
from bilqis_mlx.runtime._learning_first.priority_frontier import (
    LearningFirstPriorityFrontier,
    learning_first_priority_frontier,
    planning_unlocks as _planning_unlocks,
)
from bilqis_mlx.runtime._learning_first.priority_salience import (
    priority_history as _priority_history,
    priority_options as _strict_priority_options,
)
from bilqis_mlx.runtime.priority_source_offer import (
    _require_planning_generation, _require_planning_generation_identity,
    bind_priority_planning_generation,
    plan_priority_source_intent, prepare_priority_source_offer,
)
from bilqis_mlx.runtime.logical_batch import BamfLogicalBatchContract
from bilqis_mlx.semantic_sampling import DEFAULT_BINARY_BALANCE
from bilqis_mlx.semantics.domains import contract_digest
from .priority_planning_owner import (
    build_priority_planning_epoch as _build_priority_planning_epoch,
    priority_planning as _priority_planning,
    priority_planning_from_epoch as _priority_planning_from_epoch,
)
from .priority_rejection_replay import (
    ordered_rejections as _ordered_rejections,
    rejection_recency as _rejection_recency,
)
from .priority_competence import priority_competence_snapshot

_priority_options = _strict_priority_options


_SCOPE = "factory/foundation"
_SOURCE_EACH = DEFAULT_BINARY_BALANCE.minimum_total


def _planning_source_each(logical_batch_size):
    """Resolve only the provider-valid row floor needed for C06 planning."""
    if logical_batch_size is None:
        return _SOURCE_EACH
    try:
        contract = BamfLogicalBatchContract(logical_batch_size)
    except ValueError:
        _invalid("BAMF_PRIORITY_LOGICAL_BATCH_INVALID")
    return contract.source_minimum_rows


def _invalid(reason):
    ErrorBus.Raise(SCHOOL.BAMF_CURRICULUM.INVALID, reason=reason)


@dataclass(frozen=True)
class AcceptedPriorityAuthority:
    frontier: object | None
    history: object | None
    planning: object
    lawful_frontier: object = field(compare=False, repr=False)
    lawful_frontier_sha256: str
    offers: tuple
    planning_offer_fanout_wall_seconds: float = field(compare=False, repr=False)
    now: int
    planning_generation: object
    cadence: object = field(compare=False, repr=False)
    selection_cadence: object = field(compare=False, repr=False)


def _offer_seed(next_seed: int, capability_id: str) -> int:
    raw = f"bilqis.bamf.c03.4-source-seed/v1|{next_seed}|{capability_id}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def _priority_offers(source_context, parent, atlas_artifact_path, next_seed,
                     planning_generation, lawful_frontier, authorized,
                     source_each=_SOURCE_EACH,
                     planning_cache=None):
    by_id = {
        capability.capability_id: capability
        for capability in source_context.release.execution_plan.capabilities
    }
    ready = tuple(lawful_frontier.ready_capability_ids)
    authorized = tuple(authorized)
    if (not set(authorized) <= set(ready)
            or any(capability_id not in by_id for capability_id in authorized)):
        _invalid("BAMF_PRIORITY_LAWFUL_FRONTIER_RELEASE_DRIFT")
    capabilities = tuple(by_id[capability_id] for capability_id in authorized)
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_mode_enabled,
    )
    prepare_offer = (
        prepare_priority_source_offer
        if strict_mode_enabled() else plan_priority_source_intent)
    def prepare(capability):
        kwargs = {
            "capability": capability.capability_id,
            "source_seed": _offer_seed(next_seed, capability.capability_id),
            "source_each": source_each,
            "planning_generation": planning_generation,
        }
        if planning_cache is not None:
            kwargs["materialization_cache"] = planning_cache.source_materialization_cache
        return prepare_offer(
            source_context, parent, atlas_artifact_path, **kwargs)

    return capabilities, tuple(
        (capability.capability_id, prepare(capability))
        for capability in capabilities)


def _planning_generation_for_epoch(
        source_context, parent, atlas_artifact_path, planning_cache):
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_mode_enabled,
    )
    strict = strict_mode_enabled()
    planning_generation = None
    learning_first_key = None
    authority_key = None
    if planning_cache is not None and not strict:
        host = getattr(source_context, '_accepted_runtime_host', None)
        accepted_cache = getattr(host, '_accepted_cache', None)
        authenticated = getattr(source_context, '_accepted_feature_context', None)
        receipt = getattr(authenticated, 'receipt', None)
        authority_key = (
            source_context.release.release_sha256,
            contract_digest(parent.correction_frontier),
            getattr(receipt, 'semantic_release', None),
            getattr(receipt, 'active_set_sha256', None),
            getattr(receipt, 'feature_sha256', None),
            getattr(receipt, 'compiler_sha256', None),
            getattr(receipt, 'implementation_sha256', None),
            getattr(receipt, 'source_atlas_bundle_id', None),
            getattr(receipt, 'source_release_sha256', None),
            getattr(receipt, 'source_source_bundle_id', None),
            str(atlas_artifact_path),
        )
        learning_first_key = (
            id(source_context), id(parent), id(accepted_cache),
            getattr(accepted_cache, 'accepted_manifest_sha256', None),
            getattr(accepted_cache, 'generation_binding', None),
            authority_key,
        )
        if (planning_cache._planning_generation_key == learning_first_key
                and planning_cache._planning_generation is not None):
            planning_cache.planning_generation_hits += 1
            planning_generation = planning_cache._planning_generation
        else:
            planning_cache.planning_generation_misses += 1
            planning_generation = bind_priority_planning_generation(
                source_context, parent, atlas_artifact_path)
            planning_cache._planning_generation_key = learning_first_key
            planning_cache._planning_generation = planning_generation
    if planning_generation is None:
        planning_generation = bind_priority_planning_generation(
            source_context, parent, atlas_artifact_path)
    require_generation = (
        _require_planning_generation if strict
        else _require_planning_generation_identity)
    cache, authenticated = require_generation(
        planning_generation, source_context, parent)
    return (
        planning_generation, cache, authenticated,
        learning_first_key, authority_key, strict)


def _bind_lawful_priority_epoch(
        run_dir, source_context, parent, atlas_artifact_path, progress,
        planning_cache=None):
    if progress is not None:
        progress("teacher: binding accepted planning generation")
    (planning_generation, cache, _authenticated, learning_first_key,
     authority_key, strict) = _planning_generation_for_epoch(
        source_context, parent, atlas_artifact_path, planning_cache)
    if (planning_cache is not None and not strict
            and planning_cache._learning_first_epoch_key != learning_first_key
            and getattr(planning_cache, '_learning_first_authority_key', None)
                == authority_key
            and planning_cache._learning_first_epoch is not None
            and planning_cache._learning_first_planning is not None
            and planning_cache._learning_first_lawful_frontier is not None):
        from bilqis_mlx.runtime._learning_first.priority_frontier import (
            can_reuse_learning_first_phase_authority,
        )
        if can_reuse_learning_first_phase_authority(
                run_dir, planning_cache._learning_first_lawful_frontier):
            from bilqis_mlx.runtime.lawful_teaching_frontier import (
                _issue_lawful_teaching_frontier_from_epoch,
            )
            lawful_frontier = _issue_lawful_teaching_frontier_from_epoch(
                planning_cache._learning_first_epoch, source_context, parent,
                planning_generation, planning_cache=planning_cache)
            planning_cache.learning_first_epoch_hits += 1
            planning_cache.learning_first_publication_reuses += 1
            planning_cache._learning_first_epoch_key = learning_first_key
            planning_cache._learning_first_lawful_frontier = lawful_frontier
            return (
                planning_generation, cache, planning_cache._learning_first_epoch,
                planning_cache._learning_first_planning,
                lawful_frontier,
            )
    if (planning_cache is not None and not strict
            and planning_cache._learning_first_epoch_key == learning_first_key
            and planning_cache._learning_first_epoch is not None
            and planning_cache._learning_first_planning is not None
            and planning_cache._learning_first_lawful_frontier is not None):
        planning_cache.learning_first_epoch_hits += 1
        return (
            planning_generation,
            cache,
            planning_cache._learning_first_epoch,
            planning_cache._learning_first_planning,
            planning_cache._learning_first_lawful_frontier,
        )
    if planning_cache is not None and not strict:
        planning_cache.learning_first_epoch_misses += 1
    from bilqis_mlx.runtime.lawful_teaching_frontier import (
        _issue_lawful_teaching_frontier_from_epoch,
    )
    planning_epoch = _build_priority_planning_epoch(
        run_dir, source_context, atlas_artifact_path, progress,
        authenticated_features=_authenticated, planning_cache=planning_cache,
        planning_generation=planning_generation)
    planning = _priority_planning_from_epoch(
        planning_epoch, progress=progress, planning_cache=planning_cache)
    lawful_frontier = _issue_lawful_teaching_frontier_from_epoch(
        planning_epoch, source_context, parent, planning_generation,
        planning_cache=planning_cache)
    if planning_cache is not None and not strict:
        planning_cache._learning_first_epoch_key = learning_first_key
        planning_cache._learning_first_authority_key = authority_key
        planning_cache._learning_first_epoch = planning_epoch
        planning_cache._learning_first_planning = planning
        planning_cache._learning_first_lawful_frontier = lawful_frontier
    return planning_generation, cache, planning_epoch, planning, lawful_frontier


def _announce_offer_fanout(progress, capabilities):
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_mode_enabled,
    )
    strict = strict_mode_enabled()
    if progress is not None:
        label = ("source-backed offers" if strict
                 else "metadata-only learning-first intents")
        progress(f"teacher: preparing {label} for {len(capabilities)} lawful capabilities")
    return strict


def issue_foundation_priority_authority(
        run_dir, source_context, parent, teacher_epoch, atlas_artifact_path, *,
        teacher_state, progress=None, planning_cache=None, logical_batch_size=None,
        program=None):
    """Issue only signed UNKNOWN salience; C06 ranking owns the resulting order."""
    from bilqis_mlx.runtime.bamf_bundle._darwin_salience_signer import (
        read_host_system_source_authority_signer,
    )
    next_seed = teacher_state.get("next_seed")
    if type(next_seed) is not int or next_seed < 0:
        _invalid("BAMF_PRIORITY_TEACHER_SEED_INVALID")
    counter, last_selected = priority_rotation_state(teacher_state)
    planning_generation, cache, planning_epoch, planning, lawful_frontier = (
        _bind_lawful_priority_epoch(
            run_dir, source_context, parent, atlas_artifact_path, progress,
            planning_cache=planning_cache))
    from bilqis_mlx.runtime.active_grade_cadence import issue_active_grade_cadence
    competence, rejection_snapshot = priority_competence_snapshot(
        run_dir, parent, cache, source_context.release, program,
        lawful_frontier.ready_capability_ids)
    cadence = issue_active_grade_cadence(
        run_dir, planning_epoch, lawful_frontier, competence=competence)
    selection_cadence = cadence
    ready_capabilities = cadence.authorized_capability_ids
    planning_source_each = _planning_source_each(logical_batch_size)
    if not ready_capabilities:
        return AcceptedPriorityAuthority(
            None, None, planning, lawful_frontier,
            lawful_frontier.frontier_sha256, (), 0.0,
            counter, planning_generation,
            cadence, selection_cadence)
    strict = _announce_offer_fanout(progress, ready_capabilities)
    offer_fanout_started = time.perf_counter() if strict else None
    capabilities, offers = _priority_offers(
        source_context, parent, atlas_artifact_path, next_seed,
        planning_generation, lawful_frontier, ready_capabilities,
        planning_source_each,
        planning_cache=planning_cache)
    planning_offer_fanout_wall_seconds = (
        max(0.0, time.perf_counter() - offer_fanout_started) if strict else None)
    if progress is not None:
        progress("teacher: ranking priority options")
    rejection_count, rejection_positions = (
        _rejection_recency(run_dir, parent, cache)
        if rejection_snapshot is None else rejection_snapshot[:2])
    option_ids = {capability for capability, _ in offers}
    rejection_positions = {
        capability: position
        for capability, position in rejection_positions.items()
        if capability in option_ids
    }
    if not strict:
        now, frontier = learning_first_priority_frontier(
            source_context.release.release_sha256, offers, planning,
            counter, last_selected, rejection_count, rejection_positions,
            competence=competence)
        return AcceptedPriorityAuthority(
            frontier, None, planning,
            lawful_frontier, lawful_frontier.frontier_sha256, offers,
            planning_offer_fanout_wall_seconds, now,
            planning_generation, cadence, selection_cadence)
    registry = cache._correction_registry
    signer = read_host_system_source_authority_signer(registry)
    rejections = tuple(
        item for item in _ordered_rejections(run_dir, parent, cache)
        if item[0] in option_ids)
    now, policy, snapshot, options, evidence_rows = _priority_options(
        parent, source_context.release.release_sha256, offers, teacher_epoch,
        counter, last_selected, rejection_count, rejection_positions,
        registry, signer, planning, scope=_SCOPE, planning_unlocks=_planning_unlocks)
    history = _priority_history(
        source_context, cache, signer, policy, evidence_rows, rejections, now)
    return AcceptedPriorityAuthority(
        AttentionFrontier(options, evidence_rows, snapshot),
        history, planning,
        lawful_frontier, lawful_frontier.frontier_sha256, offers,
        planning_offer_fanout_wall_seconds, now,
        planning_generation, cadence, selection_cadence)


__all__ = ("AcceptedPriorityAuthority", "issue_foundation_priority_authority")
