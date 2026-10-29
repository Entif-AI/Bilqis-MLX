"""Structural boundary to A07's source-owned operator registry.

Concrete operators, typed values and their implementations belong to A07.
"""
from typing import Any, Mapping, Protocol, runtime_checkable
from bilqis_mlx.semantics.core import Signature


@runtime_checkable
class TypedValue(Protocol):
    type_name: str
    value: Any


@runtime_checkable
class CognitiveOperatorSpec(Protocol):
    operator_id: str
    signature: Signature
    implementation_sha256: str
    effect: str
    kind: str
    source_binding: Mapping[str, Any]


@runtime_checkable
class OperatorRegistry(Protocol):
    def require(self, operator_id: str) -> CognitiveOperatorSpec: ...
