"""Shared schema identities and validation errors for source atom handoffs."""
from __future__ import annotations

from enum import Enum
import re

from ...errors import ErrorBus, SEMANTIC_FRAME


SOURCE_ROW_WITNESS_SCHEMA = "bilqis.source-row-token-witness/v1"
SOURCE_ATOM_BINDING_SCHEMA = "bilqis.source-atom-semantic-binding/v1"
SOURCE_ATOM_HANDOFF_SCHEMA = "bilqis.source-atom-semantic-handoff/v1"
SOURCE_ATOM_RIGHTS_SCHEMA = "bilqis.source-atom-rights-state/v1"
SOURCE_ATOM_MAPPING_SCHEMA = "bilqis.source-atom-mapping-record/v1"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def invalid(reason: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<source-atom-binding>",
        span_start=0, span_end=0,
    )


def is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value)


class AtomBindingDisposition(str, Enum):
    BOUND = "BOUND"
    SOURCE_HELD = "SOURCE_HELD"
    UNMAPPED = "UNMAPPED"
