"""Scheduler-only projection of one admitted executable curriculum.

The scheduler is not allowed to reconstruct semantic/source/release authority.
It receives only the roster, ordering, staged pedagogy, declared item counts,
assessment seals for cumulative grade scopes, and the program-complete bit.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .assessment import assessment_scope_contract
from .executable_release import ExecutableFactoryRelease


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ScheduleCapability:
    id: str
    exam_item_count: int | None

    def __post_init__(self) -> None:
        if (not isinstance(self.id, str) or not self.id or
                (self.exam_item_count is not None and (
                    type(self.exam_item_count) is not int or
                    self.exam_item_count < 1))):
            raise ValueError("FACTORY_SCHEDULE_CAPABILITY_INVALID")


@dataclass(frozen=True)
class ScheduleGrade:
    id: str
    capabilities: tuple[ScheduleCapability, ...]
    teaching_stages: tuple[tuple[str, ...], ...]
    assessment_sha256: str | None

    def __post_init__(self) -> None:
        ids = tuple(item.id for item in self.capabilities)
        if (not isinstance(self.id, str) or not self.id or not ids or
                len(set(ids)) != len(ids)):
            raise ValueError("FACTORY_SCHEDULE_GRADE_INVALID")
        if self.teaching_stages and (
                any(not stage for stage in self.teaching_stages) or
                tuple(cap for stage in self.teaching_stages for cap in stage) != ids):
            raise ValueError("FACTORY_SCHEDULE_STAGES_INVALID")
        if self.assessment_sha256 is not None and (
                not isinstance(self.assessment_sha256, str) or
                len(self.assessment_sha256) != 64 or
                any(c not in "0123456789abcdef"
                    for c in self.assessment_sha256)):
            raise ValueError("FACTORY_SCHEDULE_ASSESSMENT_INVALID")

    @property
    def exam_item_counts(self) -> tuple[tuple[str, int], ...]:
        return tuple(
            (item.id, item.exam_item_count)
            for item in self.capabilities
            if item.exam_item_count is not None)


@dataclass(frozen=True)
class ScheduleProgram:
    """Complete input contract for generic scheduling and mastery state."""

    program_digest: str
    grades: tuple[ScheduleGrade, ...]
    program_complete: bool
    assessment_manifest_sha256: str | None = None

    def __post_init__(self) -> None:
        if (not isinstance(self.program_digest, str) or
                len(self.program_digest) != 64 or
                any(c not in "0123456789abcdef" for c in self.program_digest) or
                not self.grades or type(self.program_complete) is not bool):
            raise ValueError("FACTORY_SCHEDULE_PROGRAM_INVALID")
        ids = tuple(grade.id for grade in self.grades)
        if len(set(ids)) != len(ids):
            raise ValueError("FACTORY_SCHEDULE_DUPLICATE_GRADE")
        caps = tuple(
            capability.id for grade in self.grades
            for capability in grade.capabilities)
        if len(set(caps)) != len(caps):
            raise ValueError("FACTORY_SCHEDULE_DUPLICATE_CAPABILITY")
        if self.assessment_manifest_sha256 is not None and (
                not isinstance(self.assessment_manifest_sha256, str) or
                len(self.assessment_manifest_sha256) != 64 or
                any(c not in "0123456789abcdef"
                    for c in self.assessment_manifest_sha256)):
            raise ValueError("FACTORY_SCHEDULE_MANIFEST_INVALID")

    def digest(self) -> str:
        return self.program_digest

    @property
    def capability_map(self) -> dict[str, ScheduleCapability]:
        return {
            capability.id: capability
            for grade in self.grades for capability in grade.capabilities
        }


def schedule_program_from_executable_release(
        release: ExecutableFactoryRelease) -> ScheduleProgram:
    """Project only scheduler-owned facts from one verified v2 release."""
    if not isinstance(release, ExecutableFactoryRelease):
        raise TypeError("FACTORY_SCHEDULE_EXECUTABLE_RELEASE_REQUIRED")
    release.verify()
    plan = release.execution_plan
    capability_map = plan.capability_map
    grades = []
    for grade in plan.grades:
        contract = assessment_scope_contract(release, grade.cumulative_scope)
        grades.append(ScheduleGrade(
            id=grade.grade_id,
            capabilities=tuple(ScheduleCapability(
                capability_id,
                capability_map[capability_id].exam_item_count,
            ) for capability_id in grade.capabilities),
            teaching_stages=grade.teaching_stages,
            assessment_sha256=contract.rubric_sha256,
        ))
    program_digest = _digest({
        "schema": "bilqis.mlx.schedule-program/v2",
        "roster": plan.projection_digests.roster,
        "schedule": plan.projection_digests.schedule,
        "program_complete": release.curriculum.program_complete,
    })
    manifest = (
        grades[-1].assessment_sha256
        if release.curriculum.program_complete else None)
    return ScheduleProgram(
        program_digest=program_digest,
        grades=tuple(grades),
        program_complete=release.curriculum.program_complete,
        assessment_manifest_sha256=manifest,
    )
