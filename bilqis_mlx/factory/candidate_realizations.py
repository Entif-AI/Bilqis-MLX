"""Code-owned source realizations that can supply ordinary factory successors."""

from ..source_adapters import copular_curriculum as ithkuil_identity


def _realizations(_copular=ithkuil_identity):
    """Return trusted import-bound realizations, never a caller-rebindable registry."""
    return ((_copular.SENSE_ID, _copular),)


def _realization(semantic_id):
    matches = tuple(provider for key, provider in _realizations() if key == semantic_id)
    if len(matches) != 1:
        raise ValueError
    return matches[0]


def project_realized_target(
        semantic_id, current, *,
        _semantic_id=ithkuil_identity.SENSE_ID,
        _capability=ithkuil_identity.CAPABILITY,
        _projected_catalog=ithkuil_identity.projected_catalog):
    """Return the code-owned executable capability and catalog append for a target."""
    if semantic_id != _semantic_id:
        raise ValueError
    current.verify()
    if _capability in current.execution_plan.capability_map:
        raise ValueError
    projected = _projected_catalog(current.semantic_catalog)
    if (projected[:len(current.semantic_catalog)] != current.semantic_catalog
            or len(projected) <= len(current.semantic_catalog)):
        raise ValueError
    return (_capability,), projected[len(current.semantic_catalog):]


def prepare_realized_candidates(frontier, current, parent_graph, *,
                                source_root, source_registry, answer_registry):
    result = []
    available = {c.target_sense_id: c for c in frontier.candidates
                 if c.proposed_capability_id and
                 c.proposed_capability_id not in current.curriculum.capability_map}
    for sense_id, realization in _realizations():
        if sense_id not in available:
            continue
        graph = realization.expanded_graph(parent_graph)
        staged = realization.stage_identity(frontier, current, graph,
            source_root=source_root, source_registry=source_registry,
            answer_registry=answer_registry)
        staged.successor.verify_semantic_catalog(graph)
        result.append(staged)
    return tuple(result)


def admitted_candidate_graph(staged, parent_graph):
    try:
        realization = _realization(staged.source_sense_id)
    except ValueError as exc:
        raise ValueError("JIT_CANDIDATE_NATIVE_CATALOG_REQUIRED") from exc
    graph = realization.expanded_graph(parent_graph)
    staged.successor.verify_semantic_catalog(graph)
    return graph
