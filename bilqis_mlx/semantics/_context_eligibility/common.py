"""Shared context-admission schemas and validation primitives."""
from __future__ import annotations

import hashlib
import json
import re

from ...errors import ErrorBus, SEMANTIC_FRAME

ELIGIBILITY_SCHEMA = "bilqis.context-eligibility/v1"
MEMBER_SCHEMA = "bilqis.context-member/v1"
GRANT_SCHEMA = "bilqis.context-source-grant/v1"
FRONTIER_SCHEMA = "bilqis.context-source-frontier/v1"
TASK_SCHEMA = "bilqis.context-task-scope/v1"
POLICY_SCHEMA = "bilqis.context-policy/v1"
APPROVED_FRAME_SCHEMA = "bilqis.context-approved-frame/v1"
ELIGIBLE_CONTEXT_SCHEMA = "bilqis.eligible-context/v1"
CONTEXT_HOLD_SCHEMA = "bilqis.context-hold/v1"
PROJECTION_SCHEMA = "bilqis.context-approved-projection/v1"
C09_INVALIDATION_SCHEMA = "bilqis.c09-context-invalidation/v1"
CONTEXT_TRANSITION_SCHEMA = "bilqis.context-transition/v1"
PUBLIC_FORMAL = "PUBLIC_FORMAL"
MAX_CONTEXT_HOLD_DIAGNOSTICS = 16
JOIN_PAIR_ARITY = 2
MIN_JOIN_SET_ARITY = 3
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<context>", span_start=0, span_end=0,
    )


def _digest(value: object) -> str:
    return hashlib.sha256(
        (json.dumps(value, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    ).hexdigest()


def _name(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _epoch(value: object) -> bool:
    return type(value) is int and value >= 0


def _names(value: object) -> bool:
    return (isinstance(value, tuple)
            and all(_name(item) for item in value)
            and value == tuple(sorted(set(value))))
