"""Registry token binding and deterministic construction planning."""
from __future__ import annotations
import re
from bilqis_mlx.curriculum_compiler import CurriculumAST
from .types import ConstructionTask, RegistryAST, StagePlan

def bind_course_tokens(course: CurriculumAST, registry: RegistryAST) -> dict[str, tuple[int, ...]]:
    """Fail closed unless every currently taught root binds to a known token."""
    index = {token.symbol: token for token in registry.tokens}
    result = {}
    for cap in course.nodes:
        if any(root not in index for root in cap.roots):
            raise ValueError("REGISTRY_ADMITTED_COURSE_HAS_UNKNOWN_TOKEN:" + cap.id)
        result[cap.id] = tuple(index[root].id for root in cap.roots)
    return result

def stage_plan(registry: RegistryAST, grade: str) -> StagePlan:
    """Topological authoring plan, not approval to train the proposed stage."""
    found = next((g for g in registry.grades if g.id == grade), None)
    if found is None:
        raise ValueError("REGISTRY_UNKNOWN_PROPOSED_GRADE:" + grade)
    rank = {p.proposed_lesson: i for i, p in enumerate(registry.prerequisites)}
    members = tuple(sorted((x for x in registry.lessons if x.grade == grade),
                           key=lambda item: rank[item.id]))
    requires = tuple(dict.fromkeys(g for lesson in members
                                   for g in lesson.requires_grades))
    blockers = ["REGISTRY_PROPOSAL_NOT_NEURAL_TRAINING_RELEASE"]
    if "HISTORICAL" in found.status or "CONTINUITY" in found.status:
        blockers.append("HISTORICAL_GRADE_ALIAS_NOT_EXECUTABLE")
    if requires:
        blockers.append("REQUIRES_EARLIER_GRADES:" + ",".join(requires))
    if not members:
        blockers.append("NO_STRUCTURED_ADMITTED_LESSON_MEMBERS")
    annotations = [note for note in registry.supplemental_constraints
                   if grade in re.split(r"[^A-Z]+", note.grade)]
    if annotations:
        blockers.append("ADDITIONAL_UNCOMPILED_QUALIFICATION_CONSTRAINTS:" +
                        str(len(annotations)))
    return StagePlan(grade, found.status, members, tuple(blockers))

def construction_frontier(plan: StagePlan, *, mastered_grades=(),
                          constructed_lessons=()) -> tuple[ConstructionTask, ...]:
    """Deterministically discover the next eligible *authoring* tasks.

    Completed grades/lessons must be independently evidenced by the caller.
    An eligible task is NOT a semantic certification, exam or optimizer update.
    """
    mastered = set(mastered_grades)
    constructed = set(constructed_lessons)
    valid = {item.id for item in plan.lessons}
    if constructed - valid:
        raise ValueError("REGISTRY_UNKNOWN_CONSTRUCTED_LESSON:" + ",".join(sorted(constructed - valid)))
    unresolved_qualification = any(
        "UNCOMPILED_QUALIFICATION_CONSTRAINTS" in blocker
        for blocker in plan.blockers)
    tasks = []
    for item in plan.lessons:
        if item.id in constructed:
            continue
        missing_grades = tuple(g for g in item.requires_grades if g not in mastered)
        missing_lessons = tuple(l for l in item.requires_lessons if l not in constructed)
        tasks.append(ConstructionTask(item.id, item.semantics, item.construction,
                                      item.intended_probe, missing_grades,
                                      missing_lessons,
                                      not missing_grades and not missing_lessons and
                                      not unresolved_qualification))
    return tuple(tasks)
