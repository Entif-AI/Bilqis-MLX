"""Compatibility projection from historical Course into scheduler authority."""
from __future__ import annotations

from ..curriculum import Course, validate
from ..factory.schedule import (
    ScheduleCapability, ScheduleGrade, ScheduleProgram,
)


def schedule_program_from_legacy_course(course: Course) -> ScheduleProgram:
    """Preserve historical scheduler identity while live callers migrate to v2."""
    if not isinstance(course, Course):
        raise TypeError("FACTORY_LEGACY_SCHEDULE_COURSE_REQUIRED")
    validate(course)
    counts_by_grade = {
        grade.id: dict(grade.exam_item_counts) for grade in course.grades}
    return ScheduleProgram(
        program_digest=course.digest(),
        grades=tuple(ScheduleGrade(
            id=grade.id,
            capabilities=tuple(ScheduleCapability(
                capability.id,
                counts_by_grade[grade.id].get(capability.id),
            ) for capability in grade.capabilities),
            teaching_stages=grade.teaching_stages,
            assessment_sha256=grade.assessment_sha256,
        ) for grade in course.grades),
        program_complete=course.program_complete,
        assessment_manifest_sha256=course.assessment_manifest_sha256,
    )
