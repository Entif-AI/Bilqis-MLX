"""Source-owned A/B/C admission before solver-visible context exists."""
from pathlib import Path

from ...factory.adapters import RegisteredSourceAdapter
from ..atlas_projection import FrozenAtlasSnapshot
from ..context_eligibility import ApprovedContextProjection, ContextHold, ContextPolicy, SourceFrontier, TaskScope
from ..frame_schema import SourceSpan
from .common import _adapter_fail
from .public_formal_sources import canonical_adapter, canonical_graph, validate_policy, verify_draw
from .public_formal_grants import admit_tree
from .registry import bind_registered_source_row, released_frame_adapter


def public_formal_context(
    source_adapter: RegisteredSourceAdapter,
    row: dict,
    snapshot: FrozenAtlasSnapshot,
    *,
    source_root: str | Path,
    graph: dict,
    task_scope: TaskScope,
    source_frontier: SourceFrontier,
    policy: ContextPolicy,
    source_seed: int,
    source_each: int,
    source_profile_parameters: dict | None = None,
    course=None,
) -> tuple[ApprovedContextProjection, SourceFrontier] | ContextHold:
    """Reproduce a complete source row before creating any PUBLIC_FORMAL grants."""
    tokens = row.get("tokens") if isinstance(row, dict) else None
    if not isinstance(tokens, list) or not tokens:
        _adapter_fail("BAMF_CONTEXT_PUBLIC_FORMAL_TOKENS_MISSING",
                      "<unknown>", SourceSpan(0, 0), "<public-formal>")
    # A/B/C records own their complete span. Callers cannot backdate it.
    span = SourceSpan(0, len(tokens))
    source_adapter = canonical_adapter(source_adapter, span)
    adapter_id = source_adapter.descriptor.adapter_id
    root, graph = canonical_graph(source_root, graph, adapter_id, span)
    verify_draw(source_adapter, row, root, graph, span, source_seed,
                source_each, source_profile_parameters, course)
    validate_policy(snapshot, task_scope, source_frontier, policy, adapter_id, span)
    if span.end > task_scope.causal_prefix_end:
        return ContextHold(("BAMF_CONTEXT_INVISIBLE_PREFIX",), (), ())
    released = released_frame_adapter(source_adapter, span=span)
    tree = bind_registered_source_row(
        source_adapter, row, snapshot, source_root=source_root, graph=graph,
        source_span=span, causal_prefix_end=span.end, course=course)
    return admit_tree(tree, row, released.source_adapter_id,
                      task_scope, source_frontier, policy, span)
