"""Released frame bindings for the current registered source dialects."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable

from ...errors import ErrorBus, SEMANTIC_FRAME
from ...factory.adapters import RegisteredSourceAdapter
from ...generated_assessment import digest
from ...source_adapters.numeric import decode as decode_numeric
from ...source_adapters.structure import inspect_source_query
from ..atlas_projection import FrozenAtlasSnapshot
from ..context_eligibility import (
    PUBLIC_FORMAL, ApprovedContextProjection, ContextEligibility, ContextHold,
    ContextMember, ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
    frame_evidence_digest, member_evidence_digest, project_context,
)
from ..core import Apply, Literal, Signature
from ..numeric import CONTRACT as NUMERIC_CONTRACT
from ..frame_schema import (
    AtomicFrame,
    ChildFrameRef,
    ConceptRef,
    FrameInstance,
    FrameSchema,
    FrameTree,
    RoleOccurrence,
    RoleSpec,
    SourceSpan,
    ast_construct_id,
    atomic_fallback,
    bind_frame_instance,
    occurrence_id,
    validate_frame_tree,
)


MICRO_PREDICATE_ADAPTER = "source.micro.predicates/v1"
BOOLEAN_CONNECTIVE_ADAPTER = "source.micro.boolean-connectives/v1"
BOOLEAN_COMPOSITE_ADAPTER = "source.micro.boolean-composite/v1"
BOOLEAN_IDENTIFICATION_ADAPTER = "source.micro.boolean-identification/v1"
FINITE_NUMERIC_ADAPTER = "source.finite-numeric/v2"
PUBLIC_FORMAL_TIMELESS_EPOCH = 0
MAX_PUBLIC_FORMAL_DRAW_EACH = 128
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_APPEND_ONLY_NUMERIC_NODES = {
    node["id"]: node for node in NUMERIC_CONTRACT["append_only_nodes"]}


def _adapter_fail(reason: str, adapter_id: str, span: SourceSpan, role_id: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.ADAPTER.INVALID_SOURCE,
        reason=reason,
        adapter_id=adapter_id,
        span_start=span.start,
        span_end=span.end,
        role_id=role_id,
    )


def _source_id(row: dict, adapter_id: str, span: SourceSpan) -> str:
    value = row.get("source_id") or row.get("id")
    if not isinstance(value, str) or not value:
        _adapter_fail("FRAME_SOURCE_INSTANCE_ID_MISSING", adapter_id, span, "<source-row>")
    return value


def _abi_entry_for_symbol(
    snapshot: FrozenAtlasSnapshot,
    symbol: str,
    *,
    adapter_id: str,
    span: SourceSpan,
    role_id: str,
):
    matches = tuple(entry for entry in snapshot.abi_entries if entry.symbol == symbol)
    if len(matches) != 1:
        _adapter_fail("FRAME_SOURCE_SYMBOL_NOT_IN_FROZEN_ABI",
                      adapter_id, span, role_id)
    return matches[0]


def _concept_ref(
    snapshot: FrozenAtlasSnapshot,
    graph: dict,
    symbol: str,
    type_id: str,
    *,
    adapter_id: str,
    span: SourceSpan,
    role_id: str,
) -> ConceptRef:
    entry = _abi_entry_for_symbol(
        snapshot, symbol, adapter_id=adapter_id, span=span, role_id=role_id)
    try:
        graph_index = graph["tokens"].index(symbol)
    except (KeyError, ValueError, TypeError):
        _adapter_fail("FRAME_SOURCE_SYMBOL_NOT_IN_SEMANTIC_GRAPH",
                      adapter_id, span, role_id)
    if graph_index != entry.index:
        _adapter_fail("FRAME_SOURCE_ATLAS_ABI_INDEX_DRIFT",
                      adapter_id, span, role_id)
    return ConceptRef(
        semantic_id=entry.semantic_id,
        semantic_release=snapshot.release_sha256,
        abi_index=entry.index,
        type_ids=(type_id,),
        source_reference=adapter_id + ":" + symbol,
    )


def _graph_signature(
    graph: dict,
    symbol: str,
    *,
    adapter_id: str,
    span: SourceSpan,
) -> tuple[Signature, tuple[str, ...], str]:
    try:
        index = graph["tokens"].index(symbol)
        node = graph["nodes"][index]
        if node.get("id") != symbol:
            raise KeyError(symbol)
        signature = Signature.parse(node["signature"])
        if node.get("arity") != len(signature.inputs):
            raise ValueError(symbol)
        contract_sha256 = graph["row_contract_sha256"][symbol]
        if (not isinstance(contract_sha256, str)
                or not _SHA256.fullmatch(contract_sha256)):
            raise ValueError(symbol)
        raw_roles = node.get("roles")
    except (KeyError, TypeError, ValueError):
        _adapter_fail("FRAME_SOURCE_OPERATOR_CONTRACT_INVALID",
                      adapter_id, span, "<operator>")
    if (isinstance(raw_roles, list)
            and len(raw_roles) == len(signature.inputs)
            and all(isinstance(item, str) and item for item in raw_roles)
            and len(set(raw_roles)) == len(raw_roles)):
        roles = tuple(raw_roles)
    else:
        roles = tuple("arg" + str(index) for index in range(len(signature.inputs)))
    return signature, roles, contract_sha256


def _schema_for_symbol(
    snapshot: FrozenAtlasSnapshot,
    graph: dict,
    symbol: str,
    ast_construct: str,
    *,
    adapter_id: str,
    span: SourceSpan,
    scope: str,
    contract_sha256: str | None = None,
) -> tuple[FrameSchema, Signature]:
    signature, roles, graph_contract_sha256 = _graph_signature(
        graph, symbol, adapter_id=adapter_id, span=span)
    operator = _abi_entry_for_symbol(
        snapshot, symbol, adapter_id=adapter_id, span=span, role_id="<operator>")
    schema = FrameSchema(
        schema_id="frame:" + operator.semantic_id,
        revision=1,
        ast_construct=ast_construct,
        roles=tuple(
            RoleSpec(role, (type_id,), 1, 1)
            for role, type_id in zip(roles, signature.inputs)
        ),
        order_mode="ORDERED",
        scope=scope,
        ast_contract_sha256=contract_sha256 or graph_contract_sha256,
    )
    return schema, signature


def _source_terminal(
    node: dict,
    expected_type: str,
    *,
    snapshot: FrozenAtlasSnapshot,
    graph: dict,
    assignments: dict,
    adapter_id: str,
    span: SourceSpan,
    role_id: str,
) -> ConceptRef:
    kind = node.get("kind") if isinstance(node, dict) else None
    if kind == "entity":
        if expected_type != "Entity" or set(node) != {"kind", "name"}:
            _adapter_fail("FRAME_SOURCE_ENTITY_TYPE_INVALID",
                          adapter_id, span, role_id)
        symbol = "micro.entity." + str(node["name"])
    elif kind == "const":
        if (set(node) != {"kind", "name", "type"}
                or node.get("type") != expected_type):
            _adapter_fail("FRAME_SOURCE_CONST_TYPE_INVALID",
                          adapter_id, span, role_id)
        prefix = "micro.entity." if expected_type == "Entity" else (
            "development." + expected_type + ".")
        symbol = prefix + str(node["name"])
    elif kind == "literal":
        if expected_type != "Boolean" or type(node.get("value")) is not bool:
            _adapter_fail("FRAME_SOURCE_BOOLEAN_LITERAL_INVALID",
                          adapter_id, span, role_id)
        symbol = "cogal.value." + ("true" if node["value"] else "false")
    elif kind == "variable":
        name = node.get("name")
        value = assignments.get(name) if isinstance(assignments, dict) else None
        if expected_type != "Boolean" or type(value) is not bool:
            _adapter_fail("FRAME_SOURCE_BOOLEAN_VARIABLE_INVALID",
                          adapter_id, span, role_id)
        symbol = "cogal.value." + ("true" if value else "false")
    else:
        _adapter_fail("FRAME_SOURCE_TERMINAL_UNSUPPORTED",
                      adapter_id, span, role_id)
    return _concept_ref(
        snapshot, graph, symbol, expected_type,
        adapter_id=adapter_id, span=span, role_id=role_id)


def _bind_source_expression(
    node: dict,
    *,
    snapshot: FrozenAtlasSnapshot,
    graph: dict,
    assignments: dict,
    adapter_id: str,
    source_instance_id: str,
    path: tuple[int, ...],
    span: SourceSpan,
    parent_occurrence_id: str | None,
    causal_prefix_end: int,
) -> tuple[FrameTree, str]:
    try:
        shape = inspect_source_query(node)
    except ValueError:
        _adapter_fail("FRAME_SOURCE_QUERY_INVALID", adapter_id, span, "<operator>")
    symbol = shape.root
    schema, signature = _schema_for_symbol(
        snapshot, graph, symbol, "source:" + str(node.get("kind")),
        adapter_id=adapter_id, span=span, scope="source-query")
    args = node.get("args")
    if not isinstance(args, list) or len(args) != len(signature.inputs):
        _adapter_fail("FRAME_SOURCE_QUERY_ARITY_INVALID",
                      adapter_id, span, "<operator>")

    current_occurrence = occurrence_id(source_instance_id, path)
    bindings = []
    children = []
    role_counts: dict[str, int] = {}
    for index, (argument, expected_type, role_spec) in enumerate(
            zip(args, signature.inputs, schema.roles)):
        role_id = role_spec.role_id
        occurrence = role_counts.get(role_id, 0)
        role_counts[role_id] = occurrence + 1
        if isinstance(argument, dict) and argument.get("kind") in {
                "compare", "relation", "apply", "op"}:
            child, child_type = _bind_source_expression(
                argument,
                snapshot=snapshot,
                graph=graph,
                assignments=assignments,
                adapter_id=adapter_id,
                source_instance_id=source_instance_id,
                path=(*path, index),
                span=span,
                parent_occurrence_id=current_occurrence,
                causal_prefix_end=causal_prefix_end,
            )
            if child_type != expected_type:
                _adapter_fail("FRAME_SOURCE_CHILD_TYPE_INVALID",
                              adapter_id, span, role_id)
            children.append(child)
            bindings.append(RoleOccurrence(
                role_id,
                occurrence,
                child_frame=ChildFrameRef(
                    child.root.occurrence_id,
                    child.root.content_digest,
                    (child_type,),
                ),
            ))
        else:
            bindings.append(RoleOccurrence(
                role_id,
                occurrence,
                concept=_source_terminal(
                    argument,
                    expected_type,
                    snapshot=snapshot,
                    graph=graph,
                    assignments=assignments,
                    adapter_id=adapter_id,
                    span=span,
                    role_id=role_id,
                ),
            ))
    frame = bind_frame_instance(
        schema,
        snapshot,
        source_instance_id=source_instance_id,
        structural_path=path,
        source_span=span,
        parent_occurrence_id=parent_occurrence_id,
        bindings=tuple(bindings),
        causal_prefix_end=causal_prefix_end,
        declared_scope="source-query",
        source_graph=graph,
        source_adapter_id=adapter_id,
    )
    tree = FrameTree(frame, tuple(children))
    return validate_frame_tree(tree), signature.output


def _numeric_literal_tree(
    value: Literal,
    *,
    snapshot: FrozenAtlasSnapshot,
    graph: dict,
    adapter_id: str,
    source_instance_id: str,
    path: tuple[int, ...],
    span: SourceSpan,
    parent_occurrence_id: str,
    causal_prefix_end: int,
) -> tuple[ConceptRef | None, FrameTree | None]:
    if value.type_name == "Number":
        return _concept_ref(
            snapshot, graph, "school.number." + value.value, "Number",
            adapter_id=adapter_id, span=span, role_id="<literal>"), None
    atomic = atomic_fallback(
        value,
        source_instance_id=source_instance_id,
        structural_path=path,
        source_span=span,
        parent_occurrence_id=parent_occurrence_id,
        causal_prefix_end=causal_prefix_end,
    )
    return None, FrameTree(atomic)


def _bind_numeric_expression(
    expression: Apply,
    *,
    snapshot: FrozenAtlasSnapshot,
    graph: dict,
    adapter_id: str,
    source_instance_id: str,
    path: tuple[int, ...],
    span: SourceSpan,
    parent_occurrence_id: str | None,
    causal_prefix_end: int,
) -> tuple[FrameTree, str]:
    native_contract_owner = (
        expression.operator.symbol in _APPEND_ONLY_NUMERIC_NODES)
    schema, graph_signature = _schema_for_symbol(
        snapshot, graph, expression.operator.symbol, ast_construct_id(expression),
        adapter_id=adapter_id, span=span, scope="formal-expression",
        contract_sha256=(
            expression.operator.contract_sha256 if native_contract_owner else None))
    symbol = expression.operator.symbol
    graph_node = graph["nodes"][graph["tokens"].index(symbol)]
    if digest(graph_node) != graph["row_contract_sha256"][symbol]:
        _adapter_fail("FRAME_NUMERIC_CONTRACT_DRIFT",
                      adapter_id, span, "<operator>")
    if native_contract_owner:
        declared = _APPEND_ONLY_NUMERIC_NODES[symbol]
        if any(graph_node.get(field) != declared[field]
               for field in ("id", "semantic_id", "signature", "arity", "meaning")):
            _adapter_fail("FRAME_NUMERIC_APPEND_ONLY_NODE_DRIFT",
                          adapter_id, span, "<operator>")
    if graph_signature != expression.operator.signature:
        _adapter_fail("FRAME_NUMERIC_SIGNATURE_DRIFT",
                      adapter_id, span, "<operator>")
    if expression.operator.token_index != graph["tokens"].index(expression.operator.symbol):
        _adapter_fail("FRAME_NUMERIC_OPERATOR_INDEX_DRIFT",
                      adapter_id, span, "<operator>")
    if expression.operator.contract_sha256 != schema.ast_contract_sha256:
        _adapter_fail("FRAME_NUMERIC_CONTRACT_DRIFT",
                      adapter_id, span, "<operator>")

    current_occurrence = occurrence_id(source_instance_id, path)
    bindings = []
    children = []
    for index, (argument, expected_type, role_spec) in enumerate(
            zip(expression.arguments, expression.operator.signature.inputs, schema.roles)):
        role_id = role_spec.role_id
        if isinstance(argument, Apply):
            child, child_type = _bind_numeric_expression(
                argument,
                snapshot=snapshot,
                graph=graph,
                adapter_id=adapter_id,
                source_instance_id=source_instance_id,
                path=(*path, index),
                span=span,
                parent_occurrence_id=current_occurrence,
                causal_prefix_end=causal_prefix_end,
            )
            concept = None
        else:
            concept, child = _numeric_literal_tree(
                argument,
                snapshot=snapshot,
                graph=graph,
                adapter_id=adapter_id,
                source_instance_id=source_instance_id,
                path=(*path, index),
                span=span,
                parent_occurrence_id=current_occurrence,
                causal_prefix_end=causal_prefix_end,
            )
            child_type = argument.type_name
        if child_type != expected_type:
            _adapter_fail("FRAME_NUMERIC_CHILD_TYPE_INVALID",
                          adapter_id, span, role_id)
        if child is None:
            bindings.append(RoleOccurrence(role_id, 0, concept=concept))
        else:
            children.append(child)
            bindings.append(RoleOccurrence(
                role_id,
                0,
                child_frame=ChildFrameRef(
                    child.root.occurrence_id,
                    child.root.content_digest,
                    (child_type,),
                ),
            ))
    frame = bind_frame_instance(
        schema,
        snapshot,
        source_instance_id=source_instance_id,
        structural_path=path,
        source_span=span,
        parent_occurrence_id=parent_occurrence_id,
        bindings=tuple(bindings),
        causal_prefix_end=causal_prefix_end,
        declared_scope="formal-expression",
        source_graph=graph,
        source_adapter_id=adapter_id,
    )
    tree = FrameTree(frame, tuple(children))
    return validate_frame_tree(tree), expression.type_name


def _bind_source_row(
    row: dict,
    snapshot: FrozenAtlasSnapshot,
    graph: dict,
    *,
    adapter_id: str,
    span: SourceSpan,
    causal_prefix_end: int,
) -> FrameTree:
    record = row.get("record")
    if not isinstance(record, dict):
        _adapter_fail("FRAME_SOURCE_RECORD_MISSING",
                      adapter_id, span, "<source-row>")
    query = record.get("query") or record.get("expression")
    if not isinstance(query, dict):
        _adapter_fail("FRAME_SOURCE_QUERY_MISSING",
                      adapter_id, span, "<source-row>")
    tree, _ = _bind_source_expression(
        query,
        snapshot=snapshot,
        graph=graph,
        assignments=record.get("assignments", {}),
        adapter_id=adapter_id,
        source_instance_id=_source_id(row, adapter_id, span),
        path=(),
        span=span,
        parent_occurrence_id=None,
        causal_prefix_end=causal_prefix_end,
    )
    return tree


def _bind_identification_row(
    row: dict,
    snapshot: FrozenAtlasSnapshot,
    graph: dict,
    *,
    adapter_id: str,
    span: SourceSpan,
    causal_prefix_end: int,
) -> FrameTree:
    del snapshot, graph
    record = row.get("record")
    if not isinstance(record, dict) or record.get("task") != "identify_boolean_operator":
        _adapter_fail("FRAME_BOOLEAN_IDENTIFICATION_RECORD_INVALID",
                      adapter_id, span, "<source-row>")
    atomic = atomic_fallback(
        record,
        source_instance_id=_source_id(row, adapter_id, span),
        structural_path=(),
        source_span=span,
        parent_occurrence_id=None,
        causal_prefix_end=causal_prefix_end,
    )
    return validate_frame_tree(FrameTree(atomic))


def _bind_numeric_row(
    row: dict,
    snapshot: FrozenAtlasSnapshot,
    graph: dict,
    *,
    adapter_id: str,
    span: SourceSpan,
    causal_prefix_end: int,
) -> FrameTree:
    record = row.get("record")
    try:
        expression = decode_numeric(record["symbols"])
    except (KeyError, TypeError, ValueError, IndexError):
        _adapter_fail("FRAME_NUMERIC_SOURCE_RECORD_INVALID",
                      adapter_id, span, "<source-row>")
    if isinstance(expression, Literal):
        atomic = atomic_fallback(
            expression,
            source_instance_id=_source_id(row, adapter_id, span),
            structural_path=(),
            source_span=span,
            parent_occurrence_id=None,
            causal_prefix_end=causal_prefix_end,
        )
        return validate_frame_tree(FrameTree(atomic))
    tree, _ = _bind_numeric_expression(
        expression,
        snapshot=snapshot,
        graph=graph,
        adapter_id=adapter_id,
        source_instance_id=_source_id(row, adapter_id, span),
        path=(),
        span=span,
        parent_occurrence_id=None,
        causal_prefix_end=causal_prefix_end,
    )
    return tree


RowBinder = Callable[..., FrameTree]
_ROW_BINDERS: dict[str, RowBinder] = {
    MICRO_PREDICATE_ADAPTER: _bind_source_row,
    BOOLEAN_CONNECTIVE_ADAPTER: _bind_source_row,
    BOOLEAN_COMPOSITE_ADAPTER: _bind_source_row,
    BOOLEAN_IDENTIFICATION_ADAPTER: _bind_identification_row,
    FINITE_NUMERIC_ADAPTER: _bind_numeric_row,
}


@dataclass(frozen=True)
class ReleasedFrameAdapter:
    source_adapter_id: str
    binder: RowBinder


def released_frame_adapter_ids() -> tuple[str, ...]:
    return tuple(sorted(_ROW_BINDERS))


def released_frame_adapter(
    source_adapter: RegisteredSourceAdapter,
    *,
    span: SourceSpan,
) -> ReleasedFrameAdapter:
    if not isinstance(source_adapter, RegisteredSourceAdapter):
        _adapter_fail("FRAME_REGISTERED_SOURCE_ADAPTER_REQUIRED",
                      "<unknown>", span, "<adapter>")
    adapter_id = source_adapter.descriptor.adapter_id
    binder = _ROW_BINDERS.get(adapter_id)
    if binder is None:
        _adapter_fail("FRAME_SOURCE_ADAPTER_UNRELEASED",
                      adapter_id, span, "<adapter>")
    return ReleasedFrameAdapter(adapter_id, binder)


def bind_registered_source_row(
    source_adapter: RegisteredSourceAdapter,
    row: dict,
    snapshot: FrozenAtlasSnapshot,
    *,
    source_root: str | Path,
    graph: dict,
    source_span: SourceSpan,
    causal_prefix_end: int,
    course=None,
) -> FrameTree:
    """Recheck and frame one row through its existing registered source owner."""
    released = released_frame_adapter(source_adapter, span=source_span)
    try:
        valid = source_adapter.check(
            row,
            source_root=source_root,
            graph=graph,
            course=course,
        )
    except (KeyError, TypeError, ValueError, IndexError):
        _adapter_fail("FRAME_SOURCE_ADAPTER_CHECK_ERROR",
                      released.source_adapter_id, source_span, "<source-row>")
    if valid is not True:
        _adapter_fail("FRAME_SOURCE_ADAPTER_CHECK_FAILED",
                      released.source_adapter_id, source_span, "<source-row>")
    if causal_prefix_end < source_span.end:
        _adapter_fail("FRAME_CAUSAL_PREFIX_INVALID",
                      released.source_adapter_id, source_span, "<frame>")
    return released.binder(
        row,
        snapshot,
        graph,
        adapter_id=released.source_adapter_id,
        span=source_span,
        causal_prefix_end=causal_prefix_end,
    )


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
