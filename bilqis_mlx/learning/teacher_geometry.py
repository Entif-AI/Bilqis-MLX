"""Capability-local teaching-geometry identity and replay compatibility.

Teacher policy evidence is only causally comparable while the student's lesson
surface is unchanged. Source-revision history remains durable, but changed
representations open a fresh evidence epoch for the affected capability only.
"""
from __future__ import annotations

from bilqis_mlx.boolean_identification import REPRESENTATION_VARIATION
from bilqis_mlx.boolean_composite import (
    PRESENTATION as COMPOSITE_PRESENTATION,
    REPRESENTATION_VARIATION as COMPOSITE_REPRESENTATION_VARIATION,
)
from bilqis_mlx.live_grade_b import (
    OUTER_LANDMARK_PRESENTATION,
    OUTER_LANDMARK_VARIATION,
)


IDBOOLOPS_EPOCH = "idboolops-named-proposition-bindings-v1"
AND_IMPLIES_EPOCH = "and-implies-named-outer-operands-v1"
COMPOSITE_EPOCH = "composite-proof-role-tree-landmarks-v1"
GEOMETRY_SCOPE_MARKER = "/geometry="
CAPABILITY_NOT_ADMITTED = "TEACHER_GEOMETRY_CAPABILITY_NOT_ADMITTED"
SCOPE_INVALID = "TEACHER_GEOMETRY_SCOPE_INVALID"
EPOCH_INVALID = "TEACHER_GEOMETRY_EPOCH_INVALID"


def active_epoch(release, capability: str) -> str | None:
    """Return the admitted teaching-geometry epoch for one capability."""
    execution = release.execution_plan.capability_map.get(capability)
    if execution is None:
        raise ValueError(CAPABILITY_NOT_ADMITTED)
    axes = set(execution.variation_axes)
    if (capability == "B.IDBOOLOPS" and
            REPRESENTATION_VARIATION in axes):
        return IDBOOLOPS_EPOCH
    if (capability in {"B.AND", "B.IMPLIES"} and
            OUTER_LANDMARK_VARIATION in axes):
        return AND_IMPLIES_EPOCH
    if (capability == "B.COMPOSITE" and
            COMPOSITE_REPRESENTATION_VARIATION in axes):
        return COMPOSITE_EPOCH
    return None


def context_scope(base_scope: str, epoch: str | None) -> str:
    """Partition adaptive teacher evidence only when geometry actually changed."""
    if not isinstance(base_scope, str):
        raise TypeError(SCOPE_INVALID)
    if epoch is None:
        return base_scope
    if not isinstance(epoch, str) or not epoch:
        raise ValueError(EPOCH_INVALID)
    return base_scope + GEOMETRY_SCOPE_MARKER + epoch


def is_geometry_scope(scope: str) -> bool:
    return isinstance(scope, str) and GEOMETRY_SCOPE_MARKER in scope


def row_epoch(row: dict) -> str | None:
    """Identify whether an exact replay row belongs to a current geometry."""
    capability = row.get("capability") if isinstance(row, dict) else None
    record = row.get("record") if isinstance(row, dict) else None
    if not isinstance(record, dict):
        return None
    if capability == "B.IDBOOLOPS":
        observations = record.get("observations")
        if (isinstance(observations, list) and observations and
                all(isinstance(observation, dict) and
                    isinstance(observation.get("assignments"), dict) and
                    tuple(observation["assignments"]) == ("P", "Q") and
                    type(observation.get("result")) is bool
                    for observation in observations)):
            return IDBOOLOPS_EPOCH
    if (capability in {"B.AND", "B.IMPLIES"} and
            record.get("presentation") == OUTER_LANDMARK_PRESENTATION):
        return AND_IMPLIES_EPOCH
    if (capability == "B.COMPOSITE" and
            record.get("presentation") == COMPOSITE_PRESENTATION):
        return COMPOSITE_EPOCH
    return None


def row_matches_epoch(row: dict, epoch: str | None) -> bool:
    """Exact replay bytes are valid only inside their matching geometry epoch."""
    return True if epoch is None else row_epoch(row) == epoch
