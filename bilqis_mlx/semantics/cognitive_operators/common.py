"""Shared operator validation and source-ABI constants."""
from __future__ import annotations
import re
from ...errors import ErrorBus, SEMANTIC_FRAME

VALUE_SCHEMA = "bilqis.cognitive-typed-value/v1"
SOURCE_OPERAND_SCHEMA = "bilqis.cognitive-source-operand/v1"
OPERATOR_SCHEMA = "bilqis.cognitive-operator-spec/v1"
REGISTRY_SCHEMA = "bilqis.cognitive-operator-registry/v1"
BINDING_SCHEMA = "bilqis.cognitive-operator-binding/v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_UNITS = {"s": 1, "min": 60, "h": 3600}
_NATIVE_NUMERIC = frozenset({
    "ADD", "SUB", "MUL", "DIV", "EQ", "LT", "LE", "SUCC",
})
_SOURCE_INAPPLICABLE = frozenset({
    "NUMERIC_LITERAL_OUTSIDE_SOURCE_ABI",
    "NUMERIC_EXACT_DIVISION_UNDEFINED",
})


def _invalid(reason: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<operator>", span_start=0, span_end=0,
    )

