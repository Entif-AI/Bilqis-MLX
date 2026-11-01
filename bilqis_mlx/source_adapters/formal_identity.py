"""Source-owned formal coordinates for existing Factory capabilities."""
from __future__ import annotations

from bilqis_mlx.grade_b_oracle import CONNECTIVES
from bilqis_mlx.live_grade_c import PLANS


_BOOLEAN_ADAPTERS = frozenset({
    "source.micro.boolean-composite/v1",
    "source.micro.boolean-connectives/v1",
    "source.micro.boolean-identification/v1",
})


def source_formal_coordinate(
    capability_id: str, source_adapter_id: str,
) -> tuple[str, str] | None:
    """Return source-owned semantic root + A07 operator ID when exact."""
    if source_adapter_id in _BOOLEAN_ADAPTERS:
        if not capability_id.startswith("B."):
            return None
        operation = capability_id.removeprefix("B.")
        if operation not in CONNECTIVES:
            return None
        return "cogal.operator." + operation, "BOOL_" + operation
    if source_adapter_id == "source.finite-numeric/v2":
        matches = tuple(plan for plan in PLANS if plan.capability == capability_id)
        if len(matches) != 1 or matches[0].operation == "NUMBER":
            return None
        operation = matches[0].operation
        return "school.op." + operation, operation
    return None
