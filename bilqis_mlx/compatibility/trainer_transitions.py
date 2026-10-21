"""Historical Course transition implementations for immutable v1 evidence.

Current runtime progression uses ExecutableFactoryRelease + CurriculumProfile.
These functions exist only so historical migration/system tests and old receipts
remain reproducible while the compatibility surface is retired.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace

from ..curriculum.scheduler import (
    append_next_grade,
    assessment_capabilities,
    replace_admitted_grade,
    revise_admitted_grade,
)
from .live_releases import (
    BOOLEAN_IDENTIFICATION_RELEASE,
    MINIMAL_BOOLEAN_RELEASE,
    legacy_receipt_fields,
    rebind_same_grade_config,
    release_code_digest,
)
from ..learning.championship_identity import (
    build_school_identity,
    enforce_school_identity,
)
from ..live_curriculum import assessment_rubric_for_scope
from ..runtime.admission import _factory_admission
from .source_adapters import historical_source_registry


def _owners():
    from .. import trainer
    return trainer


def _next_grade_admission_event(record, school, current_grade: str,
                                introduced_grade: str, successor, epoch: dict,
                                history: list, compatibility: dict,
                                release_sha256: str) -> dict:
    return {
        "event": "SCHOOL_NEXT_GRADE_COURSE_ADMITTED",
        "generation": record["generation"],
        "grade": introduced_grade,
        "previous_cohort_sha256":
            (record.get("last_exam") or {}).get("cohort_sha256"),
        "previous_grade": current_grade,
        "previous_grade_champion_sha256": school.champions[current_grade].sha256,
        "student_sha256": school.current_student.sha256,
        "optimizer_step": school.current_student.optimizer_step,
        "teacher_events": record["teacher"]["events"],
        "championship_baseline_sha256": epoch["baseline"]["sha256"],
        "archived_championship_epochs": len(history),
        "introduced_grade_rubric": successor.grades[-1].assessment_sha256,
        "release_provider_sha256": release_code_digest(successor.version),
        "factory_release_sha256": release_sha256,
        **compatibility,
        "model_and_own_adamw_unchanged": True,
    }


def _grade_replacement_event(record, school, previous_course, successor,
                             replaced_grade: str, old_caps: tuple[str, ...],
                             new_caps: tuple[str, ...], withheld: tuple[str, ...],
                             release_sha256: str) -> dict:
    return {
        "event": "SCHOOL_GRADE_RELEASE_REPLACED",
        "generation": record["generation"],
        "grade": replaced_grade,
        "previous_release": previous_course.version,
        "release": successor.version,
        "old_capabilities": list(old_caps),
        "new_capabilities": list(new_caps),
        "withheld_capabilities": list(withheld),
        "student_sha256": school.current_student.sha256,
        "optimizer_step": school.current_student.optimizer_step,
        "factory_release_sha256": release_sha256,
        "championship_field_reset": True,
        "stale_geometry_evidence_deactivated": True,
        "actual_neural_updates": 0,
        "model_and_own_adamw_unchanged": True,
    }


def activate_next_admitted_grade(
        run_dir, receipt, previous_course, successor, graph=None):
    t = _owners()
    school = t._state_from_json(
        receipt["school"],
        t._schedule_for_receipt(run_dir, receipt, previous_course))
    current_grade = previous_course.grades[-1].id
    if (not successor.executable or
            len(successor.grades) != len(previous_course.grades) + 1 or
            successor.grades[:-1] != previous_course.grades or
            school.stage != "AWAITING_NEXT_GRADE" or
            school.grade != current_grade or
            current_grade not in school.champions or
            receipt.get("curriculum_mode") != previous_course.version):
        raise ValueError("HUMAN_TRAINER_NEXT_GRADE_ADMISSION_BOUNDARY_NOT_MET")
    legacy_school = replace(school, course_digest=previous_course.digest())
    next_state = append_next_grade(previous_course, successor, legacy_school)
    from ..learning.mentor_epoch import begin_epoch
    exam = receipt.get("last_exam") or {}
    prior_caps = tuple(
        cap.id for grade in previous_course.grades for cap in grade.capabilities)
    epoch = begin_epoch(
        previous_graduate=asdict(school.current_student),
        admitted_baseline=asdict(next_state.current_student),
        introduced_grade=successor.grades[-1].id,
        source_graph_sha256=receipt["semantic_graph_sha256"],
        previous_capabilities=prior_caps,
        previous_graduation_exam={
            "checkpoint_sha256": exam.get("student_sha256"),
            "rubric_sha256": exam.get("exam_rubric_sha256"),
            "cohort_sha256": exam.get("cohort_sha256"),
            "scores": exam.get("scores"),
        })
    history = list(receipt.get("championship_epoch_history", ()))
    if receipt.get("mentor_epoch") is not None:
        history.append(receipt["mentor_epoch"])
    release, release_file, admission = _factory_admission(
        run_dir, successor, next_state.current_student,
        receipt["semantic_graph_sha256"],
        registry=historical_source_registry())
    settled = deepcopy(
        (receipt.get("mentor_epoch") or {}).get("settled_matchups", {}))
    identity = build_school_identity(
        course_sha256=successor.digest(),
        semantic_graph_sha256=receipt["semantic_graph_sha256"],
        parameter_shapes=receipt["parameter_shapes"],
        factory_release_sha256=release.release_sha256)
    epoch["settled_matchups"] = settled
    epoch["championship_school_identity"] = identity
    compatibility = legacy_receipt_fields(successor.version)
    config_update = {}
    if successor.version == MINIMAL_BOOLEAN_RELEASE:
        if not isinstance(graph, dict):
            raise ValueError("HUMAN_TRAINER_MINIMAL_GRADE_B_REQUIRES_GRAPH")
        config_update["config"] = rebind_same_grade_config(
            successor.version, receipt["config"], graph)
    candidate = {
        **receipt,
        **compatibility,
        "curriculum_mode": successor.version,
        **config_update,
        "live_rubric_sha256": assessment_rubric_for_scope(
            successor, assessment_capabilities(successor, next_state)),
        "factory_release_sha256": release.release_sha256,
        "factory_release_file": release_file,
        "factory_admission": asdict(admission),
        "championship_school_identity": identity,
        "mentor_epoch": epoch,
        "championship_epoch_history": history,
    }
    introduced_grade = successor.grades[-1].id
    record = t._advance(
        run_dir, candidate, next_state,
        result="ACTIVE_GRADE_" + introduced_grade, persist=False)
    admitted = _next_grade_admission_event(
        record, school, current_grade, introduced_grade, successor, epoch,
        history, compatibility, release.release_sha256)
    record = t._persist(
        run_dir, t._with_delivery_outbox(record, (admitted,)))
    t._reconcile_delivery_outbox(run_dir, record)
    return record


def activate_revised_admitted_grade(
        run_dir, receipt, previous_course, successor, graph=None):
    t = _owners()
    school = t._state_from_json(
        receipt["school"],
        t._schedule_for_receipt(run_dir, receipt, previous_course))
    legacy_school = replace(school, course_digest=previous_course.digest())
    next_state, revised_grade = revise_admitted_grade(
        previous_course, successor, legacy_school)
    release, release_file, admission = _factory_admission(
        run_dir, successor, next_state.current_student,
        receipt["semantic_graph_sha256"],
        registry=historical_source_registry())
    identity = build_school_identity(
        course_sha256=successor.digest(),
        semantic_graph_sha256=receipt["semantic_graph_sha256"],
        parameter_shapes=receipt["parameter_shapes"],
        factory_release_sha256=release.release_sha256)
    history = [*receipt.get("curriculum_history", ()), {
        "release": previous_course.version,
        "course_digest": previous_course.digest(),
        "generation": receipt["generation"],
        "state_file": f"states/{receipt['generation']:07d}.json",
        "revised_grade": revised_grade,
        "retired_grade_champion": (
            asdict(school.champions[revised_grade])
            if revised_grade in school.champions else None),
    }]
    config_update = {}
    if "config" in receipt or successor.version == BOOLEAN_IDENTIFICATION_RELEASE:
        if "config" not in receipt:
            raise ValueError("HUMAN_TRAINER_TYPED_GRADE_REVISION_CONFIG_MISSING")
        config_update["config"] = rebind_same_grade_config(
            successor.version, receipt["config"], graph)
    updated = {
        **receipt,
        **legacy_receipt_fields(successor.version),
        **config_update,
        "curriculum_mode": successor.version,
        "curriculum_history": history,
        "curriculum_parent":
            receipt.get("curriculum_parent", asdict(school.current_student)),
        "live_rubric_sha256": assessment_rubric_for_scope(
            successor, assessment_capabilities(successor, next_state)),
        "factory_release_sha256": release.release_sha256,
        "factory_release_file": release_file,
        "factory_admission": asdict(admission),
        "championship_school_identity": identity,
        "last_exam": None,
    }
    updated.pop("qualification_cohort", None)
    if updated.get("mentor_epoch") is not None:
        epoch, _ = enforce_school_identity(
            updated["mentor_epoch"], identity,
            generation=receipt["generation"] + 1,
            student=asdict(school.current_student))
        updated["mentor_epoch"] = epoch
    record = t._advance(
        run_dir, updated, next_state,
        result="ACTIVE_GRADE_" + next_state.grade, persist=False)
    event = {
        "event": "SCHOOL_GRADE_RELEASE_REVISED",
        "generation": record["generation"],
        "grade": revised_grade,
        "previous_release": previous_course.version,
        "release": successor.version,
        "student_sha256": school.current_student.sha256,
        "optimizer_step": school.current_student.optimizer_step,
        "factory_release_sha256": release.release_sha256,
        "actual_neural_updates": 0,
    }
    record = t._persist(
        run_dir, t._with_delivery_outbox(record, (event,)))
    t._reconcile_delivery_outbox(run_dir, record)
    return record


def activate_replaced_admitted_grade(
        run_dir, receipt, previous_course, successor, graph=None):
    t = _owners()
    school = t._state_from_json(
        receipt["school"],
        t._schedule_for_receipt(run_dir, receipt, previous_course))
    legacy_school = replace(school, course_digest=previous_course.digest())
    next_state, replaced_grade = replace_admitted_grade(
        previous_course, successor, legacy_school)
    release, release_file, admission = _factory_admission(
        run_dir, successor, next_state.current_student,
        receipt["semantic_graph_sha256"],
        registry=historical_source_registry())
    identity = build_school_identity(
        course_sha256=successor.digest(),
        semantic_graph_sha256=receipt["semantic_graph_sha256"],
        parameter_shapes=receipt["parameter_shapes"],
        factory_release_sha256=release.release_sha256)
    old_caps = tuple(
        cap.id for grade in previous_course.grades
        if grade.id == replaced_grade for cap in grade.capabilities)
    new_caps = tuple(
        cap.id for grade in successor.grades
        if grade.id == replaced_grade for cap in grade.capabilities)
    withheld = tuple(cap for cap in old_caps if cap not in set(new_caps))
    history = [*receipt.get("curriculum_history", ()), {
        "release": previous_course.version,
        "course_digest": previous_course.digest(),
        "generation": receipt["generation"],
        "state_file": f"states/{receipt['generation']:07d}.json",
        "replaced_grade": replaced_grade,
        "old_capabilities": list(old_caps),
        "new_capabilities": list(new_caps),
        "withheld_capabilities": list(withheld),
        "replacement_kind": "HUMAN_DIRECTED_GRADE_WINNOW",
    }]
    if "config" not in receipt:
        raise ValueError("HUMAN_TRAINER_GRADE_REPLACEMENT_CONFIG_MISSING")
    updated = {
        **receipt,
        **legacy_receipt_fields(successor.version),
        "config": rebind_same_grade_config(
            successor.version, receipt["config"], graph),
        "curriculum_mode": successor.version,
        "curriculum_history": history,
        "live_rubric_sha256": assessment_rubric_for_scope(
            successor, assessment_capabilities(successor, next_state)),
        "factory_release_sha256": release.release_sha256,
        "factory_release_file": release_file,
        "factory_admission": asdict(admission),
        "championship_school_identity": identity,
        "capability_best": {},
        "graduation_perfect": {},
        "whole_student_peaks": [],
        "teacher_misses": [],
        "teacher_miss_exposures": {},
        "last_exam": None,
        "burned_generalization_cohorts": [],
        "legacy_frontier_pending_replay": False,
        "stagnation_session": None,
    }
    updated.pop("qualification_cohort", None)
    updated.pop("last_generalization_cohort", None)
    if updated.get("mentor_epoch") is not None:
        epoch, _ = enforce_school_identity(
            updated["mentor_epoch"], identity,
            generation=receipt["generation"] + 1,
            student=asdict(school.current_student))
        updated["mentor_epoch"] = epoch
    record = t._advance(
        run_dir, updated, next_state,
        result="ACTIVE_GRADE_" + next_state.grade, persist=False)
    event = _grade_replacement_event(
        record, school, previous_course, successor, replaced_grade,
        old_caps, new_caps, withheld, release.release_sha256)
    record = t._persist(
        run_dir, t._with_delivery_outbox(record, (event,)))
    t._reconcile_delivery_outbox(run_dir, record)
    return record
