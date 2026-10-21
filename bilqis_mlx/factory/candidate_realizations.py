"""Code-owned source realizations that can supply ordinary factory successors."""
from types import MappingProxyType

from ..source_adapters import copular_curriculum as ithkuil_identity


# Entries carry source meaning, not grade scheduling authority. Frontier and
# factory checks still govern scope; JIT still governs learner readiness.
REALIZATIONS = MappingProxyType({ithkuil_identity.SENSE_ID: ithkuil_identity})


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
        result.append(realization.stage_identity(frontier, current, graph,
            source_root=source_root, source_registry=source_registry,
            answer_registry=answer_registry))
    return tuple(result)


def admitted_candidate_graph(staged, parent_graph):
    realization = REALIZATIONS.get(staged.source_sense_id)
    if realization is None:
        raise ValueError("JIT_CANDIDATE_NATIVE_CATALOG_REQUIRED")
    graph = realization.expanded_graph(parent_graph)
    staged.successor.verify_semantic_catalog(graph)
    return graph
