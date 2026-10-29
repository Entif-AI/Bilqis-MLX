"""Pure B07 motif-key canonicalization and candidate-only slot planning.

The A03 FrameInstance v2 source contract is consumed through narrow read-only
protocols until its reviewed branch reaches unified. This module neither copies
the A03 validator nor allocates MLX parameters or publishes a generation.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Protocol

from bilqis_mlx.errors import ErrorBus, SCHOOL


KEY_SCHEMA = "bilqis.motif-key/v1"
MEMBER_SCHEMA = "bilqis.motif-member/v1"
MANIFEST_SCHEMA = "bilqis.motif-manifest/v1"
PLAN_SCHEMA = "bilqis.motif-allocation-plan/v1"
VIEW_SCHEMA = "bilqis.motif-candidate-view/v1"
FRAME_INPUT_SCHEMA = "bilqis.motif-frame-input/v1"
FRAME_INSTANCE_SCHEMA = "bilqis.semantic-frame-instance/v2"
FRAME_SCHEMA = "bilqis.semantic-frame-schema/v1"
CONCEPT_SCHEMA = "bilqis.semantic-concept-ref/v1"
CHILD_SCHEMA = "bilqis.semantic-child-frame-ref/v1"
MAX_CANDIDATE_ALLOCATIONS = 64
INITIAL_MOTIF_CAPACITY = 16384
MAX_MOTIF_CAPACITY = 65536
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_STATES = frozenset({"VALUE", "NONE", "UNKNOWN", "ALTERNATIVES"})


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


class FrameInstanceV2(Protocol):
    frame_schema_id: str
    frame_schema_revision: int
    schema_role_order: tuple[str, ...]
    occurrence_id: str
    content_digest: str
    bindings: tuple
    schema_version: str


class FrameSchemaV1(Protocol):
    schema_id: str
    revision: int
    ast_construct: str
    ast_contract_sha256: str | None
    roles: tuple
    order_mode: str
    scope: str
    schema_version: str


@dataclass(frozen=True)
class MotifFrameInput:
    frame: FrameInstanceV2
    schema: FrameSchemaV1
    schema_version: str = FRAME_INPUT_SCHEMA


@dataclass(frozen=True)
class MotifMember:
    role_id: str
    occurrence_index: int
    state: str
    target_kind: str
    target_ids: tuple[str, ...]
    type_ids: tuple[str, ...]
    schema_version: str = MEMBER_SCHEMA

    def __post_init__(self) -> None:
        if (not self.role_id or type(self.occurrence_index) is not int
                or self.occurrence_index < 0 or self.state not in _STATES
                or not self.target_kind
                or not isinstance(self.target_ids, tuple)
                or not isinstance(self.type_ids, tuple)
                or self.type_ids != tuple(sorted(set(self.type_ids)))
                or any(not isinstance(value, str) or not value
                       for value in (*self.target_ids, *self.type_ids))
                or self.schema_version != MEMBER_SCHEMA):
            _invalid("BAMF_MOTIF_MEMBER_INVALID")


@dataclass(frozen=True)
class MotifKey:
    kind: str
    semantic_release: str
    frame_schema_id: str
    frame_schema_revision: int
    members: tuple[MotifMember, ...]
    relation_signature: str
    scope: str
    schema_version: str = KEY_SCHEMA

    def __post_init__(self) -> None:
        target_kinds = (
            {"CONCEPT", "CHILD_FRAME", "ALTERNATIVE_CONCEPTS", "NONE", "UNKNOWN"}
            if self.kind == "EXACT" else
            {"TYPE", "CHILD_TYPE", "ALTERNATIVE_TYPES", "NONE", "UNKNOWN"}
        )
        if (self.kind not in {"EXACT", "STRUCTURAL"}
                or not _SHA.fullmatch(self.semantic_release)
                or not self.frame_schema_id
                or type(self.frame_schema_revision) is not int
                or self.frame_schema_revision < 1
                or not self.members
                or not isinstance(self.members, tuple)
                or any(type(member) is not MotifMember
                       or member.target_kind not in target_kinds
                       for member in self.members)
                or not _SHA.fullmatch(self.relation_signature)
                or not self.scope
                or self.schema_version != KEY_SCHEMA):
            _invalid("BAMF_MOTIF_KEY_INVALID")

    def canonical_bytes(self) -> bytes:
        return _bytes(asdict(self))

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True)
class MotifSlot:
    slot_id: int
    key: MotifKey

    def __post_init__(self) -> None:
        if (type(self.slot_id) is not int or self.slot_id < 0
                or type(self.key) is not MotifKey):
            _invalid("BAMF_MOTIF_SLOT_INVALID")


def _bucket(key: MotifKey) -> str:
    """Only an index hint. Full canonical key equality is mandatory on hit."""
    return key.digest[:16]


@dataclass(frozen=True)
class MotifManifest:
    semantic_release: str
    slots: tuple[MotifSlot, ...] = ()
    capacity: int = INITIAL_MOTIF_CAPACITY
    schema_version: str = MANIFEST_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.slots, tuple)
                or any(type(item) is not MotifSlot for item in self.slots)):
            _invalid("BAMF_MOTIF_MANIFEST_INVALID")
        indices = tuple(item.slot_id for item in self.slots)
        if (not _SHA.fullmatch(self.semantic_release)
                or type(self.capacity) is not int
                or not INITIAL_MOTIF_CAPACITY <= self.capacity <= MAX_MOTIF_CAPACITY
                or self.capacity % INITIAL_MOTIF_CAPACITY
                or indices != tuple(range(len(self.slots)))
                or len({item.key for item in self.slots}) != len(self.slots)
                or len(self.slots) > self.capacity
                or any(item.key.semantic_release != self.semantic_release
                       for item in self.slots)
                or self.schema_version != MANIFEST_SCHEMA):
            _invalid("BAMF_MOTIF_MANIFEST_INVALID")

    @property
    def digest(self) -> str:
        return _digest(asdict(self))

    def lookup(self, key: MotifKey) -> int | None:
        if key.semantic_release != self.semantic_release:
            _invalid("BAMF_MOTIF_FOREIGN_RELEASE")
        bucket = _bucket(key)
        for item in self.slots:
            if _bucket(item.key) == bucket and item.key == key:
                return item.slot_id
        return None


@dataclass(frozen=True)
class MotifBudget:
    new_slot_limit: int = MAX_CANDIDATE_ALLOCATIONS

    def __post_init__(self) -> None:
        if (type(self.new_slot_limit) is not int
                or not 0 <= self.new_slot_limit <= MAX_CANDIDATE_ALLOCATIONS):
            _invalid("BAMF_MOTIF_BUDGET_INVALID")


@dataclass(frozen=True)
class MotifAllocationPlan:
    parent_manifest_digest: str
    allocated: tuple[MotifSlot, ...]
    pending: tuple[MotifKey, ...]
    observed_uses: tuple[tuple[str, int], ...]
    schema_version: str = PLAN_SCHEMA


@dataclass(frozen=True)
class MotifMatch:
    occurrence_id: str
    exact_key_digest: str
    structural_key_digest: str
    disposition: str
    slot_id: int | None


@dataclass(frozen=True)
class CandidateMotifView:
    matches: tuple[MotifMatch, ...]
    plan: MotifAllocationPlan
    schema_version: str = VIEW_SCHEMA


def _state(binding) -> str:
    value = getattr(binding.state, "value", binding.state)
    if value not in _STATES:
        _invalid("BAMF_MOTIF_BINDING_STATE_INVALID")
    return value


def _member(binding, role, release: str, structural: bool) -> MotifMember:
    state = _state(binding)
    if (binding.role_id != role.role_id
            or type(binding.occurrence_index) is not int
            or binding.occurrence_index < 0):
        _invalid("BAMF_MOTIF_ROLE_INVALID")
    concept = binding.concept
    child = binding.child_frame
    if state == "VALUE":
        if (concept is None) == (child is None):
            _invalid("BAMF_MOTIF_TARGET_INVALID")
        if concept is not None:
            if (concept.schema_version != CONCEPT_SCHEMA
                    or concept.semantic_release != release
                    or not concept.semantic_id
                    or not concept.source_reference
                    or not set(concept.type_ids).intersection(role.allowed_type_ids)):
                _invalid("BAMF_MOTIF_CONCEPT_SOURCE_INVALID")
            kind = "TYPE" if structural else "CONCEPT"
            ids = tuple(concept.type_ids) if structural else (concept.semantic_id,)
            types = tuple(concept.type_ids)
        else:
            if (child.schema_version != CHILD_SCHEMA
                    or not _SHA.fullmatch(child.content_digest)
                    or not set(child.type_ids).intersection(role.allowed_type_ids)):
                _invalid("BAMF_MOTIF_CHILD_SOURCE_INVALID")
            kind = "CHILD_TYPE" if structural else "CHILD_FRAME"
            ids = tuple(child.type_ids) if structural else (child.content_digest,)
            types = tuple(child.type_ids)
    elif state == "ALTERNATIVES":
        alternatives = tuple(binding.alternatives)
        if not alternatives or concept is not None or child is not None:
            _invalid("BAMF_MOTIF_ALTERNATIVES_INVALID")
        if any(item.schema_version != CONCEPT_SCHEMA
               or item.semantic_release != release
               or not set(item.type_ids).intersection(role.allowed_type_ids)
               for item in alternatives):
            _invalid("BAMF_MOTIF_ALTERNATIVE_SOURCE_INVALID")
        kind = "ALTERNATIVE_TYPES" if structural else "ALTERNATIVE_CONCEPTS"
        ids = (tuple(json.dumps(item.type_ids, separators=(",", ":"))
                     for item in alternatives)
               if structural else tuple(item.semantic_id for item in alternatives))
        types = ()
    else:
        if concept is not None or child is not None or binding.alternatives:
            _invalid("BAMF_MOTIF_UNKNOWN_TARGET_INVALID")
        kind, ids, types = state, (), ()
    return MotifMember(binding.role_id, binding.occurrence_index,
                       state, kind, ids, types)


def motif_keys(source: MotifFrameInput, release: str) -> tuple[MotifKey, MotifKey]:
    """Derive exact and typed structural identities from the A03-owned wire shape."""
    if (not isinstance(source, MotifFrameInput)
            or source.schema_version != FRAME_INPUT_SCHEMA
            or not _SHA.fullmatch(release)):
        _invalid("BAMF_MOTIF_FRAME_INPUT_INVALID")
    frame, schema = source.frame, source.schema
    try:
        role_order = tuple(role.role_id for role in schema.roles)
        bindings = tuple(frame.bindings)
        if (frame.schema_version != FRAME_INSTANCE_SCHEMA
                or schema.schema_version != FRAME_SCHEMA
                or (frame.frame_schema_id, frame.frame_schema_revision)
                != (schema.schema_id, schema.revision)
                or frame.schema_role_order != role_order
                or not schema.scope or not schema.ast_construct
                or not _SHA.fullmatch(frame.occurrence_id)
                or not _SHA.fullmatch(frame.content_digest)
                or not bindings):
            _invalid("BAMF_MOTIF_FRAME_SCHEMA_MISMATCH")
        role_map = {role.role_id: role for role in schema.roles}
        if len(role_map) != len(role_order):
            _invalid("BAMF_MOTIF_ROLE_ORDER_INVALID")
        rank = {role: index for index, role in enumerate(role_order)}
        keys = tuple((binding.role_id, binding.occurrence_index)
                     for binding in bindings)
        if (any(role not in role_map for role, _ in keys)
                or keys != tuple(sorted(keys, key=lambda k: (rank[k[0]], k[1])))
                or len(keys) != len(set(keys))):
            _invalid("BAMF_MOTIF_ROLE_ORDER_INVALID")
        exact = tuple(_member(binding, role_map[binding.role_id], release, False)
                      for binding in bindings)
        structural = tuple(_member(binding, role_map[binding.role_id], release, True)
                           for binding in bindings)
        relations = tuple(
            (binding.role_id, binding.occurrence_index,
             binding.child_frame.content_digest)
            for binding in bindings if binding.child_frame is not None)
        signature = _digest((
            schema.ast_construct, schema.ast_contract_sha256,
            schema.order_mode, relations))
    except (AttributeError, TypeError, ValueError) as error:
        _invalid("BAMF_MOTIF_FRAME_INPUT_INVALID:" + type(error).__name__)
    return (
        MotifKey("EXACT", release, schema.schema_id, schema.revision,
                 exact, signature, schema.scope),
        MotifKey("STRUCTURAL", release, schema.schema_id, schema.revision,
                 structural, signature, schema.scope),
    )


def prepare_motifs(
    frames: tuple[MotifFrameInput, ...],
    parent_manifest: MotifManifest,
    budget: MotifBudget,
) -> CandidateMotifView:
    """Plan structural-before-instance slots without mutating accepted state."""
    if (not isinstance(frames, tuple)
            or any(not isinstance(item, MotifFrameInput) for item in frames)
            or type(parent_manifest) is not MotifManifest
            or type(budget) is not MotifBudget):
        _invalid("BAMF_MOTIF_PREPARATION_INVALID")
    pairs = tuple(motif_keys(item, parent_manifest.semantic_release)
                  for item in frames)
    observed = Counter(key for pair in pairs for key in pair)
    existing = {slot.key: slot.slot_id for slot in parent_manifest.slots}
    missing_structural = {
        structural for exact, structural in pairs
        if exact not in existing and structural not in existing}
    missing_exact = {exact for exact, _ in pairs if exact not in existing}
    sort_key = lambda key: (-observed[key], key.digest)
    ordered = (
        *sorted(missing_structural, key=sort_key),
        *sorted(missing_exact, key=sort_key),
    )
    available = min(
        budget.new_slot_limit,
        parent_manifest.capacity - len(parent_manifest.slots))
    allocated = tuple(
        MotifSlot(len(parent_manifest.slots) + index, key)
        for index, key in enumerate(ordered[:available]))
    pending = tuple(ordered[available:])
    candidate = dict(existing)
    candidate.update((item.key, item.slot_id) for item in allocated)
    matches = []
    for source, (exact, structural) in zip(frames, pairs):
        if exact in candidate:
            kind, slot = "EXACT", candidate[exact]
        elif structural in candidate:
            kind, slot = "STRUCTURAL", candidate[structural]
        else:
            kind, slot = "FACTORIZED_FALLBACK", None
        matches.append(MotifMatch(
            source.frame.occurrence_id, exact.digest, structural.digest,
            kind, slot))
    return CandidateMotifView(
        tuple(matches),
        MotifAllocationPlan(
            parent_manifest.digest, allocated, pending,
            tuple(sorted((key.digest, count) for key, count in observed.items()))),
    )
