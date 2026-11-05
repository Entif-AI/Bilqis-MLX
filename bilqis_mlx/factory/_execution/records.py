"""Factory execution records owner."""
from __future__ import annotations

from dataclasses import dataclass
from ...curriculum import AnswerFamily
from .. import execution as _api


@dataclass(frozen=True)
class CapabilityExecution:
    capability_id: str
    grade_id: str
    stage: int
    prerequisites: tuple[str, ...]
    composed_of: tuple[str, ...]
    source_anchor: str
    provider_id: str
    provider_implementation_sha256: str
    oracle_id: str
    construction_program_id: str
    provider_parameters: tuple[tuple[str, tuple[str, ...]], ...]
    variation_axes: tuple[str, ...]
    teaching_option_ids: tuple[str, ...]
    answer_families: tuple[AnswerFamily, ...]
    exam_item_count: int


@dataclass(frozen=True)
class GradeExecution:
    grade_id: str
    capabilities: tuple[str, ...]
    teaching_stages: tuple[tuple[str, ...], ...]
    cumulative_scope: tuple[str, ...]
    assessment_blueprint_sha256: str


@dataclass(frozen=True)
class ProjectionDigests:
    roster: str
    schedule: str
    assessment: str
    source: str
    answer_schema: str
    coverage: str
    teaching: str


@dataclass(frozen=True)
class CapabilityProjectionDigests:
    capability_id: str
    schedule: str
    assessment: str
    source: str
    answer_schema: str
    coverage: str
    teaching: str


@dataclass(frozen=True)
class ExecutionPlan:
    profile_id: str
    curriculum_sha256: str
    source_binding_sha256: str
    grades: tuple[GradeExecution, ...]
    capabilities: tuple[CapabilityExecution, ...]
    projection_digests: ProjectionDigests
    capability_projection_digests: tuple[CapabilityProjectionDigests, ...]

    @property
    def capability_map(self) -> dict[str, CapabilityExecution]:
        return {item.capability_id: item for item in self.capabilities}

    @property
    def grade_map(self) -> dict[str, GradeExecution]:
        return {item.grade_id: item for item in self.grades}

    @property
    def course_sha256(self) -> str:
        """Compatibility alias for pre-split callers only."""
        return self.curriculum_sha256

    def digest(self) -> str:
        return _api._digest(_api.asdict(self))
