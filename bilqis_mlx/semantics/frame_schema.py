"""Released, occurrence-aware semantic frame records over the native typed AST."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re

from ..errors import ErrorBus, SCHOOL
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

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ORDER_MODES = frozenset({"ORDERED", "UNORDERED"})


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


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
    schema_version: str = FRAME_SCHEMA_RECORD

    def __post_init__(self) -> None:
        role_ids = tuple(role.role_id for role in self.roles)
        if (not isinstance(self.schema_id, str) or not self.schema_id
                or type(self.revision) is not int or self.revision < 1
                or not isinstance(self.ast_construct, str) or not self.ast_construct
                or not self.roles or len(role_ids) != len(set(role_ids))
                or self.order_mode not in _ORDER_MODES
                or not isinstance(self.scope, str) or not self.scope
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
    schema_version: str = CHILD_FRAME_REF_RECORD

    def __post_init__(self) -> None:
        if (not _SHA256.fullmatch(self.occurrence_id)
                or not _SHA256.fullmatch(self.content_digest)
                or self.schema_version != CHILD_FRAME_REF_RECORD):
            _fail("FRAME_CHILD_REF_INVALID")


@dataclass(frozen=True)
class RoleOccurrence:
    role_id: str
    occurrence_index: int
    concept: ConceptRef | None = None
    child_frame: ChildFrameRef | None = None
    schema_version: str = ROLE_OCCURRENCE_RECORD

    def __post_init__(self) -> None:
        if (not isinstance(self.role_id, str) or not self.role_id
                or type(self.occurrence_index) is not int or self.occurrence_index < 0
                or (self.concept is None) == (self.child_frame is None)
                or self.schema_version != ROLE_OCCURRENCE_RECORD):
            _fail("FRAME_ROLE_OCCURRENCE_INVALID")

    @property
    def key(self) -> tuple[str, int]:
        return self.role_id, self.occurrence_index

    def content_identity(self) -> dict:
        if self.concept is not None:
            target = {"kind": "concept", "value": self.concept.content_identity()}
        else:
            target = {
                "kind": "child-frame",
                "content_digest": self.child_frame.content_digest,
            }
        return {
            "role_id": self.role_id,
            "occurrence_index": self.occurrence_index,
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
                or self.bindings != tuple(sorted(
                    self.bindings, key=lambda item: item.key))
                or type(self.causal_prefix_end) is not int or self.causal_prefix_end < 0
                or self.schema_version != FRAME_INSTANCE_RECORD):
            _fail("FRAME_INSTANCE_INVALID")

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


def ast_construct_id(expression: Expression) -> str:
    """Name native AST constructors without inventing a second expression tree."""
    if isinstance(expression, Literal):
        return "literal:" + expression.type_name
    if isinstance(expression, Apply):
        return "apply:" + expression.operator.symbol
    _fail("FRAME_NATIVE_AST_CONSTRUCT_INVALID")


def native_ast_content_digest(expression: Expression) -> str:
    """Reuse the existing semantic AST's canonical content identity."""
    return expression_digest(expression)


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
    return _digest({
        "source_instance_id": source_instance_id,
        "structural_path": list(structural_path),
    })


def content_digest(
    schema: FrameSchema,
    bindings: tuple[RoleOccurrence, ...],
) -> str:
    return _digest({
        "frame_schema_id": schema.schema_id,
        "frame_schema_revision": schema.revision,
        "bindings": [
            binding.content_identity()
            for binding in sorted(bindings, key=lambda item: item.key)
        ],
    })


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
    ordered = tuple(sorted(bindings, key=lambda item: item.key))
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
            schema_version=value["schema_version"],
        )
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
            child = (ChildFrameRef(**item["child_frame"])
                     if item["child_frame"] is not None else None)
            bindings.append(RoleOccurrence(
                role_id=item["role_id"],
                occurrence_index=item["occurrence_index"],
                concept=concept,
                child_frame=child,
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
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        _fail("FRAME_INSTANCE_SERIALIZATION_INVALID:" + type(error).__name__)
    if instance.canonical_bytes() != payload:
        _fail("FRAME_INSTANCE_SERIALIZATION_NONCANONICAL")
    return instance
