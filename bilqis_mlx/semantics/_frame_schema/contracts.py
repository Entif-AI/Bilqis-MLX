"""Occurrence-aware frame-schema contracts with source-owned authority."""
from __future__ import annotations
from .. import frame_schema as _facade

import hashlib
import json
import re

from ...errors import ErrorBus, SCHOOL


FRAME_SCHEMA_RECORD = "bilqis.semantic-frame-schema/v1"
FRAME_INSTANCE_RECORD = "bilqis.semantic-frame-instance/v2"
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


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)



def _bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")



def _digest(value: object) -> str:
    return hashlib.sha256(_facade._bytes(value)).hexdigest()



def source_node_digest(value: object) -> str:
    """Exact legacy source-node wire hash without importing assessment code."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"),
                   allow_nan=False).encode("utf-8")
    ).hexdigest()



def _occurrence_digest(source_instance_id: str, structural_path: tuple[int, ...]) -> str:
    return _facade._digest({
        "source_instance_id": source_instance_id,
        "structural_path": list(structural_path),
    })



def _text(value: object, reason: str) -> str:
    if not isinstance(value, str) or not value:
        _facade._fail(reason)
    return value
