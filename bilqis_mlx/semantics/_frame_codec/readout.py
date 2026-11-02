"""Frame codec readout."""
from __future__ import annotations

from ..atlas_projection import FrozenAtlasSnapshot
from ..frame_schema import BindingState, FrameInstance
from .primitives import _fail
from .schema_tags import SchemaTagMap
from .packed import PackedFrame
from .unpacking import unpack_frame


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
