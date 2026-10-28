"""Reversible compact and extended encodings for released semantic frames."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import re

from ..errors import ErrorBus, SEMANTIC_FRAME
from .atlas_projection import FrozenAtlasSnapshot
from .frame_schema import (
    AtomicFrame,
    BindingState,
    ChildFrameRef,
    ConceptRef,
    FrameInstance,
    FrameSchema,
    RoleOccurrence,
    RoleSpec,
    SourceSpan,
    frame_instance_from_bytes,
)


COMPACT_CODEC_ID = "bamf.frame-u64/v1"
SCHEMA_MAP_SCHEMA = "bilqis.frame-schema-tag-map/v1"
SCHEMA_TAG_ENTRY_SCHEMA = "bilqis.frame-schema-tag-entry/v1"
SLOT_TUPLE_SCHEMA = "bilqis.frame-slot-tuple/v1"
COMPACT_BYTES_SCHEMA = "bilqis.frame-u64-bytes/v1"
PACKED_FRAME_SCHEMA = "bilqis.packed-frame/v1"
EXTENDED_SLOT_SCHEMA = "bilqis.extended-frame-slot/v1"
EXTENDED_CODEC_ID = "bamf.frame-extended/v1"
ATOMIC_CODEC_ID = "bamf.frame-atomic/v1"

SLOT_COUNT = 4
SLOT_BITS = 13
SLOT_LIMIT = 1 << SLOT_BITS
SLOT_MASK = SLOT_LIMIT - 1
PRESENCE_SHIFT = SLOT_COUNT * SLOT_BITS
PRESENCE_MASK = (1 << SLOT_COUNT) - 1
SCHEMA_SHIFT = PRESENCE_SHIFT + SLOT_COUNT
SCHEMA_BITS = 4
SCHEMA_LIMIT = 1 << SCHEMA_BITS
SCHEMA_MASK = SCHEMA_LIMIT - 1
VERSION_SHIFT = SCHEMA_SHIFT + SCHEMA_BITS
VERSION_BITS = 4
VERSION_MASK = (1 << VERSION_BITS) - 1
CODEC_VERSION = 1
U64_BITS = 64
U64_LIMIT = 1 << U64_BITS
U64_BYTES = 8
UINT32_BITS = 32
UINT32_LIMIT = 1 << UINT32_BITS

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _fail(reason: str) -> None:
    ErrorBus.raise_(SEMANTIC_FRAME.CODEC.INVALID, reason=reason)


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n").encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


class PackDisposition(str, Enum):
    COMPACT = "COMPACT_V1"
    EXTENDED = "EXTENDED_V1"
    ATOMIC = "ATOMIC_V1"


class FallbackReason(str, Enum):
    COMPACT_ELIGIBLE = "COMPACT_ELIGIBLE"
    ATOMIC_FRAME = "ATOMIC_FRAME"
    SCHEMA_TAG_UNAVAILABLE = "SCHEMA_TAG_UNAVAILABLE"
    SCHEMA_NOT_FOUR_SINGULAR_ROLES = "SCHEMA_NOT_FOUR_SINGULAR_ROLES"
    SLOT_COUNT_NOT_FOUR = "SLOT_COUNT_NOT_FOUR"
    REPEATED_ROLE_OCCURRENCE = "REPEATED_ROLE_OCCURRENCE"
    NON_VALUE_BINDING = "NON_VALUE_BINDING"
    CHILD_FRAME = "CHILD_FRAME"
    INDEX_REQUIRES_UINT32 = "INDEX_REQUIRES_UINT32"


@dataclass(frozen=True, order=True)
class SchemaTagEntry:
    tag: int
    schema_id: str
    schema_revision: int
    schema_sha256: str
    schema_version: str = SCHEMA_TAG_ENTRY_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.tag) is not int or not 0 <= self.tag < SCHEMA_LIMIT
                or not isinstance(self.schema_id, str) or not self.schema_id
                or type(self.schema_revision) is not int or self.schema_revision < 1
                or not _SHA256.fullmatch(self.schema_sha256)
                or self.schema_version != SCHEMA_TAG_ENTRY_SCHEMA):
            _fail("FRAME_SCHEMA_TAG_ENTRY_INVALID")


@dataclass(frozen=True)
class SchemaTagMap:
    semantic_release: str
    entries: tuple[SchemaTagEntry, ...]
    schema_version: str = SCHEMA_MAP_SCHEMA

    def __post_init__(self) -> None:
        tags = tuple(item.tag for item in self.entries)
        identities = tuple(
            (item.schema_id, item.schema_revision) for item in self.entries)
        if (not _SHA256.fullmatch(self.semantic_release)
                or self.entries != tuple(sorted(self.entries))
                or len(tags) != len(set(tags))
                or len(identities) != len(set(identities))
                or self.schema_version != SCHEMA_MAP_SCHEMA):
            _fail("FRAME_SCHEMA_TAG_MAP_INVALID")

    @classmethod
    def from_schemas(
        cls,
        semantic_release: str,
        schemas: tuple[FrameSchema, ...],
    ) -> "SchemaTagMap":
        ordered = tuple(sorted(
            schemas,
            key=lambda item: (
                item.schema_id.encode("utf-8"),
                item.revision,
                hashlib.sha256(item.canonical_bytes()).digest(),
            ),
        ))
        if len(ordered) > SCHEMA_LIMIT:
            _fail("FRAME_SCHEMA_TAG_CAPACITY_EXCEEDED")
        identities = tuple((item.schema_id, item.revision) for item in ordered)
        if len(identities) != len(set(identities)):
            _fail("FRAME_SCHEMA_TAG_IDENTITY_DUPLICATE")
        return cls(
            semantic_release=semantic_release,
            entries=tuple(
                SchemaTagEntry(
                    tag=index,
                    schema_id=schema.schema_id,
                    schema_revision=schema.revision,
                    schema_sha256=hashlib.sha256(schema.canonical_bytes()).hexdigest(),
                )
                for index, schema in enumerate(ordered)
            ),
        )

    @property
    def digest(self) -> str:
        return _digest(asdict(self))

    def resolve(self, tag: int) -> SchemaTagEntry:
        if type(tag) is not int:
            _fail("FRAME_SCHEMA_TAG_INVALID")
        match = next((item for item in self.entries if item.tag == tag), None)
        if match is None:
            _fail("FRAME_SCHEMA_TAG_UNKNOWN")
        return match

    def tag_for(self, schema: FrameSchema) -> int | None:
        digest = hashlib.sha256(schema.canonical_bytes()).hexdigest()
        match = next((
            item for item in self.entries
            if item.schema_id == schema.schema_id
            and item.schema_revision == schema.revision
            and item.schema_sha256 == digest
        ), None)
        return None if match is None else match.tag


@dataclass(frozen=True)
class SlotTuple:
    indices: tuple[int, int, int, int]
    schema_tag: int
    schema: SchemaTagEntry
    presence_mask: int = PRESENCE_MASK
    codec_version: int = CODEC_VERSION
    codec_id: str = COMPACT_CODEC_ID
    schema_version: str = SLOT_TUPLE_SCHEMA

    def __post_init__(self) -> None:
        if (len(self.indices) != SLOT_COUNT
                or any(type(index) is not int or not 0 <= index < SLOT_LIMIT
                       for index in self.indices)
                or self.schema_tag != self.schema.tag
                or self.presence_mask != PRESENCE_MASK
                or self.codec_version != CODEC_VERSION
                or self.codec_id != COMPACT_CODEC_ID
                or self.schema_version != SLOT_TUPLE_SCHEMA):
            _fail("FRAME_SLOT_TUPLE_INVALID")


@dataclass(frozen=True)
class CompactFrameBytes:
    codec_id: str
    payload: bytes
    word_decimal: str
    schema_version: str = COMPACT_BYTES_SCHEMA

    def __post_init__(self) -> None:
        if (self.codec_id != COMPACT_CODEC_ID
                or not isinstance(self.payload, bytes)
                or len(self.payload) != U64_BYTES
                or not isinstance(self.word_decimal, str)
                or not self.word_decimal.isdecimal()
                or self.schema_version != COMPACT_BYTES_SCHEMA):
            _fail("FRAME_COMPACT_BYTES_INVALID")
        word = int.from_bytes(self.payload, "little", signed=False)
        if str(word) != self.word_decimal:
            _fail("FRAME_COMPACT_BYTES_WORD_MISMATCH")

    def json_value(self) -> dict[str, str]:
        return {
            "codec_id": self.codec_id,
            "word_decimal": self.word_decimal,
            "little_endian_hex": self.payload.hex(),
        }


@dataclass(frozen=True)
class ExtendedSlot:
    role_id: str
    occurrence_index: int
    state: str
    abi_indices: tuple[int, ...]
    semantic_ids: tuple[str, ...]
    child_occurrence_id: str | None
    child_content_digest: str | None
    child_type_ids: tuple[str, ...]
    schema_version: str = EXTENDED_SLOT_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.role_id, str) or not self.role_id
                or type(self.occurrence_index) is not int or self.occurrence_index < 0
                or self.state not in {item.value for item in BindingState}
                or len(self.abi_indices) != len(self.semantic_ids)
                or any(type(index) is not int or not 0 <= index < UINT32_LIMIT
                       for index in self.abi_indices)
                or any(not isinstance(item, str) or not item for item in self.semantic_ids)
                or ((self.child_occurrence_id is None)
                    != (self.child_content_digest is None))
                or (self.child_occurrence_id is not None
                    and not _SHA256.fullmatch(self.child_occurrence_id))
                or (self.child_content_digest is not None
                    and not _SHA256.fullmatch(self.child_content_digest))
                or any(not isinstance(item, str) or not item for item in self.child_type_ids)
                or self.schema_version != EXTENDED_SLOT_SCHEMA):
            _fail("FRAME_EXTENDED_SLOT_INVALID")


@dataclass(frozen=True)
class PackDecision:
    disposition: PackDisposition
    reason: FallbackReason
    schema_tag: int | None


@dataclass(frozen=True)
class PackedFrame:
    disposition: PackDisposition
    reason: FallbackReason
    codec_id: str
    semantic_release: str
    schema_map_sha256: str
    schema_id: str | None
    schema_revision: int | None
    schema_sha256: str | None
    schema_payload: bytes | None
    frame_payload: bytes
    compact_word: int | None
    extended_slots: tuple[ExtendedSlot, ...]
    schema_version: str = PACKED_FRAME_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.disposition, PackDisposition)
                or not isinstance(self.reason, FallbackReason)
                or not isinstance(self.codec_id, str) or not self.codec_id
                or not _SHA256.fullmatch(self.semantic_release)
                or not _SHA256.fullmatch(self.schema_map_sha256)
                or not isinstance(self.frame_payload, bytes)
                or not self.frame_payload
                or self.schema_version != PACKED_FRAME_SCHEMA):
            _fail("FRAME_PACKED_RECORD_INVALID")
        if self.disposition is PackDisposition.COMPACT:
            if (self.codec_id != COMPACT_CODEC_ID
                    or type(self.compact_word) is not int
                    or self.extended_slots
                    or self.schema_id is None
                    or self.schema_revision is None
                    or self.schema_sha256 is None
                    or self.schema_payload is None):
                _fail("FRAME_PACKED_COMPACT_INVALID")
        elif self.disposition is PackDisposition.EXTENDED:
            if (self.codec_id != EXTENDED_CODEC_ID
                    or self.compact_word is not None
                    or self.schema_id is None
                    or self.schema_revision is None
                    or self.schema_sha256 is None
                    or self.schema_payload is None):
                _fail("FRAME_PACKED_EXTENDED_INVALID")
        else:
            if (self.codec_id != ATOMIC_CODEC_ID
                    or self.compact_word is not None
                    or self.extended_slots
                    or any(value is not None for value in (
                        self.schema_id,
                        self.schema_revision,
                        self.schema_sha256,
                        self.schema_payload,
                    ))):
                _fail("FRAME_PACKED_ATOMIC_INVALID")


def pack4(indices: tuple[int, int, int, int], schema_tag: int) -> int:
    """Pack four complete 13-bit semantic indices into the exact BAMF v1 u64."""
    if not isinstance(indices, tuple) or len(indices) != SLOT_COUNT:
        _fail("FRAME_COMPACT_SLOT_COUNT_INVALID")
    if any(type(index) is not int or not 0 <= index < SLOT_LIMIT
           for index in indices):
        _fail("FRAME_COMPACT_INDEX_OUT_OF_RANGE")
    if type(schema_tag) is not int or not 0 <= schema_tag < SCHEMA_LIMIT:
        _fail("FRAME_COMPACT_SCHEMA_TAG_OUT_OF_RANGE")
    word = 0
    for slot, index in enumerate(indices):
        word |= index << (slot * SLOT_BITS)
    word |= PRESENCE_MASK << PRESENCE_SHIFT
    word |= schema_tag << SCHEMA_SHIFT
    word |= CODEC_VERSION << VERSION_SHIFT
    return word


def unpack4(word: int, schema_map: SchemaTagMap) -> SlotTuple:
    """Decode one exact compact word and bind its tag to one release-local schema."""
    if type(word) is not int or not 0 <= word < U64_LIMIT:
        _fail("FRAME_COMPACT_WORD_OUT_OF_RANGE")
    if not isinstance(schema_map, SchemaTagMap):
        _fail("FRAME_SCHEMA_TAG_MAP_REQUIRED")
    version = (word >> VERSION_SHIFT) & VERSION_MASK
    if version != CODEC_VERSION:
        _fail("FRAME_COMPACT_VERSION_MISMATCH")
    presence = (word >> PRESENCE_SHIFT) & PRESENCE_MASK
    if presence != PRESENCE_MASK:
        _fail("FRAME_COMPACT_PRESENCE_INVALID")
    schema_tag = (word >> SCHEMA_SHIFT) & SCHEMA_MASK
    schema = schema_map.resolve(schema_tag)
    indices = tuple(
        (word >> (slot * SLOT_BITS)) & SLOT_MASK
        for slot in range(SLOT_COUNT)
    )
    return SlotTuple(indices, schema_tag, schema)


def serialize_u64(word: int) -> CompactFrameBytes:
    if type(word) is not int or not 0 <= word < U64_LIMIT:
        _fail("FRAME_COMPACT_WORD_OUT_OF_RANGE")
    payload = word.to_bytes(U64_BYTES, "little", signed=False)
    return CompactFrameBytes(COMPACT_CODEC_ID, payload, str(word))


def deserialize_u64(encoded: CompactFrameBytes) -> int:
    if not isinstance(encoded, CompactFrameBytes):
        _fail("FRAME_COMPACT_BYTES_REQUIRED")
    return int.from_bytes(encoded.payload, "little", signed=False)


def _frame_semantic_release(
    frame: FrameInstance,
    schema_map: SchemaTagMap,
) -> str:
    releases = {
        concept.semantic_release
        for binding in frame.bindings
        for concept in (
            *((binding.concept,) if binding.concept is not None else ()),
            *binding.alternatives,
        )
    }
    if releases and releases != {schema_map.semantic_release}:
        _fail("FRAME_PACKED_SEMANTIC_RELEASE_MISMATCH")
    return schema_map.semantic_release


def classify_frame(
    frame: FrameInstance | AtomicFrame,
    schema: FrameSchema | None,
    schema_map: SchemaTagMap,
) -> PackDecision:
    """Select representation from typed frame properties, never exception control flow."""
    if not isinstance(schema_map, SchemaTagMap):
        _fail("FRAME_SCHEMA_TAG_MAP_REQUIRED")
    if isinstance(frame, AtomicFrame):
        if schema is not None:
            _fail("FRAME_ATOMIC_SCHEMA_FORBIDDEN")
        return PackDecision(
            PackDisposition.ATOMIC, FallbackReason.ATOMIC_FRAME, None)
    if not isinstance(frame, FrameInstance) or not isinstance(schema, FrameSchema):
        _fail("FRAME_PACK_INPUT_INVALID")
    if ((frame.frame_schema_id, frame.frame_schema_revision)
            != (schema.schema_id, schema.revision)):
        _fail("FRAME_PACK_SCHEMA_IDENTITY_MISMATCH")
    _frame_semantic_release(frame, schema_map)
    schema_tag = schema_map.tag_for(schema)
    if schema_tag is None:
        return PackDecision(
            PackDisposition.EXTENDED,
            FallbackReason.SCHEMA_TAG_UNAVAILABLE,
            None,
        )
    if (len(schema.roles) != SLOT_COUNT
            or any(role.min_cardinality != 1 or role.max_cardinality != 1
                   for role in schema.roles)):
        return PackDecision(
            PackDisposition.EXTENDED,
            FallbackReason.SCHEMA_NOT_FOUR_SINGULAR_ROLES,
            schema_tag,
        )
    if len(frame.bindings) != SLOT_COUNT:
        return PackDecision(
            PackDisposition.EXTENDED,
            FallbackReason.SLOT_COUNT_NOT_FOUR,
            schema_tag,
        )
    role_ids = tuple(binding.role_id for binding in frame.bindings)
    if len(role_ids) != len(set(role_ids)):
        return PackDecision(
            PackDisposition.EXTENDED,
            FallbackReason.REPEATED_ROLE_OCCURRENCE,
            schema_tag,
        )
    if any(binding.child_frame is not None for binding in frame.bindings):
        return PackDecision(
            PackDisposition.EXTENDED,
            FallbackReason.CHILD_FRAME,
            schema_tag,
        )
    if any(binding.state is not BindingState.VALUE or binding.concept is None
           for binding in frame.bindings):
        return PackDecision(
            PackDisposition.EXTENDED,
            FallbackReason.NON_VALUE_BINDING,
            schema_tag,
        )
    if any(binding.concept.abi_index >= SLOT_LIMIT for binding in frame.bindings):
        return PackDecision(
            PackDisposition.EXTENDED,
            FallbackReason.INDEX_REQUIRES_UINT32,
            schema_tag,
        )
    return PackDecision(
        PackDisposition.COMPACT,
        FallbackReason.COMPACT_ELIGIBLE,
        schema_tag,
    )


def _extended_slot(binding: RoleOccurrence) -> ExtendedSlot:
    concepts = (
        (binding.concept,) if binding.concept is not None
        else binding.alternatives
    )
    child = binding.child_frame
    return ExtendedSlot(
        role_id=binding.role_id,
        occurrence_index=binding.occurrence_index,
        state=binding.state.value,
        abi_indices=tuple(item.abi_index for item in concepts),
        semantic_ids=tuple(item.semantic_id for item in concepts),
        child_occurrence_id=None if child is None else child.occurrence_id,
        child_content_digest=None if child is None else child.content_digest,
        child_type_ids=() if child is None else child.type_ids,
    )


def _atomic_payload(frame: AtomicFrame) -> bytes:
    return _canonical_bytes(asdict(frame))


def _atomic_from_payload(payload: bytes) -> AtomicFrame:
    try:
        value = json.loads(payload)
        source_span = SourceSpan(**value["source_span"])
        frame = AtomicFrame(
            occurrence_id=value["occurrence_id"],
            content_digest=value["content_digest"],
            source_instance_id=value["source_instance_id"],
            structural_path=tuple(value["structural_path"]),
            source_span=source_span,
            parent_occurrence_id=value["parent_occurrence_id"],
            ast_construct=value["ast_construct"],
            source_payload=value["source_payload"],
            causal_prefix_end=value["causal_prefix_end"],
            schema_version=value["schema_version"],
        )
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        _fail("FRAME_ATOMIC_PAYLOAD_INVALID:" + type(error).__name__)
    if _atomic_payload(frame) != payload:
        _fail("FRAME_ATOMIC_PAYLOAD_NONCANONICAL")
    return frame


def pack_frame(
    frame: FrameInstance | AtomicFrame,
    *,
    schema: FrameSchema | None,
    schema_map: SchemaTagMap,
) -> PackedFrame:
    """Pack a frame for storage; source admission remains a readout concern."""
    decision = classify_frame(frame, schema, schema_map)
    if decision.disposition is PackDisposition.ATOMIC:
        return PackedFrame(
            disposition=decision.disposition,
            reason=decision.reason,
            codec_id=ATOMIC_CODEC_ID,
            semantic_release=schema_map.semantic_release,
            schema_map_sha256=schema_map.digest,
            schema_id=None,
            schema_revision=None,
            schema_sha256=None,
            schema_payload=None,
            frame_payload=_atomic_payload(frame),
            compact_word=None,
            extended_slots=(),
        )

    schema_payload = schema.canonical_bytes()
    schema_sha256 = hashlib.sha256(schema_payload).hexdigest()
    frame_payload = frame.canonical_bytes()
    if decision.disposition is PackDisposition.COMPACT:
        indices = tuple(binding.concept.abi_index for binding in frame.bindings)
        word = pack4(indices, decision.schema_tag)
        return PackedFrame(
            disposition=decision.disposition,
            reason=decision.reason,
            codec_id=COMPACT_CODEC_ID,
            semantic_release=schema_map.semantic_release,
            schema_map_sha256=schema_map.digest,
            schema_id=schema.schema_id,
            schema_revision=schema.revision,
            schema_sha256=schema_sha256,
            schema_payload=schema_payload,
            frame_payload=frame_payload,
            compact_word=word,
            extended_slots=(),
        )
    slots = tuple(_extended_slot(binding) for binding in frame.bindings)
    return PackedFrame(
        disposition=decision.disposition,
        reason=decision.reason,
        codec_id=EXTENDED_CODEC_ID,
        semantic_release=schema_map.semantic_release,
        schema_map_sha256=schema_map.digest,
        schema_id=schema.schema_id,
        schema_revision=schema.revision,
        schema_sha256=schema_sha256,
        schema_payload=schema_payload,
        frame_payload=frame_payload,
        compact_word=None,
        extended_slots=slots,
    )


def _validate_schema_sidecar(
    packed: PackedFrame,
    schema_map: SchemaTagMap,
) -> FrameSchema | None:
    if packed.semantic_release != schema_map.semantic_release:
        _fail("FRAME_PACKED_RELEASE_MISMATCH")
    if packed.schema_map_sha256 != schema_map.digest:
        _fail("FRAME_PACKED_SCHEMA_MAP_MISMATCH")
    if packed.disposition is PackDisposition.ATOMIC:
        return None
    try:
        value = json.loads(packed.schema_payload)
        schema = FrameSchema(
            schema_id=value["schema_id"],
            revision=value["revision"],
            ast_construct=value["ast_construct"],
            roles=tuple(
                RoleSpec(
                    role_id=item["role_id"],
                    allowed_type_ids=tuple(item["allowed_type_ids"]),
                    min_cardinality=item["min_cardinality"],
                    max_cardinality=item["max_cardinality"],
                    schema_version=item["schema_version"],
                )
                for item in value["roles"]
            ),
            order_mode=value["order_mode"],
            scope=value["scope"],
            ast_contract_sha256=value.get("ast_contract_sha256"),
            schema_version=value["schema_version"],
        )
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        _fail("FRAME_PACKED_SCHEMA_PAYLOAD_INVALID:" + type(error).__name__)
    canonical = schema.canonical_bytes()
    if (canonical != packed.schema_payload
            or hashlib.sha256(canonical).hexdigest() != packed.schema_sha256
            or (schema.schema_id, schema.revision)
            != (packed.schema_id, packed.schema_revision)):
        _fail("FRAME_PACKED_SCHEMA_IDENTITY_MISMATCH")
    if packed.disposition is PackDisposition.COMPACT:
        decoded = unpack4(packed.compact_word, schema_map)
        if ((decoded.schema.schema_id, decoded.schema.schema_revision,
             decoded.schema.schema_sha256)
                != (schema.schema_id, schema.revision, packed.schema_sha256)):
            _fail("FRAME_PACKED_COMPACT_SCHEMA_MISMATCH")
    return schema


def _validate_extended_slots(
    frame: FrameInstance,
    slots: tuple[ExtendedSlot, ...],
) -> None:
    expected = tuple(_extended_slot(binding) for binding in frame.bindings)
    if slots != expected:
        _fail("FRAME_EXTENDED_SLOT_SIDECAR_MISMATCH")


def unpack_frame(
    packed: PackedFrame,
    *,
    schema_map: SchemaTagMap,
) -> FrameInstance | AtomicFrame:
    if not isinstance(packed, PackedFrame):
        _fail("FRAME_PACKED_RECORD_REQUIRED")
    _validate_schema_sidecar(packed, schema_map)
    if packed.disposition is PackDisposition.ATOMIC:
        return _atomic_from_payload(packed.frame_payload)
    frame = frame_instance_from_bytes(packed.frame_payload)
    if packed.disposition is PackDisposition.COMPACT:
        decoded = unpack4(packed.compact_word, schema_map)
        sidecar_indices = tuple(
            binding.concept.abi_index for binding in frame.bindings)
        if decoded.indices != sidecar_indices:
            _fail("FRAME_COMPACT_SLOT_SIDECAR_MISMATCH")
    else:
        _validate_extended_slots(frame, packed.extended_slots)
    return frame


def role_index(
    packed: PackedFrame,
    role_id: str,
    occurrence_index: int,
    *,
    schema_map: SchemaTagMap,
    snapshot: FrozenAtlasSnapshot,
) -> int:
    """Return one neural-readout ABI index through the same path for both codecs."""
    frame = unpack_frame(packed, schema_map=schema_map)
    if not isinstance(frame, FrameInstance):
        _fail("FRAME_READOUT_ATOMIC_FORBIDDEN")
    match = next((
        binding for binding in frame.bindings
        if (binding.role_id, binding.occurrence_index)
        == (role_id, occurrence_index)
    ), None)
    if match is None:
        _fail("FRAME_READOUT_ROLE_UNKNOWN")
    if (match.state is not BindingState.VALUE
            or match.concept is None
            or match.child_frame is not None):
        _fail("FRAME_READOUT_SLOT_NONCONCEPT")
    concept = match.concept
    if (snapshot.release_sha256 != packed.semantic_release
            or concept.semantic_release != packed.semantic_release):
        _fail("FRAME_READOUT_RELEASE_MISMATCH")
    held_ids = {
        row.semantic_id for row in snapshot.source_hold_census()
        if row.semantic_id is not None
    }
    if concept.semantic_id in held_ids:
        _fail("FRAME_READOUT_SEMANTIC_HELD")
    lookup = dict(snapshot.semantic_lookup)
    if concept.semantic_id not in lookup:
        _fail("FRAME_READOUT_SEMANTIC_NOT_IN_ABI")
    index = lookup[concept.semantic_id]
    if index != concept.abi_index:
        _fail("FRAME_READOUT_ABI_INDEX_MISMATCH")
    entry = snapshot.abi(index)
    if not entry.active:
        _fail("FRAME_READOUT_INDEX_INACTIVE")
    return index
