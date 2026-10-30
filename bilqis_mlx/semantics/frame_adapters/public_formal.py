"""Source-owned frame public formal behavior."""
from __future__ import annotations
from pathlib import Path
from ...factory.adapters import RegisteredSourceAdapter
from ...generated_assessment import digest
from ..atlas_projection import FrozenAtlasSnapshot
from ..context_eligibility import PUBLIC_FORMAL, ApprovedContextProjection, ContextEligibility, ContextHold, ContextMember, ContextPolicy, SourceFrontier, SourceGrant, TaskScope, frame_evidence_digest, member_evidence_digest, project_context
from ..frame_schema import FrameInstance, FrameTree, SourceSpan
from .common import FINITE_NUMERIC_ADAPTER, MAX_PUBLIC_FORMAL_DRAW_EACH, PUBLIC_FORMAL_TIMELESS_EPOCH, _adapter_fail
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
    """Source-owned A/B/C admission, separate from the solver import closure.

    The registered source adapter verifies the row before this constructor
    mints any PUBLIC_FORMAL grants. Runtime readers consume only the resulting
    approved context projection, never this source-admission entrypoint.
    """
    tokens = row.get("tokens") if isinstance(row, dict) else None
    if not isinstance(tokens, list) or not tokens:
        _adapter_fail(
            "BAMF_CONTEXT_PUBLIC_FORMAL_TOKENS_MISSING",
            "<unknown>", SourceSpan(0, 0), "<public-formal>")
    # Registered formal A/B/C rows are complete source sequences. Their
    # canonical span is the full verified token sequence, never a caller-
    # supplied timestamp or position that could be backdated on first grant.
    source_span = SourceSpan(0, len(tokens))
    adapter_id = getattr(
        getattr(source_adapter, "descriptor", None), "adapter_id", "<unknown>")
    # RegisteredSourceAdapter is a frozen record, not an authority token:
    # a caller can replace its checker. Resolve the canonical source owner
    # and execute *that* checker, never a supplied callable.
    from ...source_adapters.school import live_source_registry
    if not isinstance(source_adapter, RegisteredSourceAdapter):
        _adapter_fail(
            "BAMF_CONTEXT_PUBLIC_FORMAL_ADAPTER_UNTRUSTED",
            adapter_id, source_span, "<public-formal>")
    try:
        canonical = live_source_registry().require(
            source_adapter.descriptor.generator_id,
            source_adapter.descriptor.accepted_oracle_ids[0])
    except (IndexError, TypeError, ValueError):
        _adapter_fail(
            "BAMF_CONTEXT_PUBLIC_FORMAL_ADAPTER_UNTRUSTED",
            adapter_id, source_span, "<public-formal>")
    if (source_adapter.descriptor != canonical.descriptor
            or source_adapter.check is not canonical.check
            or source_adapter.draw is not canonical.draw
            or source_adapter.enrich is not canonical.enrich
            or source_adapter.witness is not canonical.witness
            or source_adapter.dependencies is not canonical.dependencies
            or source_adapter.semantic_footprint is not canonical.semantic_footprint):
        _adapter_fail(
            "BAMF_CONTEXT_PUBLIC_FORMAL_ADAPTER_UNTRUSTED",
            adapter_id, source_span, "<public-formal>")
    source_adapter = canonical
    canonical_root = Path(__file__).resolve().parents[3] / "vendor/legacy-v16"
    if Path(source_root).resolve() != canonical_root.resolve():
        _adapter_fail(
            "BAMF_CONTEXT_PUBLIC_FORMAL_SOURCE_ROOT_DRIFT",
            adapter_id, source_span, "<public-formal>")
    if adapter_id == FINITE_NUMERIC_ADAPTER:
        from ...live_grade_c import registry_graph
        canonical_graph = registry_graph()
    else:
        from ...grade_a_probe import read_sources
        canonical_graph = read_sources(canonical_root)[2]
    if digest(graph) != digest(canonical_graph):
        _adapter_fail(
            "BAMF_CONTEXT_PUBLIC_FORMAL_GRAPH_DRIFT",
            adapter_id, source_span, "<public-formal>")
    graph = canonical_graph
    if (type(source_seed) is not int or type(source_each) is not int
            or not 1 <= source_each <= MAX_PUBLIC_FORMAL_DRAW_EACH):
        _adapter_fail(
            "BAMF_CONTEXT_PUBLIC_FORMAL_DRAW_PROVENANCE_INVALID",
            adapter_id, source_span, "<public-formal>")
    draw_args = {
        "source_root": canonical_root, "graph": graph, "course": course,
        "capability": row.get("capability"), "seed": source_seed,
        "each": source_each,
    }
    if source_profile_parameters is not None:
        draw_args["profile_parameters"] = source_profile_parameters
    try:
        canonical_rows = canonical.draw(**draw_args)
    except (KeyError, TypeError, ValueError) as exc:
        _adapter_fail(
            "BAMF_CONTEXT_PUBLIC_FORMAL_DRAW_PROVENANCE_INVALID",
            adapter_id, source_span, "<public-formal>")
    if not isinstance(canonical_rows, (tuple, list)) or not any(
            candidate == row for candidate in canonical_rows):
        _adapter_fail(
            "BAMF_CONTEXT_PUBLIC_FORMAL_ROW_IDENTITY_UNVERIFIED",
            adapter_id, source_span, "<public-formal>")
    if (not isinstance(task_scope, TaskScope)
            or not isinstance(source_frontier, SourceFrontier)
            or not isinstance(policy, ContextPolicy)
            or not isinstance(snapshot, FrozenAtlasSnapshot)
            or snapshot.release_sha256 != task_scope.semantic_release
            or task_scope.purpose is None
            or task_scope.purpose not in policy.allowed_purposes
            or PUBLIC_FORMAL not in policy.allowed_regimes
            or PUBLIC_FORMAL not in policy.allowed_join_classes
            or policy.rights_epoch != source_frontier.rights_epoch):
        _adapter_fail(
            "BAMF_CONTEXT_PUBLIC_FORMAL_POLICY_INVALID",
            adapter_id, source_span, "<public-formal>")
    if source_span.end > task_scope.causal_prefix_end:
        return ContextHold(("BAMF_CONTEXT_INVISIBLE_PREFIX",), (), ())
    released = released_frame_adapter(source_adapter, span=source_span)
    tree = bind_registered_source_row(
        source_adapter, row, snapshot, source_root=source_root, graph=graph,
        source_span=source_span, causal_prefix_end=source_span.end,
        course=course)

    def walk(node: FrameTree):
        yield node.root
        for child in node.children:
            yield from walk(child)

    envelopes = []
    grants = {item.source_handle: item for item in source_frontier.grants}
    source_visible_digest = digest({
        "source_id": row.get("source_id") or row.get("id"),
        "record": row.get("record"),
        "tokens": row.get("tokens"),
    })
    for frame in walk(tree):
        prefix = (
            "public-formal:" + released.source_adapter_id + ":"
            + source_visible_digest + ":" + frame.occurrence_id)
        members = (
            tuple(ContextMember(
                binding.role_id, binding.occurrence_index,
                prefix + ":member:" + binding.role_id + ":" + str(binding.occurrence_index),
                frame.causal_prefix_end)
                for binding in frame.bindings)
            if isinstance(frame, FrameInstance)
            else (ContextMember(
                "<atomic>", 0, prefix + ":member:<atomic>:0",
                frame.causal_prefix_end),)
        )
        envelope = ContextEligibility(
            frame_handle=prefix + ":frame", frame=frame,
            source_handle=prefix + ":source", members=members,
            principal_id=task_scope.principal_id,
            tenant_id=task_scope.tenant_id, purpose=task_scope.purpose,
            source_regime=PUBLIC_FORMAL,
            semantic_release=task_scope.semantic_release,
            jurisdiction=task_scope.jurisdiction, scope=task_scope.scope,
            join_class=PUBLIC_FORMAL, policy_epoch=policy.policy_epoch,
            rights_epoch=source_frontier.rights_epoch,
            correction_generation=source_frontier.correction_generation,
            observed_at=PUBLIC_FORMAL_TIMELESS_EPOCH,
            effective_from=PUBLIC_FORMAL_TIMELESS_EPOCH,
            effective_until=None,
            causal_prefix_end=frame.causal_prefix_end,
        )
        evidence = {envelope.source_handle: frame_evidence_digest(frame)}
        evidence.update({
            member.source_handle: member_evidence_digest(frame, member)
            for member in members
        })
        for handle, evidence_sha in evidence.items():
            grant = SourceGrant(
                handle, task_scope.principal_id, task_scope.tenant_id,
                PUBLIC_FORMAL, task_scope.semantic_release, evidence_sha,
                (task_scope.purpose,), (task_scope.jurisdiction,),
                (task_scope.scope,), source_frontier.rights_epoch,
                source_frontier.correction_generation,
                PUBLIC_FORMAL_TIMELESS_EPOCH, PUBLIC_FORMAL_TIMELESS_EPOCH,
            )
            prior = grants.get(handle)
            if prior is not None and prior != grant:
                _adapter_fail(
                    "BAMF_CONTEXT_PUBLIC_FORMAL_GRANT_COLLISION",
                    adapter_id, source_span, "<public-formal>")
            grants[handle] = grant
        envelopes.append(envelope)
    frontier = SourceFrontier(
        source_frontier.rights_epoch, source_frontier.correction_generation,
        tuple(sorted(grants.values(), key=lambda grant: grant.source_handle)))
    projected = project_context(
        tuple(envelopes), task_scope, frontier, policy)
    if isinstance(projected, ContextHold):
        return projected
    return projected, frontier
