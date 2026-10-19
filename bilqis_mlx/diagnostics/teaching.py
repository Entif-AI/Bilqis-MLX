"""Practical S4/S5 checks using delivered *families* and source query structure.

Only a source-oracle-checked candidate pool may be supplied by the caller.
The summary is evidence of actual selected optimizer batches, without storing
every specimen ID or restricting failed examination questions from teaching.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from ..curriculum import Course
from ..source_adapters.structure import inspect_source_query
from .signals import (DiagnosticFinding, DiagnosticStatus, DiagnosticTarget,
                      LearningSignal, ObservationScope)


@dataclass(frozen=True)
class LessonStepEvidence:
    offered_count: int
    delivered_count: int
    simplest_offered: tuple[int, int]
    simplest_delivered: tuple[int, int]
    prerequisite_capabilities: tuple[str, ...]


def inspect_lesson_step(course: Course, capability: str, offered: list[dict],
                        delivered: list[dict]) -> LessonStepEvidence:
    """Use owned course identities, not locally invented semantic labels."""
    caps = course.capability_map
    if capability not in caps or not offered or not delivered:
        raise ValueError("LESSON_EVIDENCE_MISSING_CAPABILITY_OR_BATCH")
    own = caps[capability]
    root_owners: dict[str, set[str]] = {}
    for candidate in caps.values():
        for root in candidate.taught_roots:
            root_owners.setdefault(root, set()).add(candidate.id)

    def extract(row: dict) -> tuple[tuple[int, int], tuple[str, ...]]:
        if (not isinstance(row, dict) or row.get("capability") != capability or
                not isinstance(row.get("record"), dict) or
                not isinstance(row.get("tokens"), list) or
                not row["tokens"] or not row.get("oracle") or not row.get("generator")):
            raise ValueError("LESSON_EVIDENCE_INVALID_SOURCE_ROW")
        from ..source_adapters.numeric import DIALECT
        if row["record"].get("task") == DIALECT:
            from ..source_adapters.numeric import inspect_record
            shape = inspect_record(row["record"])
        else:
            shape = inspect_source_query(row["record"].get("query"))
        if shape.root not in own.taught_roots:
            raise ValueError("LESSON_EVIDENCE_WRONG_ROOT")
        involved = set()
        for root in shape.rooted_operators[1:]:
            if root in own.taught_roots:
                continue
            owners = root_owners.get(root, set())
            eligible = owners & set(own.prerequisites)
            if len(eligible) != 1:
                raise ValueError("LESSON_EVIDENCE_UNADMITTED_CONSTITUENT")
            involved.update(eligible)
        return (shape.semantic_operations, len(row["tokens"])), tuple(sorted(involved))

    available = {}
    for row in offered:
        identity = row.get("id")
        if not isinstance(identity, str) or not identity:
            raise ValueError("LESSON_EVIDENCE_OFFERED_IDENTITY_MISSING")
        if identity in available and available[identity] != row:
            raise ValueError("LESSON_EVIDENCE_OFFERED_IDENTITY_CONFLICT")
        available[identity] = row
    if any(row.get("id") not in available or available[row["id"]] != row
           for row in delivered):
        raise ValueError("LESSON_EVIDENCE_DELIVERED_NOT_OFFERED")
    offered_shapes = [extract(row)[0] for row in offered]
    delivered_shapes = [extract(row) for row in delivered]
    return LessonStepEvidence(
        len(offered), len(delivered), min(offered_shapes),
        min(complexity for complexity, _ in delivered_shapes),
        tuple(sorted({name for _, prerequisites in delivered_shapes
                      for name in prerequisites})),
    )


def diagnose_teaching_visit(course: Course, capability: str,
                            steps: tuple[LessonStepEvidence, ...], *,
                            introductory: bool | None) -> tuple[DiagnosticFinding, ...]:
    """Warn the inherited teacher; never modify its learned allocation."""
    if capability not in course.capability_map or not steps:
        raise ValueError("LESSON_DIAGNOSTIC_MISSING_INPUT")
    defined = course.capability_map[capability].prerequisites
    observed = {name for step in steps for name in step.prerequisite_capabilities}
    total = sum(step.delivered_count for step in steps)
    if not defined:
        s4_status = DiagnosticStatus.NOT_APPLICABLE
        s4_note = "Direct capability has no earlier-grade prerequisites"
    elif observed & set(defined):
        s4_status = DiagnosticStatus.NOT_OBSERVED
        s4_note = "Actual delivered examples used previously taught semantic constituents"
    else:
        s4_status = DiagnosticStatus.OBSERVED_IN_INSTRUCTION
        s4_note = "No declared earlier-grade constituent appeared in the delivered examples"

    first = steps[0]
    if introductory is None:
        s5_status = DiagnosticStatus.NOT_MEASURED
        s5_note = "Cannot establish whether this was the capability's first instruction"
    elif not introductory:
        s5_status = DiagnosticStatus.NOT_APPLICABLE
        s5_note = "This was not the capability's introductory visit"
    elif first.simplest_delivered > first.simplest_offered:
        s5_status = DiagnosticStatus.OBSERVED_IN_INSTRUCTION
        s5_note = "A simpler independently source-valid example was offered but not selected first"
    else:
        s5_status = DiagnosticStatus.NOT_OBSERVED
        s5_note = "A simplest offered source-valid example was delivered at introduction"

    def finding(signal: LearningSignal, status: DiagnosticStatus, note: str):
        return DiagnosticFinding(signal, status, capability, DiagnosticTarget.CAPABILITY,
            ObservationScope.TRAINING_VISIT, total, None, None, None, (), note)

    return (finding(LearningSignal.DISCONNECTED_PREREQUISITES, s4_status, s4_note),
            finding(LearningSignal.EXCESSIVE_INTRODUCTORY_COMPLEXITY, s5_status, s5_note))


METHODOLOGY_VERSION = "bilqis.lesson-methodology/v1"


def summarize_teaching_visit(course: Course, capability: str,
                             steps: tuple[LessonStepEvidence, ...], *,
                             introductory: bool, unmeasured_reason: str | None = None) -> dict:
    """Record only compact offered/delivered evidence; no exam-item embargo.

    Parsing a future source dialect is an *observability* gap, not a new
    permission gate on already source-verified early-grade teaching.
    """
    if unmeasured_reason:
        findings = tuple(DiagnosticFinding(
            signal, DiagnosticStatus.NOT_MEASURED, capability,
            DiagnosticTarget.CAPABILITY, ObservationScope.TRAINING_VISIT,
            0, None, None, None, (),
            "Structural diagnostic unavailable: " + unmeasured_reason)
            for signal in (LearningSignal.DISCONNECTED_PREREQUISITES,
                           LearningSignal.EXCESSIVE_INTRODUCTORY_COMPLEXITY))
    else:
        findings = diagnose_teaching_visit(
            course, capability, steps, introductory=introductory)
    return {
        "schema": METHODOLOGY_VERSION,
        "course_sha256": course.digest(),
        "capability": capability,
        "introductory_full_grade_pass": introductory,
        "offered_examples": sum(step.offered_count for step in steps),
        "delivered_examples": sum(step.delivered_count for step in steps),
        "optimizer_batches_observed": len(steps),
        "simplest_offered_first_batch": list(steps[0].simplest_offered) if steps else None,
        "simplest_delivered_first_batch": list(steps[0].simplest_delivered) if steps else None,
        "constituent_capabilities_delivered": sorted({name for step in steps
            for name in step.prerequisite_capabilities}),
        "findings": [asdict(item) for item in findings],
    }
