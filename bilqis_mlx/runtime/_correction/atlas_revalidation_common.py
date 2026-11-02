"""Shared validation primitives for correction revalidation."""
from __future__ import annotations

import json
import re

from ..errors import ErrorBus, SCHOOL
from ..semantics.cognitive_dependencies import DependencyRef


CORRECTION_EVENT_SCHEMA = "bilqis.c09.correction-event/v3"
REVALIDATED_ARTIFACT_SCHEMA = "bilqis.c09.revalidated-artifact/v3"
REVALIDATION_FRONTIER_SCHEMA = "bilqis.c09.revalidation-frontier/v1"
REVALIDATION_TASK_SCHEMA = "bilqis.c09.revalidation-task/v1"
REVALIDATION_QUEUE_SCHEMA = "bilqis.c09.revalidation-queue/v1"
STATE_TRANSITION_SCHEMA = "bilqis.c09.state-transition/v3"
REVALIDATION_PROGRESS_SCHEMA = "bilqis.c09.revalidation-progress/v1"
SOURCE_AUTHORITY_SCOPE_SCHEMA = "bilqis.c09.source-authority-scope/v1"
SOURCE_AUTHORITY_KEY_SCHEMA = "bilqis.c09.source-authority-key/v2"
SOURCE_AUTHORITY_REGISTRY_SCHEMA = "bilqis.c09.source-authority-registry/v2"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ED25519_SIGNATURE = re.compile(r"[0-9a-f]{128}\Z")
MAX_REVALIDATION_PRIORITY = 4


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_REVALIDATION.INVALID, reason=reason)


def _name(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _digest(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _time(value: object) -> bool:
    return type(value) is int and value >= 0


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _refs_payload(refs: tuple[DependencyRef, ...]) -> list[dict[str, str]]:
    return [
        {"kind": ref.kind.value, "key": ref.key,
         "schema_version": ref.schema_version}
        for ref in refs
    ]
