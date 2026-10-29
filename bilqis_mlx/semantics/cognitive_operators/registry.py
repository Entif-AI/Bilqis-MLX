"""Released pure operator declarations and immutable source contracts."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
from pathlib import Path
from .. import numeric as released_numeric
from ..context_eligibility import ContextEligibility, ContextPolicy, SourceFrontier, TaskScope
from ..core import Signature
from ..domains import FiniteDomain, contract_digest
from .common import OPERATOR_SCHEMA, REGISTRY_SCHEMA, BINDING_SCHEMA, _NATIVE_NUMERIC, _SHA, _invalid
from .types import SourceOperand

@dataclass(frozen=True)
class CognitiveOperatorSpec:
    operator_id: str
    signature: Signature
    applicability: str
    version: str
    implementation_sha256: str
    semantic_release: str
    source_reference: str
    source_contract_sha256: str
    effect: str = "PURE"
    schema_version: str = OPERATOR_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.operator_id, str) or not self.operator_id
                or not isinstance(self.signature, Signature)
                or not isinstance(self.applicability, str) or not self.applicability
                or not isinstance(self.version, str) or not self.version
                or not isinstance(self.implementation_sha256, str)
                or not _SHA.fullmatch(self.implementation_sha256)
                or not isinstance(self.semantic_release, str)
                or not _SHA.fullmatch(self.semantic_release)
                or not isinstance(self.source_reference, str)
                or not self.source_reference
                or not isinstance(self.source_contract_sha256, str)
                or not _SHA.fullmatch(self.source_contract_sha256)
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
                if declared is None:
                    _invalid("BAMF_OPERATOR_DECLARATION_DRIFT")
                declared_inputs, declared_output, declared_applicability = declared
                if (spec.signature != Signature(
                            declared_inputs, declared_output)
                        or spec.applicability != declared_applicability
                        or spec.version != "v1"
                        or spec.semantic_release != self.semantic_release):
                    _invalid("BAMF_OPERATOR_DECLARATION_DRIFT")
                source_reference, source_digest = _source_contract(
                    operator_id, spec.signature, spec.version)
                if (spec.source_reference != source_reference
                        or spec.source_contract_sha256 != source_digest):
                    _invalid("BAMF_OPERATOR_SOURCE_CONTRACT_DRIFT")
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


def _implementation_digest(operator_id: str) -> str:
    module_files = sorted(Path(__file__).resolve().parent.glob("*.py"))
    source = b"".join(
        path.name.encode("utf-8") + b"\0" + path.read_bytes()
        for path in module_files
    )
    return hashlib.sha256(operator_id.encode("utf-8") + b"\0" + source).hexdigest()


def _source_contract(
    operator_id: str, signature: Signature, version: str,
) -> tuple[str, str]:
    """Existing released numeric ABI or a separately grant-required formal law."""
    if operator_id in _NATIVE_NUMERIC:
        operation = released_numeric.OPERATIONS.get(operator_id)
        if operation is None or operation.signature != signature:
            _invalid("BAMF_OPERATOR_NATIVE_SOURCE_MISSING")
        return (
            "bilqis_mlx.semantics.numeric:" + operation.symbol,
            operation.contract_sha256,
        )
    return (
        "public-formal-law:" + operator_id,
        contract_digest({
            "authority": "PUBLIC_FORMAL_LAW_REQUIRES_SOURCE_GRANT",
            "operator_id": operator_id,
            "signature": signature,
            "version": version,
        }),
    )


def operator_grant_digest(spec: CognitiveOperatorSpec) -> str:
    """Evidence a source authority must explicitly admit for this operator."""
    return contract_digest({
        "schema": "bilqis.cognitive-operator-grant/v1",
        "operator": spec,
    })


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
        tuple(
            CognitiveOperatorSpec(
                operator_id, Signature(inputs, output), applicability, "v1",
                _implementation_digest(operator_id), semantic_release,
                *_source_contract(operator_id, Signature(inputs, output), "v1"),
            )
            for operator_id, inputs, output, applicability in _DECLARATIONS
        ),
    )


