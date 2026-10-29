"""Typed source operands, values and exact unit quantities."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from ..domains import FiniteDomain, contract_digest
from ..frame_schema import ConceptRef
from .common import VALUE_SCHEMA, SOURCE_OPERAND_SCHEMA, _SHA, _UNITS, _invalid

class ValueState(str, Enum):
    VALUE = "VALUE"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"
    UNRESOLVED = "UNRESOLVED"


class SourceKind(str, Enum):
    TASK_VISIBLE = "TASK_VISIBLE"
    ADMITTED_KNOWLEDGE = "ADMITTED_KNOWLEDGE"


@dataclass(frozen=True)
class Duration:
    numerator: int
    denominator: int
    unit: str

    def __post_init__(self) -> None:
        if (type(self.numerator) is not int or type(self.denominator) is not int
                or self.numerator < 0 or self.denominator <= 0
                or self.unit not in _UNITS):
            _invalid("BAMF_OPERATOR_DURATION_INVALID")
        rational = Fraction(self.numerator, self.denominator)
        object.__setattr__(self, "numerator", rational.numerator)
        object.__setattr__(self, "denominator", rational.denominator)


@dataclass(frozen=True)
class UnitConversion:
    """An admitted exact unit edge, not an unqualified runtime conversion."""
    from_unit: str
    to_unit: str
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if (self.from_unit not in _UNITS or self.to_unit not in _UNITS
                or type(self.numerator) is not int or self.numerator <= 0
                or type(self.denominator) is not int or self.denominator <= 0
                or Fraction(self.numerator, self.denominator)
                != Fraction(_UNITS[self.from_unit], _UNITS[self.to_unit])):
            _invalid("BAMF_OPERATOR_UNIT_EDGE_INVALID")
        rational = Fraction(self.numerator, self.denominator)
        object.__setattr__(self, "numerator", rational.numerator)
        object.__setattr__(self, "denominator", rational.denominator)


@dataclass(frozen=True)
class TypedValue:
    type_name: str
    value: object
    semantic_release: str
    source_handle: str | None = None
    state: ValueState = ValueState.VALUE
    schema_version: str = VALUE_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.type_name, str) or not self.type_name
                or not isinstance(self.semantic_release, str)
                or not _SHA.fullmatch(self.semantic_release)
                or (self.source_handle is not None
                    and (not isinstance(self.source_handle, str)
                         or not self.source_handle))
                or not isinstance(self.state, ValueState)
                or self.schema_version != VALUE_SCHEMA):
            _invalid("BAMF_OPERATOR_TYPED_VALUE_INVALID")
        if self.state is not ValueState.VALUE:
            if self.value is not None:
                _invalid("BAMF_OPERATOR_NONVALUE_HAS_PAYLOAD")
            return
        validators = {
            "Boolean": lambda v: type(v) is bool,
            "Number": lambda v: type(v) is int,
            "Index": lambda v: type(v) is int and v >= 0,
            "Entity": lambda v: isinstance(v, str) and bool(v),
            "RoleId": lambda v: isinstance(v, str) and bool(v),
            "TypeName": lambda v: isinstance(v, str) and bool(v),
            "UnitName": lambda v: isinstance(v, str) and v in _UNITS,
            "EventStatus": lambda v: v in ("PLANNED", "OCCURRED"),
            "FrameHandle": lambda v: isinstance(v, str) and bool(v),
            "ConceptRef": lambda v: isinstance(v, ConceptRef)
            and v.semantic_release == self.semantic_release,
            "EntitySet": lambda v: isinstance(v, tuple)
            and all(isinstance(x, str) and bool(x) for x in v)
            and v == tuple(sorted(set(v))),
            "TypeSet": lambda v: isinstance(v, tuple)
            and all(isinstance(x, str) and bool(x) for x in v)
            and v == tuple(sorted(set(v))),
            "Duration": lambda v: isinstance(v, Duration),
            "UnitConversion": lambda v: isinstance(v, UnitConversion),
        }
        if self.type_name not in validators or not validators[self.type_name](self.value):
            _invalid("BAMF_OPERATOR_TYPED_PAYLOAD_INVALID")


@dataclass(frozen=True)
class SourceOperand:
    typed: TypedValue
    kind: SourceKind
    source_reference: str
    visible_at_prefix: int
    schema_version: str = SOURCE_OPERAND_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.typed, TypedValue)
                or not self.typed.source_handle
                or not isinstance(self.kind, SourceKind)
                or not isinstance(self.source_reference, str)
                or not self.source_reference
                or type(self.visible_at_prefix) is not int
                or self.visible_at_prefix < 0
                or self.schema_version != SOURCE_OPERAND_SCHEMA):
            _invalid("BAMF_OPERATOR_SOURCE_OPERAND_INVALID")


def source_operand_digest(operand: SourceOperand) -> str:
    """Source-grant evidence for one exact value, provenance and visibility."""
    return contract_digest(operand)


def numeric_domain_digest(domain: FiniteDomain, release: str) -> str:
    return contract_digest({
        "schema": "bilqis.cognitive-numeric-domain-grant/v1",
        "semantic_release": release,
        "domain": domain,
    })

