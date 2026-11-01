"""Source-owned formal coordinates for existing Factory capabilities."""
from __future__ import annotations

from dataclasses import dataclass

from bilqis_mlx.grade_b_oracle import CONNECTIVES, VERSION as BOOLEAN_ORACLE
from bilqis_mlx.live_grade_b import constructor_digest as boolean_provider_digest
from bilqis_mlx.live_grade_c import PLANS, provider_implementation_digest as numeric_provider_digest
from bilqis_mlx.numeric_curriculum import ORACLE as NUMERIC_ORACLE


_BOOLEAN_ADAPTER = "source.micro.boolean-connectives/v1"
_NUMERIC_ADAPTER = "source.finite-numeric/v2"


@dataclass(frozen=True)
class SourceFormalAuthority:
    semantic_root: str
    operator_id: str
    generator_id: str
    accepted_oracle_ids: tuple[str, ...]
    implementation_sha256: str


def _local_capability_id(capability_id: str) -> str:
    return capability_id.rsplit(".", 1)[-1]


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
