"""Frame codec atomic."""
from __future__ import annotations

from dataclasses import asdict
import json

from ..frame_schema import AtomicFrame, SourceSpan
from .primitives import _fail, _canonical_bytes


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
