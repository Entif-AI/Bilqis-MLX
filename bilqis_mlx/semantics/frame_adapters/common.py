"""Source-owned frame common behavior."""
from __future__ import annotations
import re
from ...errors import ErrorBus, SEMANTIC_FRAME
from ..atlas_projection import FrozenAtlasSnapshot
from ..core import Signature
from ..numeric import CONTRACT as NUMERIC_CONTRACT
from ..frame_schema import ConceptRef, FrameSchema, RoleSpec, SourceSpan


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
