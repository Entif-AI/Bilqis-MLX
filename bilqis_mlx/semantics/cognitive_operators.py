"""Pure, source-qualified cognitive operators. No assessment or neural imports.

The source frontier, not an operand's self-declared type, admits task-visible
facts. The frame gate owns role visibility; finite domains own numeric bounds.
This module never creates a source grant, allocates a semantic token, or
evaluates an independent answer key.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
import hashlib
from pathlib import Path
import re

from ..errors import ErrorBus, SEMANTIC_FRAME
from .context_eligibility import (
    ContextEligibility, ContextHold, ContextPolicy, SourceFrontier, SourceGrant,
    TaskScope, check_context_eligibility,
)
from .core import Signature
from .domains import FiniteDomain, ValueCodec, contract_digest
from .frame_schema import BindingState, ConceptRef, FrameInstance


VALUE_SCHEMA = "bilqis.cognitive-typed-value/v1"
SOURCE_OPERAND_SCHEMA = "bilqis.cognitive-source-operand/v1"
OPERATOR_SCHEMA = "bilqis.cognitive-operator-spec/v1"
REGISTRY_SCHEMA = "bilqis.cognitive-operator-registry/v1"
BINDING_SCHEMA = "bilqis.cognitive-operator-binding/v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_UNITS = {"s": 1, "min": 60, "h": 3600}


def _invalid(reason: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<operator>", span_start=0, span_end=0,
    )


class ValueState(str, Enum):
    VALUE = "VALUE"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


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


@dataclass(frozen=True)
class CognitiveOperatorSpec:
    operator_id: str
    signature: Signature
    applicability: str
    version: str
    implementation_sha256: str
    effect: str = "PURE"
    schema_version: str = OPERATOR_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.operator_id, str) or not self.operator_id
                or not isinstance(self.signature, Signature)
                or not isinstance(self.applicability, str) or not self.applicability
                or not isinstance(self.version, str) or not self.version
                or not isinstance(self.implementation_sha256, str)
                or not _SHA.fullmatch(self.implementation_sha256)
                or self.effect != "PURE"
                or self.schema_version != OPERATOR_SCHEMA):
            _invalid("BAMF_OPERATOR_SPEC_INVALID")


@dataclass(frozen=True)
class OperatorRegistry:
    semantic_release: str
    specs: tuple[CognitiveOperatorSpec, ...]
    schema_version: str = REGISTRY_SCHEMA

    def __post_init__(self) -> None:
        ids = tuple(spec.operator_id for spec in self.specs)
        if (not isinstance(self.semantic_release, str)
                or not _SHA.fullmatch(self.semantic_release)
                or not isinstance(self.specs, tuple)
                or any(not isinstance(spec, CognitiveOperatorSpec) for spec in self.specs)
                or not self.specs or len(ids) != len(set(ids))
                or self.schema_version != REGISTRY_SCHEMA):
            _invalid("BAMF_OPERATOR_REGISTRY_INVALID")

    def resolve(self, operator_id: str) -> CognitiveOperatorSpec:
        for spec in self.specs:
            if spec.operator_id == operator_id:
                declared = next((
                    (inputs, output, applicability)
                    for name, inputs, output, applicability in _DECLARATIONS
                    if name == operator_id
                ), None)
                if (declared is None
                        or spec.signature != Signature(declared[0], declared[1])
                        or spec.applicability != declared[2]
                        or spec.version != "v1"):
                    _invalid("BAMF_OPERATOR_DECLARATION_DRIFT")
                if spec.implementation_sha256 != _implementation_digest(operator_id):
                    _invalid("BAMF_OPERATOR_IMPLEMENTATION_DRIFT")
                return spec
        _invalid("BAMF_OPERATOR_NOT_REGISTERED")


@dataclass(frozen=True)
class OperatorBinding:
    task: TaskScope
    frontier: SourceFrontier
    policy: ContextPolicy
    registry: OperatorRegistry
    operands: tuple[SourceOperand, ...]
    frames: tuple[ContextEligibility, ...] = ()
    numeric_domain: FiniteDomain | None = None
    numeric_source_handle: str | None = None
    schema_version: str = BINDING_SCHEMA

    def __post_init__(self) -> None:
        handles = tuple(item.typed.source_handle for item in self.operands)
        if (not isinstance(self.task, TaskScope)
                or not isinstance(self.frontier, SourceFrontier)
                or not isinstance(self.policy, ContextPolicy)
                or not isinstance(self.registry, OperatorRegistry)
                or not isinstance(self.operands, tuple)
                or any(not isinstance(item, SourceOperand) for item in self.operands)
                or len(handles) != len(set(handles))
                or not isinstance(self.frames, tuple)
                or any(not isinstance(item, ContextEligibility) for item in self.frames)
                or (self.numeric_domain is None) != (self.numeric_source_handle is None)
                or (self.numeric_domain is not None
                    and not isinstance(self.numeric_domain, FiniteDomain))
                or self.schema_version != BINDING_SCHEMA):
            _invalid("BAMF_OPERATOR_BINDING_INVALID")


def _check_grant(
    handle: str, evidence: str, binding: OperatorBinding,
) -> None:
    task, frontier, policy = binding.task, binding.frontier, binding.policy
    grant = next((item for item in frontier.grants
                  if item.source_handle == handle), None)
    if grant is None:
        _invalid("BAMF_OPERATOR_SOURCE_GRANT_MISSING")
    if (frontier.rights_epoch != policy.rights_epoch
            or grant.evidence_digest != evidence
            or grant.semantic_release != task.semantic_release
            or grant.principal_id != task.principal_id
            or grant.tenant_id != task.tenant_id
            or grant.rights_epoch != frontier.rights_epoch
            or grant.correction_generation != frontier.correction_generation
            or grant.revoked or task.purpose is None
            or task.purpose not in policy.allowed_purposes
            or task.purpose not in grant.permitted_purposes
            or task.jurisdiction not in policy.allowed_jurisdictions
            or task.jurisdiction not in grant.permitted_jurisdictions
            or task.scope not in policy.allowed_scopes
            or task.scope not in grant.permitted_scopes
            or grant.source_regime not in policy.allowed_regimes
            or grant.observed_at > task.observed_frontier
            or grant.effective_from > task.effective_time
            or (grant.effective_until is not None
                and task.effective_time >= grant.effective_until)):
        _invalid("BAMF_OPERATOR_SOURCE_GRANT_INELIGIBLE")


def _approved_frames(binding: OperatorBinding) -> dict[str, ContextEligibility]:
    if not binding.frames:
        return {}
    result = check_context_eligibility(
        binding.frames, binding.task, binding.frontier, binding.policy)
    if isinstance(result, ContextHold):
        _invalid("BAMF_OPERATOR_CONTEXT_HELD")
    return {item.frame_handle: item for item in binding.frames}


def _authorize_inputs(
    values: tuple[TypedValue, ...], binding: OperatorBinding,
) -> None:
    if binding.registry.semantic_release != binding.task.semantic_release:
        _invalid("BAMF_OPERATOR_RELEASE_MISMATCH")
    approved = _approved_frames(binding)
    visible = {operand.typed: operand for operand in binding.operands}
    for operand in binding.operands:
        if (operand.typed.semantic_release != binding.task.semantic_release
                or operand.visible_at_prefix > binding.task.causal_prefix_end):
            _invalid("BAMF_OPERATOR_INVISIBLE_OPERAND")
        _check_grant(
            operand.typed.source_handle, source_operand_digest(operand), binding)
    for value in values:
        if not isinstance(value, TypedValue):
            _invalid("BAMF_OPERATOR_INPUT_NOT_TYPED")
        if value.semantic_release != binding.task.semantic_release:
            _invalid("BAMF_OPERATOR_INPUT_RELEASE_MISMATCH")
        if value in visible:
            continue
        if value.type_name == "FrameHandle":
            envelope = approved.get(value.value)
            if (envelope is not None
                    and value.source_handle == envelope.source_handle):
                continue
        if value.type_name == "ConceptRef":
            if any(
                member.source_handle == value.source_handle
                and frame_binding.concept == value.value
                for envelope in approved.values()
                if isinstance(envelope.frame, FrameInstance)
                for member in envelope.members
                for frame_binding in envelope.frame.bindings
                if frame_binding.key == member.key
            ):
                continue
        _invalid("BAMF_OPERATOR_OPERAND_NOT_ADMITTED")


def _number_domain(binding: OperatorBinding) -> FiniteDomain | None:
    domain = binding.numeric_domain
    if domain is None:
        return None
    if (domain.type_name != "Number" or not domain.closed
            or domain.codec is not ValueCodec.DECIMAL_INTEGER_TEXT):
        _invalid("BAMF_OPERATOR_NUMERIC_DOMAIN_INVALID")
    _check_grant(
        binding.numeric_source_handle,
        numeric_domain_digest(domain, binding.task.semantic_release),
        binding,
    )
    return domain


def _frame(handle: str, binding: OperatorBinding) -> FrameInstance | None:
    for envelope in binding.frames:
        if envelope.frame_handle == handle:
            return envelope.frame if isinstance(envelope.frame, FrameInstance) else None
    return None


_UNSUPPORTED = object()
_UNKNOWN = object()
_NONE = object()


def _compute(operator_id: str, values: tuple[object, ...],
             binding: OperatorBinding) -> object:
    if operator_id == "ROLE_LOOKUP":
        handle, role, index = values
        frame = _frame(handle, binding)
        if frame is None:
            return _UNSUPPORTED
        occupant = next((item for item in frame.bindings
                         if item.key == (role, index)), None)
        if occupant is None or occupant.state is BindingState.UNKNOWN:
            return _UNKNOWN
        if occupant.state is BindingState.NONE:
            return _NONE
        return occupant.concept if occupant.concept is not None else _UNSUPPORTED
    if operator_id == "SAME_IDENTITY":
        left, right = values
        return (left.semantic_id, left.semantic_release, left.abi_index) == (
            right.semantic_id, right.semantic_release, right.abi_index)
    if operator_id == "TYPE_OF":
        return values[0].type_ids
    if operator_id == "HAS_TYPE":
        return values[1] in values[0].type_ids
    if operator_id == "MEMBER_OF":
        return values[0] in values[1]
    if operator_id == "BOOL_NOT":
        return not values[0]
    if operator_id == "BOOL_AND":
        return values[0] and values[1]
    if operator_id == "BOOL_OR":
        return values[0] or values[1]
    if operator_id == "BOOL_XOR":
        return values[0] != values[1]
    if operator_id == "BOOL_IMPLIES":
        return not values[0] or values[1]
    if operator_id == "BOOL_IFF":
        return values[0] == values[1]
    if operator_id == "IS_OCCURRED":
        return values[0] == "OCCURRED"
    if operator_id == "PARENT_OF":
        parent, child = (_frame(handle, binding) for handle in values)
        return (child.parent_occurrence_id == parent.occurrence_id
                if parent is not None and child is not None else _UNSUPPORTED)
    if operator_id == "BEFORE":
        left, right = (_frame(handle, binding) for handle in values)
        return (left.source_span.end <= right.source_span.start
                if left is not None and right is not None else _UNSUPPORTED)
    if operator_id == "UNIT_CONVERT":
        duration, target = values
        edge = next((
            item.typed.value for item in binding.operands
            if item.kind is SourceKind.ADMITTED_KNOWLEDGE
            and item.typed.type_name == "UnitConversion"
            and item.typed.state is ValueState.VALUE
            and item.typed.value.from_unit == duration.unit
            and item.typed.value.to_unit == target
        ), None)
        if edge is None:
            return _UNSUPPORTED
        quantity = (Fraction(duration.numerator, duration.denominator)
                    * Fraction(edge.numerator, edge.denominator))
        return Duration(quantity.numerator, quantity.denominator, target)
    if operator_id == "COUNT":
        return len(values[0])
    if operator_id == "SUCC":
        return values[0] + 1
    if operator_id in {"ADD", "SUB", "MUL", "DIV", "MOD", "EQ", "LT", "LE"}:
        left, right = values
        if operator_id == "ADD":
            return left + right
        if operator_id == "SUB":
            return left - right
        if operator_id == "MUL":
            return left * right
        if operator_id == "EQ":
            return left == right
        if operator_id == "LT":
            return left < right
        if operator_id == "LE":
            return left <= right
        if right == 0:
            return _UNSUPPORTED
        if operator_id == "MOD":
            return left % right
        return left // right if left % right == 0 else _UNSUPPORTED
    _invalid("BAMF_OPERATOR_UNIMPLEMENTED")


def _implementation_digest(operator_id: str) -> str:
    return hashlib.sha256(
        operator_id.encode("utf-8") + b"\0" + Path(__file__).read_bytes()
    ).hexdigest()


_DECLARATIONS = (
    ("ROLE_LOOKUP", ("FrameHandle", "RoleId", "Index"), "ConceptRef", "VISIBLE_FRAME"),
    ("SAME_IDENTITY", ("ConceptRef", "ConceptRef"), "Boolean", "SOURCE_IDENTITY"),
    ("TYPE_OF", ("ConceptRef",), "TypeSet", "SOURCE_TYPES"),
    ("HAS_TYPE", ("ConceptRef", "TypeName"), "Boolean", "SOURCE_TYPES"),
    ("MEMBER_OF", ("Entity", "EntitySet"), "Boolean", "SOURCE_SET"),
    ("BOOL_NOT", ("Boolean",), "Boolean", "SOURCE_BOOLEAN"),
    ("BOOL_AND", ("Boolean", "Boolean"), "Boolean", "SOURCE_BOOLEAN"),
    ("BOOL_OR", ("Boolean", "Boolean"), "Boolean", "SOURCE_BOOLEAN"),
    ("BOOL_XOR", ("Boolean", "Boolean"), "Boolean", "SOURCE_BOOLEAN"),
    ("BOOL_IMPLIES", ("Boolean", "Boolean"), "Boolean", "SOURCE_BOOLEAN"),
    ("BOOL_IFF", ("Boolean", "Boolean"), "Boolean", "SOURCE_BOOLEAN"),
    ("ADD", ("Number", "Number"), "Number", "FINITE_NUMBER"),
    ("SUB", ("Number", "Number"), "Number", "FINITE_NUMBER"),
    ("MUL", ("Number", "Number"), "Number", "FINITE_NUMBER"),
    ("DIV", ("Number", "Number"), "Number", "FINITE_NUMBER"),
    ("MOD", ("Number", "Number"), "Number", "FINITE_NUMBER"),
    ("EQ", ("Number", "Number"), "Boolean", "FINITE_NUMBER"),
    ("LT", ("Number", "Number"), "Boolean", "FINITE_NUMBER"),
    ("LE", ("Number", "Number"), "Boolean", "FINITE_NUMBER"),
    ("SUCC", ("Number",), "Number", "FINITE_NUMBER"),
    ("COUNT", ("EntitySet",), "Number", "FINITE_NUMBER"),
    ("UNIT_CONVERT", ("Duration", "UnitName"), "Duration", "EXACT_DURATION"),
    ("PARENT_OF", ("FrameHandle", "FrameHandle"), "Boolean", "VISIBLE_FRAME"),
    ("BEFORE", ("FrameHandle", "FrameHandle"), "Boolean", "VISIBLE_FRAME"),
    ("IS_OCCURRED", ("EventStatus",), "Boolean", "SOURCE_EVENT_STATUS"),
)


def default_registry(semantic_release: str) -> OperatorRegistry:
    return OperatorRegistry(
        semantic_release,
        tuple(CognitiveOperatorSpec(
            operator_id, Signature(inputs, output), applicability, "v1",
            _implementation_digest(operator_id),
        ) for operator_id, inputs, output, applicability in _DECLARATIONS),
    )


def execute_pure(
    operator_id: str,
    typed_inputs: tuple[TypedValue, ...],
    binding: OperatorBinding,
) -> TypedValue:
    """Execute one source-qualified PURE operator, never an evaluation oracle."""
    if not isinstance(binding, OperatorBinding) or not isinstance(typed_inputs, tuple):
        _invalid("BAMF_OPERATOR_CALL_INVALID")
    if any(not isinstance(item, TypedValue) for item in typed_inputs):
        _invalid("BAMF_OPERATOR_INPUT_NOT_TYPED")
    spec = binding.registry.resolve(operator_id)
    if tuple(item.type_name for item in typed_inputs) != spec.signature.inputs:
        _invalid("BAMF_OPERATOR_SIGNATURE_MISMATCH")
    _authorize_inputs(typed_inputs, binding)
    release = binding.task.semantic_release
    def unresolved(state: ValueState) -> TypedValue:
        return TypedValue(spec.signature.output, None, release, state=state)

    if any(item.state is ValueState.UNKNOWN for item in typed_inputs):
        return unresolved(ValueState.UNKNOWN)
    if any(item.state is not ValueState.VALUE for item in typed_inputs):
        return unresolved(ValueState.UNSUPPORTED)
    domain = None
    if spec.applicability == "FINITE_NUMBER":
        domain = _number_domain(binding)
        if domain is None:
            return unresolved(ValueState.UNSUPPORTED)
        for item in typed_inputs:
            if item.type_name == "Number":
                try:
                    domain.encode(item.value)
                except ValueError:
                    return unresolved(ValueState.UNSUPPORTED)
    result = _compute(operator_id, tuple(item.value for item in typed_inputs), binding)
    if result is _UNKNOWN:
        return unresolved(ValueState.UNKNOWN)
    if result is _NONE:
        return unresolved(ValueState.NONE)
    if result is _UNSUPPORTED:
        return unresolved(ValueState.UNSUPPORTED)
    if domain is not None and spec.signature.output == "Number":
        try:
            domain.encode(result)
        except ValueError:
            return unresolved(ValueState.UNSUPPORTED)
    return TypedValue(spec.signature.output, result, release)
