"""Resolve canonical A/B/C source owners before public-formal grants exist."""
from pathlib import Path

from ...factory.adapters import RegisteredSourceAdapter
from ...factory.source_identity import canonical_source_adapter
from ...generated_assessment import digest
from ..atlas_projection import FrozenAtlasSnapshot
from ..context_eligibility import PUBLIC_FORMAL, ContextPolicy, SourceFrontier, TaskScope
from .common import (
    BOOLEAN_COMPOSITE_ADAPTER, BOOLEAN_CONNECTIVE_ADAPTER,
    BOOLEAN_IDENTIFICATION_ADAPTER, FINITE_NUMERIC_ADAPTER,
    MAX_PUBLIC_FORMAL_DRAW_EACH, MICRO_PREDICATE_ADAPTER, _adapter_fail,
)


def canonical_adapter(source_adapter, span):
    """A copied frozen adapter record does not own its supplied callables."""
    adapter_id = getattr(getattr(source_adapter, "descriptor", None), "adapter_id", "<unknown>")
    if not isinstance(source_adapter, RegisteredSourceAdapter):
        _adapter_fail("BAMF_CONTEXT_PUBLIC_FORMAL_ADAPTER_UNTRUSTED",
                      adapter_id, span, "<public-formal>")
    try:
        canonical = canonical_source_adapter(source_adapter)
    except (IndexError, TypeError, ValueError):
        _adapter_fail("BAMF_CONTEXT_PUBLIC_FORMAL_ADAPTER_UNTRUSTED",
                      adapter_id, span, "<public-formal>")
    if (source_adapter.descriptor != canonical.descriptor
            or any(getattr(source_adapter, name) is not getattr(canonical, name)
                   for name in ("check", "draw", "enrich", "witness", "dependencies", "semantic_footprint"))):
        _adapter_fail("BAMF_CONTEXT_PUBLIC_FORMAL_ADAPTER_UNTRUSTED",
                      adapter_id, span, "<public-formal>")
    return canonical


def canonical_graph(source_root, graph, adapter_id, span):
    root, canonical = source_graph_for_adapter(adapter_id)
    if Path(source_root).resolve() != root.resolve():
        _adapter_fail("BAMF_CONTEXT_PUBLIC_FORMAL_SOURCE_ROOT_DRIFT",
                      adapter_id, span, "<public-formal>")
    if digest(graph) != digest(canonical):
        _adapter_fail("BAMF_CONTEXT_PUBLIC_FORMAL_GRAPH_DRIFT",
                      adapter_id, span, "<public-formal>")
    return root, canonical


def source_graph_for_adapter(adapter_id: str):
    """Return the repository-owned source graph for a registered formal adapter."""
    root = Path(__file__).resolve().parents[3] / "vendor/legacy-v16"
    if adapter_id == FINITE_NUMERIC_ADAPTER:
        from ...live_grade_c import registry_graph
        return root, registry_graph()
    if adapter_id not in {
            MICRO_PREDICATE_ADAPTER, BOOLEAN_CONNECTIVE_ADAPTER,
            BOOLEAN_COMPOSITE_ADAPTER, BOOLEAN_IDENTIFICATION_ADAPTER}:
        _adapter_fail("BAMF_CONTEXT_PUBLIC_FORMAL_ADAPTER_UNTRUSTED",
                      str(adapter_id), SourceSpan(0, 0), "<public-formal>")
    from ...grade_a_probe import read_sources
    return root, read_sources(root)[2]


def verify_draw(adapter, row, source_root, graph, span, seed, each, profile, course):
    adapter_id = adapter.descriptor.adapter_id
    if type(seed) is not int or type(each) is not int or not 1 <= each <= MAX_PUBLIC_FORMAL_DRAW_EACH:
        _adapter_fail("BAMF_CONTEXT_PUBLIC_FORMAL_DRAW_PROVENANCE_INVALID",
                      adapter_id, span, "<public-formal>")
    arguments = dict(source_root=source_root, graph=graph, course=course,
                     capability=row.get("capability"), seed=seed, each=each)
    if profile is not None:
        arguments["profile_parameters"] = profile
    try:
        rows = adapter.draw(**arguments)
    except (KeyError, TypeError, ValueError):
        _adapter_fail("BAMF_CONTEXT_PUBLIC_FORMAL_DRAW_PROVENANCE_INVALID",
                      adapter_id, span, "<public-formal>")
    if not isinstance(rows, (tuple, list)) or not any(candidate == row for candidate in rows):
        _adapter_fail("BAMF_CONTEXT_PUBLIC_FORMAL_ROW_IDENTITY_UNVERIFIED",
                      adapter_id, span, "<public-formal>")


def validate_policy(snapshot, task, frontier, policy, adapter_id, span):
    if (not isinstance(task, TaskScope)
            or not isinstance(frontier, SourceFrontier)
            or not isinstance(policy, ContextPolicy)
            or not isinstance(snapshot, FrozenAtlasSnapshot)
            or snapshot.release_sha256 != task.semantic_release
            or task.purpose is None or task.purpose not in policy.allowed_purposes
            or PUBLIC_FORMAL not in policy.allowed_regimes
            or PUBLIC_FORMAL not in policy.allowed_join_classes
            or policy.rights_epoch != frontier.rights_epoch):
        _adapter_fail("BAMF_CONTEXT_PUBLIC_FORMAL_POLICY_INVALID",
                      adapter_id, span, "<public-formal>")
