"""Released, occurrence-aware semantic frame records over the native typed AST."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import re

from ..errors import BilqisError, ErrorBus, SEMANTIC_FRAME, SCHOOL
from .atlas_projection import FrozenAtlasSnapshot
from .core import Apply, Expression, Literal, expression_digest


FRAME_SCHEMA_RECORD = "bilqis.semantic-frame-schema/v1"
FRAME_INSTANCE_RECORD = "bilqis.semantic-frame-instance/v1"
CONCEPT_REF_RECORD = "bilqis.semantic-concept-ref/v1"
ROLE_SPEC_RECORD = "bilqis.semantic-role-spec/v1"
ROLE_OCCURRENCE_RECORD = "bilqis.semantic-role-occurrence/v1"
CHILD_FRAME_REF_RECORD = "bilqis.semantic-child-frame-ref/v1"
SOURCE_SPAN_RECORD = "bilqis.semantic-source-span/v1"
FRAME_EDGE_RECORD = "bilqis.semantic-frame-edge/v1"
ATOMIC_FRAME_RECORD = "bilqis.semantic-atomic-frame/v1"
FRAME_TREE_RECORD = "bilqis.semantic-frame-tree/v1"

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ORDER_MODES = frozenset({"ORDERED", "UNORDERED"})


class BindingState(str, Enum):
    VALUE = "VALUE"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"
    ALTERNATIVES = "ALTERNATIVES"


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _occurrence_digest(source_instance_id: str, structural_path: tuple[int, ...]) -> str:
    return _digest({
        "source_instance_id": source_instance_id,
        "structural_path": list(structural_path),
    })


def _frame_content_digest(
    frame_schema_id: str,
    frame_schema_revision: int,
    bindings: tuple["RoleOccurrence", ...],
) -> str:
    return _digest({
        "frame_schema_id": frame_schema_id,
        "frame_schema_revision": frame_schema_revision,
        "bindings": [
            binding.content_identity()
            for binding in sorted(bindings, key=lambda item: item.key)
        ],
    })


def _text(value: object, reason: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(reason)
    return value


@dataclass(frozen=True, order=True)
class SourceSpan:
    start: int
    end: int
    schema_version: str = SOURCE_SPAN_RECORD

    def __post_init__(self) -> None:
        if (type(self.start) is not int or type(self.end) is not int
                or self.start < 0 or self.end < self.start
                or self.schema_version != SOURCE_SPAN_RECORD):
            _fail("FRAME_SOURCE_SPAN_INVALID")


@dataclass(frozen=True, order=True)
class RoleSpec:
    role_id: str
    allowed_type_ids: tuple[str, ...]
    min_cardinality: int
    max_cardinality: int
    schema_version: str = ROLE_SPEC_RECORD

    def __post_init__(self) -> None:
        if (not isinstance(self.role_id, str) or not self.role_id
                or not self.allowed_type_ids
                or self.allowed_type_ids != tuple(sorted(set(self.allowed_type_ids)))
                or any(not isinstance(item, str) or not item for item in self.allowed_type_ids)
                or type(self.min_cardinality) is not int
                or type(self.max_cardinality) is not int
                or self.min_cardinality < 0
                or self.max_cardinality < self.min_cardinality
                or self.schema_version != ROLE_SPEC_RECORD):
            _fail("FRAME_ROLE_SPEC_INVALID")


@dataclass(frozen=True)
class FrameSchema:
    schema_id: str
    revision: int
    ast_construct: str
    roles: tuple[RoleSpec, ...]
    order_mode: str
    scope: str
    ast_contract_sha256: str | None = None
    schema_version: str = FRAME_SCHEMA_RECORD

    def __post_init__(self) -> None:
        role_ids = tuple(role.role_id for role in self.roles)
        if (not isinstance(self.schema_id, str) or not self.schema_id
                or type(self.revision) is not int or self.revision < 1
                or not isinstance(self.ast_construct, str) or not self.ast_construct
                or not self.roles or len(role_ids) != len(set(role_ids))
                or self.order_mode not in _ORDER_MODES
                or not isinstance(self.scope, str) or not self.scope
                or (self.ast_contract_sha256 is not None
                    and not _SHA256.fullmatch(self.ast_contract_sha256))
                or self.schema_version != FRAME_SCHEMA_RECORD):
            _fail("FRAME_SCHEMA_INVALID")

    @property
    def identity(self) -> str:
        return f"{self.schema_id}@{self.revision}"

    def canonical_bytes(self) -> bytes:
        return _bytes(asdict(self))


@dataclass(frozen=True, order=True)
class ConceptRef:
    semantic_id: str
    semantic_release: str
    abi_index: int
    type_ids: tuple[str, ...]
    source_reference: str
    schema_version: str = CONCEPT_REF_RECORD

    def __post_init__(self) -> None:
        if (not isinstance(self.semantic_id, str) or not self.semantic_id
                or not isinstance(self.semantic_release, str)
                or not _SHA256.fullmatch(self.semantic_release)
                or type(self.abi_index) is not int or self.abi_index < 0
                or self.type_ids != tuple(sorted(set(self.type_ids)))
                or any(not isinstance(item, str) or not item for item in self.type_ids)
                or not isinstance(self.source_reference, str) or not self.source_reference
                or self.schema_version != CONCEPT_REF_RECORD):
            _fail("FRAME_CONCEPT_REF_INVALID")

    def content_identity(self) -> dict:
        return {
            "semantic_id": self.semantic_id,
            "semantic_release": self.semantic_release,
            "abi_index": self.abi_index,
            "type_ids": list(self.type_ids),
        }


@dataclass(frozen=True, order=True)
class ChildFrameRef:
    occurrence_id: str
    content_digest: str
    type_ids: tuple[str, ...] = ("Frame",)
    schema_version: str = CHILD_FRAME_REF_RECORD

    def __post_init__(self) -> None:
        if (not _SHA256.fullmatch(self.occurrence_id)
                or not _SHA256.fullmatch(self.content_digest)
                or not self.type_ids
                or self.type_ids != tuple(sorted(set(self.type_ids)))
                or self.schema_version != CHILD_FRAME_REF_RECORD):
            _fail("FRAME_CHILD_REF_INVALID")


@dataclass(frozen=True)
class RoleOccurrence:
    role_id: str
    occurrence_index: int
    concept: ConceptRef | None = None
    child_frame: ChildFrameRef | None = None
    state: BindingState = BindingState.VALUE
    alternatives: tuple[ConceptRef, ...] = ()
    schema_version: str = ROLE_OCCURRENCE_RECORD

    def __post_init__(self) -> None:
        value_targets = int(self.concept is not None) + int(self.child_frame is not None)
        valid_state = (
            (self.state is BindingState.VALUE and value_targets == 1 and not self.alternatives)
            or (self.state in {BindingState.NONE, BindingState.UNKNOWN}
                and value_targets == 0 and not self.alternatives)
            or (self.state is BindingState.ALTERNATIVES
                and value_targets == 0 and bool(self.alternatives))
        )
        if (not isinstance(self.role_id, str) or not self.role_id
                or type(self.occurrence_index) is not int or self.occurrence_index < 0
                or not isinstance(self.state, BindingState)
                or not valid_state
                or self.schema_version != ROLE_OCCURRENCE_RECORD):
            _fail("FRAME_ROLE_OCCURRENCE_INVALID")

    @property
    def key(self) -> tuple[str, int]:
        return self.role_id, self.occurrence_index

    def content_identity(self) -> dict:
        if self.state is BindingState.VALUE and self.concept is not None:
            target = {"kind": "concept", "value": self.concept.content_identity()}
        elif self.state is BindingState.VALUE and self.child_frame is not None:
            target = {
                "kind": "child-frame",
                "content_digest": self.child_frame.content_digest,
                "type_ids": list(self.child_frame.type_ids),
            }
        elif self.state is BindingState.ALTERNATIVES:
            target = {
                "kind": "alternatives",
                "values": [item.content_identity() for item in self.alternatives],
            }
        else:
            target = {"kind": self.state.value.lower()}
        return {
            "role_id": self.role_id,
            "occurrence_index": self.occurrence_index,
            "state": self.state.value,
            "target": target,
        }


@dataclass(frozen=True, order=True)
class FrameEdge:
    parent_occurrence_id: str
    role_id: str
    occurrence_index: int
    child_occurrence_id: str
    schema_version: str = FRAME_EDGE_RECORD


@dataclass(frozen=True)
class FrameInstance:
    frame_schema_id: str
    frame_schema_revision: int
    occurrence_id: str
    content_digest: str
    source_instance_id: str
    structural_path: tuple[int, ...]
    source_span: SourceSpan
    parent_occurrence_id: str | None
    bindings: tuple[RoleOccurrence, ...]
    causal_prefix_end: int
    schema_version: str = FRAME_INSTANCE_RECORD

    def __post_init__(self) -> None:
        keys = tuple(binding.key for binding in self.bindings)
        if (not isinstance(self.frame_schema_id, str) or not self.frame_schema_id
                or type(self.frame_schema_revision) is not int or self.frame_schema_revision < 1
                or not _SHA256.fullmatch(self.occurrence_id)
                or not _SHA256.fullmatch(self.content_digest)
                or not isinstance(self.source_instance_id, str) or not self.source_instance_id
                or any(type(item) is not int or item < 0 for item in self.structural_path)
                or (self.parent_occurrence_id is not None
                    and not _SHA256.fullmatch(self.parent_occurrence_id))
                or len(keys) != len(set(keys))
                or type(self.causal_prefix_end) is not int
                or self.causal_prefix_end < self.source_span.end
                or self.schema_version != FRAME_INSTANCE_RECORD):
            _fail("FRAME_INSTANCE_INVALID")
        if self.occurrence_id != _occurrence_digest(
                self.source_instance_id, self.structural_path):
            _fail("FRAME_OCCURRENCE_ID_MISMATCH")
        if self.content_digest != _frame_content_digest(
                self.frame_schema_id, self.frame_schema_revision, self.bindings):
            _fail("FRAME_CONTENT_DIGEST_MISMATCH")

    @property
    def child_edges(self) -> tuple[FrameEdge, ...]:
        return tuple(
            FrameEdge(
                self.occurrence_id,
                binding.role_id,
                binding.occurrence_index,
                binding.child_frame.occurrence_id,
            )
            for binding in self.bindings
            if binding.child_frame is not None
        )

    def canonical_bytes(self) -> bytes:
        return _bytes(asdict(self))


@dataclass(frozen=True)
class AtomicFrame:
    occurrence_id: str
    content_digest: str
    source_instance_id: str
    structural_path: tuple[int, ...]
    source_span: SourceSpan
    parent_occurrence_id: str | None
    ast_construct: str
    source_payload: str
    causal_prefix_end: int
    schema_version: str = ATOMIC_FRAME_RECORD

    def __post_init__(self) -> None:
        try:
            json.loads(self.source_payload)
        except (TypeError, ValueError):
            _fail("FRAME_ATOMIC_SOURCE_PAYLOAD_INVALID")
        if (not _SHA256.fullmatch(self.occurrence_id)
                or not _SHA256.fullmatch(self.content_digest)
                or not self.source_instance_id
                or any(type(item) is not int or item < 0 for item in self.structural_path)
                or (self.parent_occurrence_id is not None
                    and not _SHA256.fullmatch(self.parent_occurrence_id))
                or not self.ast_construct
                or type(self.causal_prefix_end) is not int
                or self.causal_prefix_end < self.source_span.end
                or self.schema_version != ATOMIC_FRAME_RECORD):
            _fail("FRAME_ATOMIC_FALLBACK_INVALID")

    @property
    def source_data(self):
        return json.loads(self.source_payload)


@dataclass(frozen=True)
class FrameTree:
    root: FrameInstance | AtomicFrame
    children: tuple["FrameTree", ...] = ()
    schema_version: str = FRAME_TREE_RECORD

    def __post_init__(self) -> None:
        if self.schema_version != FRAME_TREE_RECORD:
            _fail("FRAME_TREE_INVALID")


def _binding_fail(reason: str, source_span: SourceSpan, role_id: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason,
        span_start=source_span.start,
        span_end=source_span.end,
        role_id=role_id,
    )


def ast_construct_id(expression: Expression) -> str:
    """Name native AST constructors without inventing a second expression tree."""
    if isinstance(expression, Literal):
        return "literal:" + expression.type_name
    if isinstance(expression, Apply):
        return "apply:" + expression.operator.symbol
    _fail("FRAME_NATIVE_AST_CONSTRUCT_INVALID")


def source_ast_construct_id(ast: object) -> str:
    if isinstance(ast, (Literal, Apply)):
        return ast_construct_id(ast)
    if isinstance(ast, dict):
        kind = ast.get("kind")
        if isinstance(kind, str) and kind:
            return "source:" + kind
        task = ast.get("task")
        if isinstance(task, str) and task:
            return "source-task:" + task
    _fail("FRAME_SOURCE_AST_CONSTRUCT_INVALID")


def native_ast_content_digest(expression: Expression) -> str:
    """Reuse the existing semantic AST's canonical content identity."""
    return expression_digest(expression)


def _source_payload(ast: object) -> object:
    if isinstance(ast, (Literal, Apply)):
        return {"native_expression": asdict(ast)}
    if isinstance(ast, (dict, list, str, int, float, bool)) or ast is None:
        return ast
    _fail("FRAME_ATOMIC_SOURCE_UNSERIALIZABLE")


def concept_ref_from_snapshot(
    snapshot: FrozenAtlasSnapshot,
    semantic_id: str,
    *,
    source_reference: str,
    type_ids: tuple[str, ...] | None = None,
) -> ConceptRef:
    if not isinstance(snapshot, FrozenAtlasSnapshot):
        _fail("FRAME_ATLAS_SNAPSHOT_REQUIRED")
    abi = snapshot.abi_for_semantic(semantic_id)
    if type_ids is None:
        matching = tuple(
            item for item in snapshot.concepts
            if item.concept.semantic_id == semantic_id)
        if len(matching) != 1:
            _fail("FRAME_CONCEPT_TYPES_REQUIRED")
        type_ids = matching[0].concept.types
    return ConceptRef(
        semantic_id=semantic_id,
        semantic_release=snapshot.release_sha256,
        abi_index=abi.index,
        type_ids=tuple(sorted(set(type_ids))),
        source_reference=source_reference,
    )


def occurrence_id(source_instance_id: str, structural_path: tuple[int, ...]) -> str:
    _text(source_instance_id, "FRAME_SOURCE_INSTANCE_ID_INVALID")
    if any(type(item) is not int or item < 0 for item in structural_path):
        _fail("FRAME_STRUCTURAL_PATH_INVALID")
    return _occurrence_digest(source_instance_id, structural_path)


def content_digest(
    schema: FrameSchema,
    bindings: tuple[RoleOccurrence, ...],
) -> str:
    return _frame_content_digest(schema.schema_id, schema.revision, bindings)


def _binding_concepts(binding: RoleOccurrence) -> tuple[ConceptRef, ...]:
    if binding.state is BindingState.VALUE and binding.concept is not None:
        return (binding.concept,)
    if binding.state is BindingState.ALTERNATIVES:
        return binding.alternatives
    return ()


def validate_frame_bindings(
    schema: FrameSchema,
    snapshot: FrozenAtlasSnapshot,
    *,
    bindings: tuple[RoleOccurrence, ...],
    source_span: SourceSpan,
    causal_prefix_end: int,
    declared_scope: str,
) -> tuple[RoleOccurrence, ...]:
    if not isinstance(snapshot, FrozenAtlasSnapshot):
        _fail("FRAME_ATLAS_SNAPSHOT_REQUIRED")
    if declared_scope != schema.scope:
        _binding_fail("FRAME_SCOPE_MISMATCH", source_span, "<frame>")
    if type(causal_prefix_end) is not int or causal_prefix_end < source_span.end:
        _binding_fail("FRAME_CAUSAL_PREFIX_INVALID", source_span, "<frame>")

    role_by_id = {role.role_id: role for role in schema.roles}
    if any(binding.role_id not in role_by_id for binding in bindings):
        unknown = next(binding.role_id for binding in bindings
                       if binding.role_id not in role_by_id)
        _binding_fail("FRAME_BINDING_ROLE_UNKNOWN", source_span, unknown)
    grouped = {
        role.role_id: tuple(
            binding for binding in bindings if binding.role_id == role.role_id)
        for role in schema.roles
    }
    for role in schema.roles:
        members = grouped[role.role_id]
        if not role.min_cardinality <= len(members) <= role.max_cardinality:
            _binding_fail("FRAME_ROLE_CARDINALITY_INVALID", source_span, role.role_id)
        if tuple(item.occurrence_index for item in members) != tuple(range(len(members))):
            _binding_fail("FRAME_ROLE_OCCURRENCE_SEQUENCE_INVALID",
                          source_span, role.role_id)
        for member in members:
            if member.child_frame is not None:
                if not set(member.child_frame.type_ids).intersection(role.allowed_type_ids):
                    _binding_fail("FRAME_ROLE_TYPE_INVALID", source_span, role.role_id)
                continue
            for concept in _binding_concepts(member):
                if concept.semantic_release != snapshot.release_sha256:
                    _binding_fail("FRAME_SEMANTIC_RELEASE_MISMATCH",
                                  source_span, role.role_id)
                abi = snapshot.abi_for_semantic(concept.semantic_id)
                if abi.index != concept.abi_index:
                    _binding_fail("FRAME_ABI_INDEX_MISMATCH", source_span, role.role_id)
                authoritative = next(
                    (item.concept.types for item in snapshot.concepts
                     if item.concept.semantic_id == concept.semantic_id),
                    None,
                )
                if (authoritative is not None
                        and tuple(concept.type_ids) != tuple(authoritative)):
                    _binding_fail("FRAME_CONCEPT_TYPE_AUTHORITY_MISMATCH",
                                  source_span, role.role_id)
                if not set(concept.type_ids).intersection(role.allowed_type_ids):
                    _binding_fail("FRAME_ROLE_TYPE_INVALID", source_span, role.role_id)

    rank = {role.role_id: index for index, role in enumerate(schema.roles)}
    return tuple(sorted(
        bindings,
        key=lambda item: (rank[item.role_id], item.occurrence_index),
    ))


def make_frame_instance(
    schema: FrameSchema,
    *,
    source_instance_id: str,
    structural_path: tuple[int, ...],
    source_span: SourceSpan,
    parent_occurrence_id: str | None,
    bindings: tuple[RoleOccurrence, ...],
    causal_prefix_end: int,
) -> FrameInstance:
    role_ids = {role.role_id for role in schema.roles}
    if any(binding.role_id not in role_ids for binding in bindings):
        _fail("FRAME_BINDING_ROLE_UNKNOWN")
    rank = {role.role_id: index for index, role in enumerate(schema.roles)}
    ordered = tuple(sorted(
        bindings, key=lambda item: (rank[item.role_id], item.occurrence_index)))
    return FrameInstance(
        frame_schema_id=schema.schema_id,
        frame_schema_revision=schema.revision,
        occurrence_id=occurrence_id(source_instance_id, structural_path),
        content_digest=content_digest(schema, ordered),
        source_instance_id=source_instance_id,
        structural_path=structural_path,
        source_span=source_span,
        parent_occurrence_id=parent_occurrence_id,
        bindings=ordered,
        causal_prefix_end=causal_prefix_end,
    )


def bind_frame_instance(
    schema: FrameSchema,
    snapshot: FrozenAtlasSnapshot,
    *,
    source_instance_id: str,
    structural_path: tuple[int, ...],
    source_span: SourceSpan,
    parent_occurrence_id: str | None,
    bindings: tuple[RoleOccurrence, ...],
    causal_prefix_end: int,
    declared_scope: str,
) -> FrameInstance:
    ordered = validate_frame_bindings(
        schema,
        snapshot,
        bindings=bindings,
        source_span=source_span,
        causal_prefix_end=causal_prefix_end,
        declared_scope=declared_scope,
    )
    return make_frame_instance(
        schema,
        source_instance_id=source_instance_id,
        structural_path=structural_path,
        source_span=source_span,
        parent_occurrence_id=parent_occurrence_id,
        bindings=ordered,
        causal_prefix_end=causal_prefix_end,
    )


def atomic_fallback(
    ast: object,
    *,
    source_instance_id: str,
    structural_path: tuple[int, ...],
    source_span: SourceSpan,
    parent_occurrence_id: str | None,
    causal_prefix_end: int,
) -> AtomicFrame:
    payload = _source_payload(ast)
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False)
    construct = source_ast_construct_id(ast)
    return AtomicFrame(
        occurrence_id=occurrence_id(source_instance_id, structural_path),
        content_digest=_digest({
            "ast_construct": construct,
            "source_payload": json.loads(canonical),
        }),
        source_instance_id=source_instance_id,
        structural_path=structural_path,
        source_span=source_span,
        parent_occurrence_id=parent_occurrence_id,
        ast_construct=construct,
        source_payload=canonical,
        causal_prefix_end=causal_prefix_end,
    )


def bind_ast_frames(
    ast: object,
    snapshot: FrozenAtlasSnapshot,
    *,
    schema: FrameSchema | None,
    source_instance_id: str,
    structural_path: tuple[int, ...] = (),
    source_span: SourceSpan,
    parent_occurrence_id: str | None = None,
    bindings: tuple[RoleOccurrence, ...] = (),
    causal_prefix_end: int,
    declared_scope: str | None = None,
) -> FrameTree:
    """Bind one native AST node or preserve it atomically when no schema is approved."""
    if schema is None:
        return FrameTree(atomic_fallback(
            ast,
            source_instance_id=source_instance_id,
            structural_path=structural_path,
            source_span=source_span,
            parent_occurrence_id=parent_occurrence_id,
            causal_prefix_end=causal_prefix_end,
        ))
    if source_ast_construct_id(ast) != schema.ast_construct:
        _fail("FRAME_AST_CONSTRUCT_MISMATCH")
    if isinstance(ast, Apply):
        if schema.ast_contract_sha256 is None:
            _binding_fail("FRAME_AST_CONTRACT_REQUIRED",
                          source_span, "<operator>")
        if ast.operator.contract_sha256 != schema.ast_contract_sha256:
            _binding_fail("FRAME_AST_CONTRACT_MISMATCH",
                          source_span, "<operator>")
    instance = bind_frame_instance(
        schema,
        snapshot,
        source_instance_id=source_instance_id,
        structural_path=structural_path,
        source_span=source_span,
        parent_occurrence_id=parent_occurrence_id,
        bindings=bindings,
        causal_prefix_end=causal_prefix_end,
        declared_scope=declared_scope or "",
    )
    return FrameTree(instance)


def validate_frame_tree(tree: FrameTree) -> FrameTree:
    if not isinstance(tree, FrameTree):
        _fail("FRAME_TREE_INVALID")
    root = tree.root
    if isinstance(root, AtomicFrame):
        if tree.children:
            _fail("FRAME_ATOMIC_CHILDREN_FORBIDDEN")
        return tree
    expected = {
        binding.child_frame.occurrence_id: binding.child_frame
        for binding in root.bindings if binding.child_frame is not None
    }
    actual = {
        child.root.occurrence_id: child.root
        for child in tree.children
    }
    if set(expected) != set(actual):
        _binding_fail("FRAME_CHILD_OCCURRENCE_MISMATCH",
                      root.source_span, "<child-frame>")
    for occurrence, reference in expected.items():
        child = actual[occurrence]
        if child.content_digest != reference.content_digest:
            _binding_fail("FRAME_CHILD_CONTENT_MISMATCH",
                          root.source_span, "<child-frame>")
    for child in tree.children:
        validate_frame_tree(child)
    return tree


def frame_schema_from_bytes(payload: bytes) -> FrameSchema:
    try:
        value = json.loads(payload)
        roles = tuple(RoleSpec(
            role_id=item["role_id"],
            allowed_type_ids=tuple(item["allowed_type_ids"]),
            min_cardinality=item["min_cardinality"],
            max_cardinality=item["max_cardinality"],
            schema_version=item["schema_version"],
        ) for item in value["roles"])
        schema = FrameSchema(
            schema_id=value["schema_id"],
            revision=value["revision"],
            ast_construct=value["ast_construct"],
            roles=roles,
            order_mode=value["order_mode"],
            scope=value["scope"],
            ast_contract_sha256=value.get("ast_contract_sha256"),
            schema_version=value["schema_version"],
        )
    except BilqisError:
        raise
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        _fail("FRAME_SCHEMA_SERIALIZATION_INVALID:" + type(error).__name__)
    if schema.canonical_bytes() != payload:
        _fail("FRAME_SCHEMA_SERIALIZATION_NONCANONICAL")
    return schema


def frame_instance_from_bytes(payload: bytes) -> FrameInstance:
    try:
        value = json.loads(payload)
        bindings = []
        for item in value["bindings"]:
            concept_value = item["concept"]
            concept = (ConceptRef(
                semantic_id=concept_value["semantic_id"],
                semantic_release=concept_value["semantic_release"],
                abi_index=concept_value["abi_index"],
                type_ids=tuple(concept_value["type_ids"]),
                source_reference=concept_value["source_reference"],
                schema_version=concept_value["schema_version"],
            ) if concept_value is not None else None)
            child_value = item["child_frame"]
            child = (ChildFrameRef(
                occurrence_id=child_value["occurrence_id"],
                content_digest=child_value["content_digest"],
                type_ids=tuple(child_value["type_ids"]),
                schema_version=child_value["schema_version"],
            ) if child_value is not None else None)
            alternatives = tuple(ConceptRef(
                semantic_id=alternative["semantic_id"],
                semantic_release=alternative["semantic_release"],
                abi_index=alternative["abi_index"],
                type_ids=tuple(alternative["type_ids"]),
                source_reference=alternative["source_reference"],
                schema_version=alternative["schema_version"],
            ) for alternative in item.get("alternatives", ()))
            bindings.append(RoleOccurrence(
                role_id=item["role_id"],
                occurrence_index=item["occurrence_index"],
                concept=concept,
                child_frame=child,
                state=BindingState(item.get("state", BindingState.VALUE.value)),
                alternatives=alternatives,
                schema_version=item["schema_version"],
            ))
        instance = FrameInstance(
            frame_schema_id=value["frame_schema_id"],
            frame_schema_revision=value["frame_schema_revision"],
            occurrence_id=value["occurrence_id"],
            content_digest=value["content_digest"],
            source_instance_id=value["source_instance_id"],
            structural_path=tuple(value["structural_path"]),
            source_span=SourceSpan(**value["source_span"]),
            parent_occurrence_id=value["parent_occurrence_id"],
            bindings=tuple(bindings),
            causal_prefix_end=value["causal_prefix_end"],
            schema_version=value["schema_version"],
        )
    except BilqisError:
        raise
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        _fail("FRAME_INSTANCE_SERIALIZATION_INVALID:" + type(error).__name__)
    if instance.canonical_bytes() != payload:
        _fail("FRAME_INSTANCE_SERIALIZATION_NONCANONICAL")
    return instance
