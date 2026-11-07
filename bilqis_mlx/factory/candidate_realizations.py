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
    return (capability,), (symbol,)


def realized_source_sense_id(semantic_id):
    """Return the source sense owned by a trusted code realization."""
    if semantic_id == _COPULAR_ATLAS_SEMANTIC_ID:
        return _COPULAR_SOURCE_SENSE_ID
    capability = _EVENT_ATLAS_IDENTITIES.get(semantic_id)
    if capability is None:
        raise ValueError
    return ithkuil_events.SOURCE_SPECS[capability].sense_id


def prepare_realized_candidates(frontier, current, parent_graph, *,
                                source_root, source_registry, answer_registry):
    result = []
    available = {c.target_sense_id: c for c in frontier.candidates
                 if c.proposed_capability_id and
                 c.proposed_capability_id not in current.curriculum.capability_map}
    for sense_id, realization, capability in _realizations():
        if sense_id not in available:
            continue
        semantic_id = (_COPULAR_ATLAS_SEMANTIC_ID if realization is ithkuil_identity
                       else ithkuil_events.atlas_semantic_id(capability))
        try:
            project_realized_target(semantic_id, current)
        except ValueError:
            continue
        if realization is ithkuil_identity:
            graph = realization.expanded_graph(parent_graph)
            staged = realization.stage_identity(
                frontier, current, graph,
                source_root=source_root, source_registry=source_registry,
                answer_registry=answer_registry,
            )
        else:
            prerequisites = realization.SOURCE_SPECS[capability].prerequisites
            if any(item not in current.curriculum.capability_map for item in prerequisites):
                continue
            staged = realization.stage_capability(
                frontier, current, parent_graph, capability,
                source_root=source_root, source_registry=source_registry,
                answer_registry=answer_registry,
            )
            graph = realization.projected_graph(parent_graph, (capability,))
        staged.successor.verify_semantic_catalog(graph)
        result.append(staged)
    return tuple(result)


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
