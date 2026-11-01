"""Code-owned source realizations that can supply ordinary factory successors."""
from types import MappingProxyType

from ..source_adapters import copular_curriculum as ithkuil_identity


# Entries carry source meaning, not grade scheduling authority. Frontier and
# factory checks still govern scope; JIT still governs learner readiness.
REALIZATIONS = MappingProxyType({ithkuil_identity.SENSE_ID: ithkuil_identity})


def project_realized_target(semantic_id, current):
    """Return the code-owned executable capability and catalog append for a target."""
    realization = REALIZATIONS.get(semantic_id)
    if realization is None:
        raise ValueError
    current.verify()
    capability = realization.CAPABILITY
    if capability in current.execution_plan.capability_map:
        raise ValueError
    projected = realization.projected_catalog(current.semantic_catalog)
    if (projected[:len(current.semantic_catalog)] != current.semantic_catalog
            or len(projected) <= len(current.semantic_catalog)):
        raise ValueError
    return (capability,), projected[len(current.semantic_catalog):]


def prepare_realized_candidates(frontier, current, parent_graph, *,
                                source_root, source_registry, answer_registry):
    result = []
    available = {c.target_sense_id: c for c in frontier.candidates
                 if c.proposed_capability_id and
                 c.proposed_capability_id not in current.curriculum.capability_map}
    for sense_id, realization in REALIZATIONS.items():
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
    realization = REALIZATIONS.get(staged.source_sense_id)
    if realization is None:
        raise ValueError("JIT_CANDIDATE_NATIVE_CATALOG_REQUIRED")
    graph = realization.expanded_graph(parent_graph)
    staged.successor.verify_semantic_catalog(graph)
    return graph
