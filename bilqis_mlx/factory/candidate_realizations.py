"""Code-owned source realizations that can supply ordinary factory successors."""

from ..source_adapters import copular_curriculum as ithkuil_identity
from ..source_adapters import event_frames as ithkuil_events


_COPULAR_ATLAS_SEMANTIC_ID = ithkuil_identity.atlas_semantic_id()
_COPULAR_SOURCE_SENSE_ID = ithkuil_identity.SENSE_ID
_COPULAR_CAPABILITY = ithkuil_identity.CAPABILITY
_COPULAR_REGISTERED_TOKENS = ithkuil_identity.PROJECTION_REGISTERED_TOKENS
_COPULAR_ADMISSION_TOKEN = ithkuil_identity.PROJECTION_ADMISSION_TOKEN
_EVENT_ATLAS_IDENTITIES = {
    ithkuil_events.atlas_semantic_id(capability): capability
    for capability in ithkuil_events.SOURCE_SPECS
}


def _realizations(_copular=ithkuil_identity):
    """Return trusted import-bound realizations, never a caller-rebindable registry."""
    return (
        (_COPULAR_SOURCE_SENSE_ID, _copular, _COPULAR_CAPABILITY),
        *((spec.sense_id, ithkuil_events, capability)
          for capability, spec in ithkuil_events.SOURCE_SPECS.items()),
    )


def _realization(semantic_id):
    matches = tuple((provider, capability)
                    for key, provider, capability in _realizations()
                    if key == semantic_id)
    if len(matches) != 1:
        raise ValueError
    return matches[0]


def project_realized_target(
        semantic_id, current, *,
        _semantic_id=_COPULAR_ATLAS_SEMANTIC_ID,
        _capability=_COPULAR_CAPABILITY,
        _registered_tokens=_COPULAR_REGISTERED_TOKENS,
        _admission_token=_COPULAR_ADMISSION_TOKEN):
    """Return the code-owned executable capability and catalog append for a target."""
    current.verify()
    if semantic_id == _semantic_id:
        if _capability in current.execution_plan.capability_map:
            raise ValueError
        if _admission_token in current.semantic_catalog:
            prefix = (*_registered_tokens, _admission_token)
            if current.semantic_catalog[:len(prefix)] != prefix:
                raise ValueError
            return (_capability,), ()
        if (len(current.semantic_catalog) > len(_registered_tokens)
                or current.semantic_catalog
                   != _registered_tokens[:len(current.semantic_catalog)]
                or _admission_token in _registered_tokens):
            raise ValueError
        projected = (*_registered_tokens, _admission_token)
        return (_capability,), projected[len(current.semantic_catalog):]

    capability = _EVENT_ATLAS_IDENTITIES.get(semantic_id)
    if capability is None or capability in current.execution_plan.capability_map:
        raise ValueError
    spec = ithkuil_events.SOURCE_SPECS[capability]
    if any(prerequisite not in current.curriculum.capability_map
           for prerequisite in spec.prerequisites):
        raise ValueError
    symbol = ithkuil_events.SYMBOLS[capability]
    if symbol in current.semantic_catalog:
        raise ValueError
    required_symbols = tuple(
        ithkuil_events.SYMBOLS[item]
        for item in spec.prerequisites if item in ithkuil_events.SYMBOLS
    )
    if any(item not in current.semantic_catalog for item in required_symbols):
        raise ValueError
    reserved = ()
    if _COPULAR_ADMISSION_TOKEN not in current.semantic_catalog:
        _, reserved = project_realized_target(_COPULAR_ATLAS_SEMANTIC_ID, current)
    return (capability,), (*reserved, symbol)


def realized_source_sense_id(semantic_id):
    """Return the source sense owned by a trusted code realization."""
    if semantic_id == _COPULAR_ATLAS_SEMANTIC_ID:
        return _COPULAR_SOURCE_SENSE_ID
    capability = _EVENT_ATLAS_IDENTITIES.get(semantic_id)
    if capability is None:
        raise ValueError
    return ithkuil_events.SOURCE_SPECS[capability].sense_id


def prepare_realized_candidate(
        frontier, current, parent_graph, semantic_id, *,
        source_root, source_registry, answer_registry):
    """Stage one explicitly selected code-owned realization without admission."""
    project_realized_target(semantic_id, current)
    if semantic_id == _COPULAR_ATLAS_SEMANTIC_ID:
        realization, capability = ithkuil_identity, _COPULAR_CAPABILITY
        graph = (
            parent_graph
            if _COPULAR_ADMISSION_TOKEN in current.semantic_catalog
            else realization.expanded_graph(parent_graph)
        )
        staged = realization.stage_identity(
            frontier, current, graph,
            source_root=source_root, source_registry=source_registry,
            answer_registry=answer_registry,
        )
    else:
        capability = _EVENT_ATLAS_IDENTITIES.get(semantic_id)
        if capability is None:
            raise ValueError
        realization = ithkuil_events
        staged = realization.stage_capability(
            frontier, current, parent_graph, capability,
            source_root=source_root, source_registry=source_registry,
            answer_registry=answer_registry,
        )
        graph = realization.projected_graph(parent_graph, (capability,))
    staged.successor.verify_semantic_catalog(graph)
    return staged


def project_authoritative_target(semantic_id, current, selected_obligations):
    """Derive one A09 projection from the code-owned realization authority."""
    from dataclasses import replace
    from .atlas_frontier_selection_validation import (
        TargetDeltaProjection, catalog_digest, obligation_signature,
    )

    capabilities, identities = project_realized_target(semantic_id, current)
    provisional = TargetDeltaProjection(
        semantic_id=semantic_id,
        obligation_signature=obligation_signature(selected_obligations),
        current_release_sha256=current.release_sha256,
        current_semantic_catalog_sha256=current.semantic_catalog_sha256,
        added_capability_ids=capabilities,
        introduced_semantic_ids=identities,
        projected_semantic_catalog_sha256=catalog_digest(
            current.semantic_catalog + identities),
        projection_sha256="0" * 64,
    )
    return replace(
        provisional, projection_sha256=provisional.expected_digest())


def prepare_realized_candidates(frontier, current, parent_graph, *,
                                source_root, source_registry, answer_registry):
    """Preserve the legacy ambient boundary: only its historical copular candidate."""
    available = {
        candidate.target_sense_id
        for candidate in frontier.candidates
        if candidate.proposed_capability_id
        and candidate.proposed_capability_id not in current.curriculum.capability_map
    }
    if _COPULAR_SOURCE_SENSE_ID not in available:
        return ()
    try:
        project_realized_target(_COPULAR_ATLAS_SEMANTIC_ID, current)
    except ValueError:
        return ()
    return (prepare_realized_candidate(
        frontier, current, parent_graph, _COPULAR_ATLAS_SEMANTIC_ID,
        source_root=source_root, source_registry=source_registry,
        answer_registry=answer_registry,
    ),)


def admitted_candidate_graph(staged, parent_graph):
    try:
        realization, capability = _realization(staged.source_sense_id)
    except ValueError as exc:
        raise ValueError("JIT_CANDIDATE_NATIVE_CATALOG_REQUIRED") from exc
    graph = (realization.expanded_graph(parent_graph)
             if realization is ithkuil_identity
             else realization.projected_graph(parent_graph, (capability,)))
    staged.successor.verify_semantic_catalog(graph)
    return graph
