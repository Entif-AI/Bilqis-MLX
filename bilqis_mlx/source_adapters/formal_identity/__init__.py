"""Source-owned formal coordinates for existing Factory capabilities."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from bilqis_mlx.grade_b_oracle import CONNECTIVES, VERSION as BOOLEAN_ORACLE
from bilqis_mlx.live_grade_b import constructor_digest as boolean_provider_digest
from bilqis_mlx.live_grade_c import PLANS, provider_implementation_digest as numeric_provider_digest
from bilqis_mlx.numeric_curriculum import ORACLE as NUMERIC_ORACLE


_BOOLEAN_ADAPTER = "source.micro.boolean-connectives/v1"
_BOOLEAN_COMPOSITE_ADAPTER = "source.micro.boolean-composite/v1"
_BOOLEAN_IDENTIFICATION_ADAPTER = "source.micro.boolean-identification/v1"
_NUMERIC_ADAPTER = "source.finite-numeric/v2"
_WORLD_ADAPTER = "source.bamf.qualified-world/v1"
_WORLD_OPERATOR_COORDINATES = MappingProxyType({
    "WORLD.IS_OCCURRED": ("ithkuil:LEXSENSE-294d00be074a56", "IS_OCCURRED"),
})
_WORLD_NON_OPERATOR_CAPABILITIES = frozenset({
    "WORLD.ACTOR_OF",
    "WORLD.BEFORE",
    "WORLD.DIRECT_CAUSE",
})


@dataclass(frozen=True)
class SourceFormalAuthority:
    semantic_root: str
    operator_id: str
    generator_id: str
    accepted_oracle_ids: tuple[str, ...]
    implementation_sha256: str


class OperatorDispositionKind(str, Enum):
    OPERATOR = "OPERATOR"
    NON_OPERATOR = "NON_OPERATOR"


@dataclass(frozen=True)
class SourceOperatorDisposition:
    capability_id: str
    source_adapter_id: str
    kind: OperatorDispositionKind
    operator_id: str | None
    semantic_root: str | None
    generator_id: str
    accepted_oracle_ids: tuple[str, ...]
    implementation_sha256: str

    def __post_init__(self) -> None:
        operator = self.kind is OperatorDispositionKind.OPERATOR
        if (not all(isinstance(value, str) and value for value in (
                self.capability_id, self.source_adapter_id, self.generator_id,
                self.implementation_sha256))
                or not isinstance(self.kind, OperatorDispositionKind)
                or type(self.accepted_oracle_ids) is not tuple
                or not self.accepted_oracle_ids
                or any(not isinstance(value, str) or not value
                       for value in self.accepted_oracle_ids)
                or operator != (self.operator_id is not None)
                or operator != (self.semantic_root is not None)
                or (self.operator_id is not None
                    and (not isinstance(self.operator_id, str) or not self.operator_id))
                or (self.semantic_root is not None
                    and (not isinstance(self.semantic_root, str) or not self.semantic_root))):
            raise ValueError("SOURCE_OPERATOR_DISPOSITION_INVALID")


def _disposition_from_descriptor(
        capability_id, descriptor, *, operator_id=None, semantic_root=None):
    kind = (OperatorDispositionKind.OPERATOR
            if operator_id is not None else OperatorDispositionKind.NON_OPERATOR)
    return SourceOperatorDisposition(
        capability_id=capability_id,
        source_adapter_id=descriptor.adapter_id,
        kind=kind,
        operator_id=operator_id,
        semantic_root=semantic_root,
        generator_id=descriptor.generator_id,
        accepted_oracle_ids=descriptor.accepted_oracle_ids,
        implementation_sha256=descriptor.implementation_sha256,
    )


def _local_capability_id(capability_id: str) -> str:
    return capability_id.rsplit(".", 1)[-1]


def _numeric_non_operator_disposition(
        capability_id: str, source_adapter_id: str) -> SourceOperatorDisposition | None:
    if source_adapter_id != _NUMERIC_ADAPTER:
        return None
    matches = tuple(
        plan for plan in PLANS
        if _local_capability_id(plan.capability) == _local_capability_id(capability_id))
    if len(matches) != 1 or matches[0].operation != "NUMBER":
        return None
    return SourceOperatorDisposition(
        capability_id=capability_id,
        source_adapter_id=source_adapter_id,
        kind=OperatorDispositionKind.NON_OPERATOR,
        operator_id=None,
        semantic_root=None,
        generator_id="bilqis_mlx.numeric_curriculum.draw_numeric",
        accepted_oracle_ids=(NUMERIC_ORACLE,),
        implementation_sha256=numeric_provider_digest(),
    )


def _derived_boolean_non_operator_disposition(
        capability_id: str, source_adapter_id: str) -> SourceOperatorDisposition | None:
    if source_adapter_id == _BOOLEAN_COMPOSITE_ADAPTER:
        from bilqis_mlx import boolean_composite
        if capability_id != boolean_composite.CAPABILITY:
            return None
        return SourceOperatorDisposition(
            capability_id=capability_id,
            source_adapter_id=source_adapter_id,
            kind=OperatorDispositionKind.NON_OPERATOR,
            operator_id=None,
            semantic_root=None,
            generator_id=boolean_composite.GENERATOR,
            accepted_oracle_ids=(BOOLEAN_ORACLE, boolean_composite.ORACLE),
            implementation_sha256=boolean_composite.constructor_digest(),
        )
    if source_adapter_id != _BOOLEAN_IDENTIFICATION_ADAPTER:
        return None
    from bilqis_mlx import boolean_composite, boolean_identification
    if capability_id != boolean_identification.CAPABILITY:
        return None
    return SourceOperatorDisposition(
        capability_id=capability_id,
        source_adapter_id=source_adapter_id,
        kind=OperatorDispositionKind.NON_OPERATOR,
        operator_id=None,
        semantic_root=None,
        generator_id=boolean_identification.GENERATOR,
        accepted_oracle_ids=(
            BOOLEAN_ORACLE,
            boolean_composite.ORACLE,
            boolean_identification.ORACLE,
        ),
        implementation_sha256=boolean_identification.constructor_digest(),
    )


def _world_operator_disposition(
        capability_id: str, source_adapter_id: str) -> SourceOperatorDisposition | None:
    if source_adapter_id != _WORLD_ADAPTER:
        return None
    from bilqis_mlx.source_adapters import world_rules
    if capability_id not in world_rules.CAPABILITIES:
        return None
    coordinate = _WORLD_OPERATOR_COORDINATES.get(capability_id)
    if coordinate is not None:
        semantic_root, operator_id = coordinate
        return _disposition_from_descriptor(
            capability_id, world_rules.registered_adapter().descriptor,
            operator_id=operator_id, semantic_root=semantic_root)
    if capability_id in _WORLD_NON_OPERATOR_CAPABILITIES:
        return _disposition_from_descriptor(
            capability_id, world_rules.registered_adapter().descriptor)
    return None


def source_formal_coordinate(
    capability_id: str, source_adapter_id: str,
) -> SourceFormalAuthority | None:
    """Return source-owned formal authority without depending on grade placement."""
    local_id = _local_capability_id(capability_id)
    if source_adapter_id == _BOOLEAN_ADAPTER:
        operation = local_id
        if operation not in CONNECTIVES:
            return None
        return SourceFormalAuthority(
            "cogal.operator." + operation,
            "BOOL_" + operation,
            "bilqis_mlx.live_grade_b.draw_connectives",
            (BOOLEAN_ORACLE,),
            boolean_provider_digest(),
        )
    if source_adapter_id == _NUMERIC_ADAPTER:
        matches = tuple(
            plan for plan in PLANS
            if _local_capability_id(plan.capability) == local_id)
        if len(matches) != 1 or matches[0].operation == "NUMBER":
            return None
        operation = matches[0].operation
        return SourceFormalAuthority(
            "school.op." + operation,
            operation,
            "bilqis_mlx.numeric_curriculum.draw_numeric",
            (NUMERIC_ORACLE,),
            numeric_provider_digest(),
        )
    return None


def source_operator_disposition(
        capability_id: str, source_adapter_id: str) -> SourceOperatorDisposition | None:
    """Return source-owned operator classification; absence is never NON_OPERATOR."""
    coordinate = source_formal_coordinate(capability_id, source_adapter_id)
    if coordinate is not None:
        return SourceOperatorDisposition(
            capability_id=capability_id,
            source_adapter_id=source_adapter_id,
            kind=OperatorDispositionKind.OPERATOR,
            operator_id=coordinate.operator_id,
            semantic_root=coordinate.semantic_root,
            generator_id=coordinate.generator_id,
            accepted_oracle_ids=coordinate.accepted_oracle_ids,
            implementation_sha256=coordinate.implementation_sha256,
        )

    known_non_operator = _numeric_non_operator_disposition(
        capability_id, source_adapter_id)
    if known_non_operator is not None:
        return known_non_operator
    known_non_operator = _derived_boolean_non_operator_disposition(
        capability_id, source_adapter_id)
    if known_non_operator is not None:
        return known_non_operator

    if source_adapter_id == "source.ithkuil-reference-identity/v1":
        from bilqis_mlx.source_adapters import copular
        if capability_id != copular.CAPABILITY:
            return None
        return _disposition_from_descriptor(
            capability_id, copular.registered_adapter().descriptor,
            operator_id=copular.SYMBOL, semantic_root=copular.SYMBOL)

    if source_adapter_id == "source.ithkuil-event-frames/v1":
        from bilqis_mlx.source_adapters import event_frames
        if capability_id not in event_frames.SOURCE_SPECS:
            return None
        return _disposition_from_descriptor(
            capability_id, event_frames.registered_adapter().descriptor,
            operator_id=event_frames.SYMBOLS[capability_id],
            semantic_root=event_frames.SYMBOLS[capability_id])

    world = _world_operator_disposition(capability_id, source_adapter_id)
    if world is not None:
        return world

    return None
