"""Executable release, profile and JIT adoption transactions."""
from __future__ import annotations


import bilqis_mlx.compatibility.executable_projection as _compatibility_executable_projection
import bilqis_mlx.curriculum.scheduler as _curriculum_scheduler
import bilqis_mlx.factory.executable_release as _factory_executable_release
import bilqis_mlx.factory.live_answers as _factory_live_answers
import bilqis_mlx.factory.schedule as _factory_schedule
import bilqis_mlx.learning.championship_identity as _learning_championship_identity
import bilqis_mlx.profiles.catalog as _profiles_catalog
import bilqis_mlx.runtime.admission as _runtime_admission
import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
import bilqis_mlx.runtime.state as _runtime_state
import bilqis_mlx.source_adapters.school as _source_adapters_school
import bilqis_mlx.vocabulary_growth as _bilqis_mlx_vocabulary_growth
import copy as _copy
import dataclasses as _dataclasses
import functools as _functools
import pathlib as _pathlib
import uuid as _uuid


def _ensure_factory_admission(run_dir, receipt, course, graph):
    """Neural-inert migration for historical runs that predate FactoryRelease."""
    if receipt.get("factory_admission") is not None:
        _runtime_admission._require_factory_admission(run_dir, receipt, course)
        return receipt
    school = _runtime_state._state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
    release, release_file, admission = _runtime_admission._factory_admission(
        run_dir, course, school.current_student, _runtime_state._fingerprint(graph))
    migrated = {**receipt,
                "factory_release_sha256": release.release_sha256,
                "factory_release_file": release_file,
                "factory_admission": _dataclasses.asdict(admission)}
    record = _runtime_checkpoints._advance(run_dir, migrated, school, persist=False)
    event = {"event": "SCHOOL_FACTORY_RELEASE_MIGRATED",
             "generation": record["generation"],
             "grade": school.grade,
             "factory_release_sha256": release.release_sha256,
             "student_sha256": school.current_student.sha256,
             "optimizer_step": school.current_student.optimizer_step,
             "actual_neural_updates": 0}
    record = _runtime_checkpoints._persist(run_dir, _runtime_checkpoints._with_delivery_outbox(record, (event,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, record)
    _runtime_admission._require_factory_admission(run_dir, record, course)
    return record


def _migrate_executable_release(run_dir, receipt, course, grade_a_course, source_root, graph):
    school = _runtime_state._state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
    release, program, _ = _compatibility_executable_projection.compile_projected_executable_release(
        course, grade_a_course, source_root, graph)
    rebound = _dataclasses.replace(school, course_digest=program.digest())
    _runtime_state._state_from_json(_dataclasses.asdict(rebound), program)
    release, release_file, admission = _runtime_admission._executable_factory_admission(
        run_dir, release, rebound.current_student,
        receipt["semantic_graph_sha256"], graph)
    migrated = dict(receipt)
    migrated.update({
        "factory_release_sha256": release.release_sha256,
        "factory_release_file": release_file,
        "factory_release_schema": release.schema,
        "factory_admission_v2": _dataclasses.asdict(admission),
        "live_rubric_sha256": program.grades[rebound.grade_index].assessment_sha256,
        **_compatibility_executable_projection.legacy_execution_metadata(course),
    })
    return migrated, release, program, rebound


def _ensure_executable_release(run_dir, receipt, course, grade_a_course, source_root, graph):
    if receipt.get("factory_admission_v2") is None:
        migrated, release, program, rebound = _migrate_executable_release(
            run_dir, receipt, course, grade_a_course, source_root, graph)
        receipt = _runtime_checkpoints._advance(run_dir, migrated, rebound)
        _runtime_admission._require_executable_factory_admission(run_dir, receipt, graph)
        return receipt, release, program
    release = _runtime_admission._require_executable_factory_admission(run_dir, receipt, graph)
    return receipt, release, _factory_schedule.schedule_program_from_executable_release(release)


@_functools.lru_cache(maxsize=32)
def _cached_schedule_program(run_dir_string, release_sha256, release_file):
    release = _runtime_admission._read_executable_factory_release_artifact(
        _pathlib.Path(run_dir_string), {
            "factory_release_sha256": release_sha256,
            "factory_release_file": release_file,
        })
    return _factory_schedule.schedule_program_from_executable_release(release)


def _schedule_for_receipt(run_dir, receipt, course):
    if receipt.get("factory_admission_v2") is not None:
        return _cached_schedule_program(
            str(_pathlib.Path(run_dir).resolve()),
            receipt["factory_release_sha256"],
            receipt["factory_release_file"],
        )
    if isinstance(course, _factory_schedule.ScheduleProgram):
        return course
    from bilqis_mlx.compatibility.schedule_program import schedule_program_from_legacy_course

    if receipt.get("factory_admission") is not None:
        # A v1 run already owns an immutable admitted course. Reconstruct the
        # scheduler from that sealed artifact instead of asking today's source
        # constructors to reproduce yesterday's byte identity.
        release = _runtime_admission._read_factory_release(_pathlib.Path(run_dir), receipt)
        return schedule_program_from_legacy_course(release.course)
    return schedule_program_from_legacy_course(course)


def _activate_next_admitted_grade(run_dir, receipt, previous_course, successor,
                                  graph=None):
    """Compatibility shim for historical Course transition tests."""
    from bilqis_mlx.compatibility.trainer_transitions import activate_next_admitted_grade
    return activate_next_admitted_grade(
        run_dir, receipt, previous_course, successor, graph)


def _verify_profile_successor(predecessor, successor, graph, profile):
    """Require the compiled successor to match the requested catalog and profile."""
    successor.verify_successor_of(predecessor)
    successor.verify_semantic_catalog(graph)
    if successor.profile != profile:
        raise ValueError("FACTORY_EXECUTABLE_PROFILE_TRANSITION_MISMATCH")


def _profile_transition(previous_program, successor_program, school, *, mastery_debt=None):
    topology = _curriculum_scheduler.classify_schedule_topology(previous_program, successor_program)
    appended = topology is _curriculum_scheduler.ScheduleTopology.APPEND_GRADE
    if topology is _curriculum_scheduler.ScheduleTopology.UNCHANGED and mastery_debt is None:
        return school, None, False
    revised = topology in (
        _curriculum_scheduler.ScheduleTopology.UNCHANGED,
        _curriculum_scheduler.ScheduleTopology.SAME_GRADE_EXPANSION,
        _curriculum_scheduler.ScheduleTopology.SAME_GRADE_REVISION)
    if appended:
        if mastery_debt is None and school.stage == "AWAITING_NEXT_GRADE_WITH_DEBT":
            mastery_debt = school.carried_mastery_debt
        return (
            (_curriculum_scheduler.append_next_grade_with_debt(
                previous_program, successor_program, school, mastery_debt)
             if mastery_debt is not None else
             _curriculum_scheduler.adopt_appended_program(previous_program, successor_program, school)),
            None,
            True,
        )
    if revised and mastery_debt is None:
        changed = tuple(
            index for index, (old_grade, new_grade) in
            enumerate(zip(previous_program.grades, successor_program.grades))
            if (old_grade.capabilities != new_grade.capabilities or
                old_grade.teaching_stages != new_grade.teaching_stages))
        if len(changed) == 1 and changed[0] < school.grade_index:
            next_state, revised_grade = _curriculum_scheduler.adopt_expanded_prior_grade(
                previous_program, successor_program, school)
        else:
            next_state, revised_grade = _curriculum_scheduler.adopt_revised_program(
                previous_program, successor_program, school)
        return next_state, revised_grade, False
    raise ValueError("FACTORY_EXECUTABLE_PROFILE_TRANSITION_UNSUPPORTED")


def _profile_championship_state(
        receipt, predecessor, successor, school, next_state, *, appended,
        mastery_debt=None):
    exam = (receipt.get("debt_admission_boundary_exam") if mastery_debt is not None
            else receipt.get("last_exam")) or {}
    history = list(receipt.get("championship_epoch_history", ()))
    identity = _learning_championship_identity.build_school_identity(
        course_sha256=successor.execution_plan.curriculum_sha256,
        semantic_graph_sha256=receipt["semantic_graph_sha256"],
        parameter_shapes=receipt["parameter_shapes"],
        factory_release_sha256=successor.release_sha256)
    if appended:
        from bilqis_mlx.learning.mentor_epoch import begin_epoch, begin_debt_epoch
        boundary = {
            "checkpoint_sha256": exam.get("student_sha256"),
            "rubric_sha256": exam.get("exam_rubric_sha256"),
            "cohort_sha256": exam.get("cohort_sha256"),
            "scores": exam.get("scores"),
        }
        arguments = dict(
            admitted_baseline=_dataclasses.asdict(next_state.current_student),
            introduced_grade=next_state.grade,
            source_graph_sha256=receipt["semantic_graph_sha256"],
            previous_capabilities=tuple(
                item.capability_id for item in predecessor.execution_plan.capabilities))
        if mastery_debt is not None:
            epoch = begin_debt_epoch(**arguments,
                previous_checkpoint=_dataclasses.asdict(school.current_student),
                previous_boundary_exam=boundary, previous_mastery_debt=mastery_debt)
        else:
            epoch = begin_epoch(**arguments,
                previous_graduate=_dataclasses.asdict(school.current_student),
                previous_graduation_exam=boundary)
        if receipt.get("mentor_epoch") is not None:
            history.append(receipt["mentor_epoch"])
        epoch["settled_matchups"] = _copy.deepcopy(
            (receipt.get("mentor_epoch") or {}).get("settled_matchups", {}))
        epoch["championship_school_identity"] = identity
        return identity, epoch, history
    epoch = receipt.get("mentor_epoch")
    if epoch is not None:
        epoch, identity_event = _learning_championship_identity.enforce_school_identity(
            epoch, identity,
            generation=receipt["generation"] + 1,
            student=_dataclasses.asdict(school.current_student))
        if identity_event:
            history.append(receipt["mentor_epoch"])
    return identity, epoch, history


def _profile_adoption_receipt(
        receipt, compatibility_course, successor, successor_program,
        release_file, admission, identity, epoch, history, revised_grade,
        graph):
    heads = _factory_executable_release.answer_heads_from_executable_release(successor, graph)
    numeric_values = heads.get("numeric_active", {}).get("values")
    candidate = {
        **receipt,
        "curriculum_mode": compatibility_course.version,
        "config": {**receipt["config"], "answer_heads": heads},
        "live_rubric_sha256": successor_program.grades[-1].assessment_sha256,
        "factory_release_sha256": successor.release_sha256,
        "factory_release_file": release_file,
        "factory_release_schema": successor.schema,
        "factory_admission_v2": _dataclasses.asdict(admission),
        "championship_school_identity": identity,
        "mentor_epoch": epoch,
        "championship_epoch_history": history,
        "last_exam": None if revised_grade is not None else receipt.get("last_exam"),
    }
    if numeric_values is not None:
        candidate["numeric_maximum"] = len(numeric_values) - 1
    candidate.pop("qualification_cohort_v2", None)
    return candidate


def _adopt_executable_profile(
        run_dir, receipt, grade_a_course, source_root, graph, profile, *,
        compiled_successor=None, allow_mastery_debt=False):
    """Adopt one same-ABI v2 profile change without release-name dispatch."""
    predecessor = _runtime_admission._require_executable_factory_admission(run_dir, receipt, graph)
    previous_program = _factory_schedule.schedule_program_from_executable_release(predecessor)
    school = _runtime_state._state_from_json(receipt["school"], previous_program)
    compatibility_course = _compatibility_executable_projection.legacy_course_for_profile(
        grade_a_course, source_root, profile)
    successor = compiled_successor or _factory_executable_release.compile_successor_profile_release(
        predecessor,
        profile,
        _source_adapters_school.live_source_registry(),
        _factory_live_answers.live_answer_registry(),
        source_root=source_root,
        graph=graph,
        verification_seed=2026101906)
    _verify_profile_successor(predecessor, successor, graph, profile)
    successor_program = _factory_schedule.schedule_program_from_executable_release(successor)
    mastery_debt = None
    if allow_mastery_debt:
        _, mastery_debt = _catalog_boundary_evidence(
            predecessor, previous_program, school, receipt, allow_mastery_debt=True)
    next_state, revised_grade, appended = _profile_transition(
        previous_program, successor_program, school, mastery_debt=mastery_debt)
    successor, release_file, admission = _runtime_admission._executable_factory_admission(
        run_dir, successor, next_state.current_student,
        receipt["semantic_graph_sha256"], graph)
    identity, epoch, history = _profile_championship_state(
        receipt, predecessor, successor, school, next_state, appended=appended,
        mastery_debt=mastery_debt)
    candidate = _profile_adoption_receipt(
        receipt, compatibility_course, successor, successor_program,
        release_file, admission, identity, epoch, history, revised_grade, graph)
    if allow_mastery_debt:
        candidate["last_exam"] = receipt["debt_admission_boundary_exam"]
        candidate.pop("fixed_frontier_exam", None)
    record = _runtime_checkpoints._advance(
        run_dir, candidate, next_state,
        result="ACTIVE_GRADE_" + next_state.grade, persist=False)
    event = {
        "event": "SCHOOL_EXECUTION_PROFILE_ADOPTED",
        "generation": record["generation"],
        "grade": next_state.grade,
        "profile_id": successor.profile.profile_id,
        "transition_kind": "APPEND_GRADE" if appended else "REVISE_PROFILE",
        "revised_grade": revised_grade,
        "debt_admission": allow_mastery_debt,
        "carried_mastery_debt": list(next_state.carried_mastery_debt),
        "previous_factory_release_sha256": predecessor.release_sha256,
        "factory_release_sha256": successor.release_sha256,
        "student_sha256": school.current_student.sha256,
        "optimizer_step": school.current_student.optimizer_step,
        "actual_neural_updates": 0,
    }
    record = _runtime_checkpoints._persist(
        run_dir, _runtime_checkpoints._with_delivery_outbox(record, (event,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, record)
    return record, compatibility_course, successor, successor_program


def _require_complete_profile_boundary(program, school, receipt):
    """Require one complete perfect cumulative exam for the admitted prefix."""
    if school.stage != "AWAITING_NEXT_GRADE":
        raise ValueError("FACTORY_PROFILE_EXPANSION_NOT_AT_GRADE_BOUNDARY")
    exam = receipt.get("last_exam") or {}
    expected = {
        capability.id: capability.exam_item_count
        for grade in program.grades for capability in grade.capabilities
    }
    if (exam.get("student_sha256") != school.current_student.sha256 or
            exam.get("optimizer_step") != school.current_student.optimizer_step or
            exam.get("scores") != {
                capability: {"correct": count, "total": count}
                for capability, count in expected.items()}):
        raise ValueError(
            "FACTORY_PROFILE_EXPANSION_REQUIRES_COMPLETE_PERFECT_PREFIX")


def _catalog_boundary_evidence(
        predecessor, previous_program, school, receipt, *, allow_mastery_debt):
    if not allow_mastery_debt:
        _require_complete_profile_boundary(previous_program, school, receipt)
        return receipt.get("last_exam") or {}, ()
    exam = receipt.get("debt_admission_boundary_exam") or {}
    expected = {
        cap.id: cap.exam_item_count
        for grade in previous_program.grades for cap in grade.capabilities
    }
    from bilqis_mlx.factory.assessment import assessment_scope_contract
    contract = assessment_scope_contract(predecessor, tuple(expected))
    if (exam.get("student_sha256") != school.current_student.sha256 or
            exam.get("optimizer_step") != school.current_student.optimizer_step or
            exam.get("factory_release_sha256") != predecessor.release_sha256 or
            exam.get("exam_rubric_sha256") != contract.rubric_sha256 or
            set(exam.get("scores", {})) != set(expected) or
            any(score.get("total") != expected[cap]
                for cap, score in exam.get("scores", {}).items())):
        raise ValueError("DEBT_ADMISSION_REQUIRES_EXACT_COMPLETE_BOUNDARY")
    mastery_debt = tuple(
        cap for cap in expected
        if exam["scores"][cap]["correct"] != expected[cap])
    return exam, mastery_debt


def _catalog_epoch_state(
        receipt, predecessor, successor, school, next_state, pointer,
        transition, grown, exam, mastery_debt, *, allow_mastery_debt):
    from bilqis_mlx.learning.mentor_epoch import begin_debt_epoch, begin_epoch
    graph_sha = _runtime_state._fingerprint(transition.graph)
    boundary_exam = {
        "checkpoint_sha256": exam.get("student_sha256"),
        "rubric_sha256": exam.get("exam_rubric_sha256"),
        "cohort_sha256": exam.get("cohort_sha256"),
        "scores": exam.get("scores"),
    }
    epoch_args = dict(
        admitted_baseline=_dataclasses.asdict(pointer),
        introduced_grade=next_state.grade,
        source_graph_sha256=graph_sha,
        previous_capabilities=tuple(
            item.capability_id for item in predecessor.execution_plan.capabilities))
    if allow_mastery_debt:
        epoch = begin_debt_epoch(
            **epoch_args,
            previous_checkpoint=_dataclasses.asdict(school.current_student),
            previous_boundary_exam=boundary_exam,
            previous_mastery_debt=mastery_debt)
    else:
        epoch = begin_epoch(
            **epoch_args,
            previous_graduate=_dataclasses.asdict(school.current_student),
            previous_graduation_exam=boundary_exam)
    history = list(receipt.get("championship_epoch_history", ()))
    if receipt.get("mentor_epoch") is not None:
        history.append(receipt["mentor_epoch"])
    identity = _learning_championship_identity.build_school_identity(
        course_sha256=successor.execution_plan.curriculum_sha256,
        semantic_graph_sha256=graph_sha,
        parameter_shapes={name: list(value.shape) for name, value in grown.items()},
        factory_release_sha256=successor.release_sha256)
    epoch["settled_matchups"] = _copy.deepcopy(
        (receipt.get("mentor_epoch") or {}).get("settled_matchups", {}))
    epoch["championship_school_identity"] = identity
    return epoch, history, identity


def _catalog_adoption_receipt(
        receipt, compatibility_course, successor, successor_program,
        release_file, admission, transition, grown, epoch, history,
        identity):
    graph_sha = _runtime_state._fingerprint(transition.graph)
    heads = _factory_executable_release.answer_heads_from_executable_release(successor, transition.graph)
    numeric_values = heads.get("numeric_active", {}).get("values")
    updated = {
        **receipt,
        "curriculum_mode": compatibility_course.version,
        "semantic_graph_sha256": graph_sha,
        "factory_release_sha256": successor.release_sha256,
        "factory_release_file": release_file,
        "factory_release_schema": successor.schema,
        "factory_admission_v2": _dataclasses.asdict(admission),
        "parameter_shapes": {
            name: list(value.shape) for name, value in grown.items()},
        "championship_school_identity": identity,
        "config": {
            **receipt["config"],
            "vocab_size": len(transition.graph["tokens"]),
            "answer_heads": heads,
        },
        "live_rubric_sha256": successor_program.grades[-1].assessment_sha256,
        "numeric_maximum": (
            len(numeric_values) - 1 if numeric_values is not None else
            receipt.get("numeric_maximum")),
        "numeric_scope_final_maximum": transition.numeric_scope_final_maximum,
        "mentor_epoch": epoch,
        "championship_epoch_history": history,
        "last_exam": None,
    }
    updated.pop("qualification_cohort_v2", None)
    return updated


def _catalog_adoption_event(
        record, school, pointer, successor, growth, grade: str) -> dict:
    return {
        "event": "SCHOOL_SEMANTIC_CATALOG_PROFILE_ADOPTED",
        "generation": record["generation"],
        "grade": grade,
        "profile_id": successor.profile.profile_id,
        "semantic_geometry": successor.transition.semantic_geometry,
        "growth": growth,
        "previous_student_sha256": school.current_student.sha256,
        "student_sha256": pointer.sha256,
        "optimizer_step": pointer.optimizer_step,
        "factory_release_sha256": successor.release_sha256,
        "actual_neural_updates": 0,
    }


def _adopt_catalog_profile(
        mx, run_dir, receipt, grade_a_course, source_root, graph,
        parameters, optimizer, transition, *, reserve_gib, allow_mastery_debt=False,
        compiled_successor=None):
    """Adopt one append-only semantic ABI/profile expansion with zero updates."""
    import bilqis_mlx.learning.student_ops as _learning_student_ops
    predecessor = _runtime_admission._require_executable_factory_admission(run_dir, receipt, graph)
    previous_program = _factory_schedule.schedule_program_from_executable_release(predecessor)
    school = _runtime_state._state_from_json(receipt["school"], previous_program)
    exam, mastery_debt = _catalog_boundary_evidence(
        predecessor, previous_program, school, receipt,
        allow_mastery_debt=allow_mastery_debt)
    compatibility_course = _compatibility_executable_projection.legacy_course_for_profile(
        grade_a_course, source_root, transition.profile)
    successor = compiled_successor or _factory_executable_release.compile_successor_profile_release(
        predecessor,
        transition.profile,
        _source_adapters_school.live_source_registry(),
        _factory_live_answers.live_answer_registry(),
        source_root=source_root,
        graph=transition.graph,
        verification_seed=2026101907)
    _verify_profile_successor(predecessor, successor, transition.graph, transition.profile)
    if (successor.transition is None or
            successor.transition.semantic_geometry != "APPEND_ONLY_EXPANSION"):
        raise ValueError("FACTORY_CATALOG_TRANSITION_NOT_APPEND_ONLY")
    successor_program = _factory_schedule.schedule_program_from_executable_release(successor)
    next_state = (
        _curriculum_scheduler.append_next_grade_with_debt(
            previous_program, successor_program, school, mastery_debt)
        if allow_mastery_debt else
        _curriculum_scheduler.adopt_appended_program(previous_program, successor_program, school))

    grown, own_optimizer, growth = _bilqis_mlx_vocabulary_growth.extend_mlx_student(
        parameters, optimizer, graph, transition.graph)
    pointer = _runtime_checkpoints._bundle_pointer(
        run_dir, "catalog-admission-" + _uuid.uuid4().hex[:12],
        grown, own_optimizer, transition.graph, reserve_gib=reserve_gib)
    next_state = _dataclasses.replace(next_state, current_student=pointer)
    successor, release_file, admission = _runtime_admission._executable_factory_admission(
        run_dir, successor, pointer, _runtime_state._fingerprint(transition.graph),
        transition.graph)
    epoch, history, identity = _catalog_epoch_state(
        receipt, predecessor, successor, school, next_state, pointer,
        transition, grown, exam, mastery_debt,
        allow_mastery_debt=allow_mastery_debt)
    updated = _catalog_adoption_receipt(
        receipt, compatibility_course, successor, successor_program,
        release_file, admission, transition, grown, epoch, history,
        identity)
    from bilqis_mlx.fixed_frontier import load_frontier_cohort, rebaseline_frontier_exam
    preserved = load_frontier_cohort(run_dir, exam)
    if preserved is None:
        raise ValueError("FACTORY_CATALOG_BOUNDARY_COHORT_REQUIRED")
    updated["last_exam"] = rebaseline_frontier_exam(
        run_dir, exam, checkpoint=_dataclasses.asdict(pointer), predictions=_learning_student_ops._predictions(
            mx, grown, list(preserved.rows), updated["config"], updated["answer_ids"]))
    record = _runtime_checkpoints._advance(
        run_dir, updated, next_state, model_bundle=pointer.filename,
        result="ACTIVE_GRADE_" + next_state.grade, persist=False)
    event = _catalog_adoption_event(
        record, school, pointer, successor, growth, next_state.grade)
    record = _runtime_checkpoints._persist(
        run_dir, _runtime_checkpoints._with_delivery_outbox(record, (event,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, record)
    return grown, own_optimizer, transition.graph, record, compatibility_course


def _adopt_jit_proposal(mx, run_dir, receipt, grade_a_course, source_root, graph,
                       parameters, optimizer, session, proposal, *, reserve_gib):
    """Use the existing student/own-AdamW admission transaction for a fresh JIT choice."""
    from bilqis_mlx.factory.candidate_realizations import admitted_candidate_graph
    from bilqis_mlx.runtime.jit_adoption import verify_current_implementations
    predecessor = _runtime_admission._require_executable_factory_admission(run_dir, receipt, graph)
    program = _factory_schedule.schedule_program_from_executable_release(predecessor)
    school = _runtime_state._state_from_json(receipt["school"], program)
    staged = session.resolve_ready_proposal(school.current_student, proposal)
    successor = staged.successor
    verify_current_implementations(successor, _source_adapters_school.live_source_registry(), _factory_live_answers.live_answer_registry())
    successor_program = _factory_schedule.schedule_program_from_executable_release(successor)
    appended = (_curriculum_scheduler.classify_schedule_topology(program, successor_program)
                is _curriculum_scheduler.ScheduleTopology.APPEND_GRADE)
    if appended:
        _require_complete_profile_boundary(program, school, receipt)
    if successor.transition.semantic_geometry == "APPEND_ONLY_EXPANSION":
        from bilqis_mlx.profiles.catalog import CatalogProfileTransition
        next_graph = admitted_candidate_graph(staged, graph)
        return _adopt_catalog_profile(mx, run_dir, receipt, grade_a_course, source_root,
            graph, parameters, optimizer, CatalogProfileTransition(successor.profile, next_graph),
            reserve_gib=reserve_gib, compiled_successor=successor)
    record, course, _, _ = _adopt_executable_profile(
        run_dir, receipt, grade_a_course, source_root, graph, successor.profile,
        compiled_successor=successor)
    return parameters, optimizer, graph, record, course


def _activate_revised_admitted_grade(run_dir, receipt, previous_course, successor,
                                     graph=None):
    """Publish the historical same-grade revision through the runtime writer."""
    from dataclasses import asdict, replace
    from ..curriculum.scheduler import revise_admitted_grade, assessment_capabilities
    from ..compatibility.live_releases import (
        BOOLEAN_IDENTIFICATION_RELEASE, legacy_receipt_fields, rebind_same_grade_config)
    from ..compatibility.source_adapters import historical_source_registry
    from ..learning.championship_identity import build_school_identity, enforce_school_identity
    from ..live_curriculum import assessment_rubric_for_scope
    from .admission import _factory_admission
    school = _runtime_state._state_from_json(
        receipt["school"],
        _schedule_for_receipt(run_dir, receipt, previous_course))
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
    record = _runtime_checkpoints._advance(
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
    record = _runtime_checkpoints._persist(
        run_dir, _runtime_checkpoints._with_delivery_outbox(record, (event,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, record)
    return record


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


def _activate_replaced_admitted_grade(run_dir, receipt, previous_course, successor,
                                      graph=None):
    """Publish the historical grade replacement through the runtime writer."""
    from dataclasses import asdict, replace
    from ..curriculum.scheduler import replace_admitted_grade, assessment_capabilities
    from ..compatibility.live_releases import legacy_receipt_fields, rebind_same_grade_config
    from ..compatibility.source_adapters import historical_source_registry
    from ..learning.championship_identity import build_school_identity, enforce_school_identity
    from ..live_curriculum import assessment_rubric_for_scope
    from .admission import _factory_admission
    school = _runtime_state._state_from_json(
        receipt["school"],
        _schedule_for_receipt(run_dir, receipt, previous_course))
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
    record = _runtime_checkpoints._advance(
        run_dir, updated, next_state,
        result="ACTIVE_GRADE_" + next_state.grade, persist=False)
    event = _grade_replacement_event(
        record, school, previous_course, successor, replaced_grade,
        old_caps, new_caps, withheld, release.release_sha256)
    record = _runtime_checkpoints._persist(
        run_dir, _runtime_checkpoints._with_delivery_outbox(record, (event,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, record)
    return record


def _advance_numeric_profile(run_dir, receipt, grade_a_course, source_root, graph,
                             course, release, program, *, numeric_staircase):
    """Rebind a wide historical scope, then advance the admitted staircase."""
    if numeric_staircase:
        from bilqis_mlx.numeric_staircase import INITIAL_MAXIMUM, FINAL_MAXIMUM
        if receipt.get("numeric_maximum", 0) > FINAL_MAXIMUM:
            current = _runtime_admission._require_executable_factory_admission(
                run_dir, receipt, graph)
            active = _factory_schedule.schedule_program_from_executable_release(current)
            school = _runtime_state._state_from_json(receipt["school"], active)
            if school.grade == active.grades[-1].id:
                receipt, course, release, program = _adopt_executable_profile(
                    run_dir, {**receipt, "numeric_scope_final_maximum": FINAL_MAXIMUM},
                    grade_a_course, source_root, graph,
                    _profiles_catalog.numeric_scope_profile(current, INITIAL_MAXIMUM))
    final_scope = receipt.get("numeric_scope_final_maximum")
    if final_scope is not None:
        current = _runtime_admission._require_executable_factory_admission(
            run_dir, receipt, graph)
        active = _factory_schedule.schedule_program_from_executable_release(current)
        school = _runtime_state._state_from_json(receipt["school"], active)
        next_profile = _profiles_catalog.next_numeric_scope_profile(
            current, final_maximum=final_scope)
        if next_profile is not None and school.stage in ("AWAITING_NEXT_GRADE", "AWAITING_NEXT_GRADE_WITH_DEBT"):
            receipt, course, release, program = _adopt_executable_profile(
                run_dir, receipt, grade_a_course, source_root, graph, next_profile)
    return receipt, course, release, program


def _auto_adopt_known_grade_boundary(*args, **kwargs):
    """Route sanctioned historical grade transitions through compatibility policy."""
    from bilqis_mlx.compatibility.trainer_transitions import _auto_adopt_known_grade_boundary as adopt
    return adopt(*args, **kwargs)
