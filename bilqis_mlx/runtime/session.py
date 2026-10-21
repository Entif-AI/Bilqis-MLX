"""Operator locking, source preparation and saved-session lifecycle."""
from __future__ import annotations

import bilqis_mlx.backup as _bilqis_mlx_backup
import bilqis_mlx.compatibility.executable_projection as _compatibility_executable_projection
import bilqis_mlx.compatibility.source_bootstrap as _compatibility_source_bootstrap
import bilqis_mlx.curriculum.scheduler as _curriculum_scheduler
import bilqis_mlx.factory.schedule as _factory_schedule
import bilqis_mlx.grade_a_manifest as _bilqis_mlx_grade_a_manifest
import bilqis_mlx.learning.capability_frontier as _learning_capability_frontier
import bilqis_mlx.learning.championship_identity as _learning_championship_identity
import bilqis_mlx.learning.championship_runtime as _learning_championship_runtime
import bilqis_mlx.learning.learning_experiment as _learning_learning_experiment
import bilqis_mlx.learning.student_ops as _learning_student_ops
import bilqis_mlx.runtime.admission as _runtime_admission
import bilqis_mlx.runtime.assessment as _runtime_assessment
import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
import bilqis_mlx.runtime.disk as _runtime_disk
import bilqis_mlx.runtime.mlx_checkpoint as _runtime_mlx_checkpoint
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.state as _runtime_state
import bilqis_mlx.source as _bilqis_mlx_source
import contextlib as _contextlib
import dataclasses as _dataclasses
import fcntl as _fcntl
import json as _json
import os as _os
import pathlib as _pathlib
import shlex as _shlex
import sys as _sys
import uuid as _uuid

VERSION = "bilqis.mlx.human-grade-a-trainer/v1"
LOCKFILE = ".grade-a-operator.lock"


@_contextlib.contextmanager
def operator_lock(folder: _pathlib.Path):
    folder.mkdir(parents=True, exist_ok=True)
    fd = _os.open(folder / LOCKFILE, _os.O_RDWR | _os.O_CREAT, 0o600)
    try:
        try:
            _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("HUMAN_TRAINER_ANOTHER_OPERATOR_ACTIVE") from exc
        yield
    finally:
        _fcntl.flock(fd, _fcntl.LOCK_UN)
        _os.close(fd)


def prepare_source(legacy_root: _pathlib.Path, source_checkpoint: _pathlib.Path, manifest_path: _pathlib.Path):
    legacy_root = _pathlib.Path(legacy_root).resolve(strict=True)
    source_checkpoint = _pathlib.Path(source_checkpoint).resolve(strict=True)
    manifest = _json.loads(_pathlib.Path(manifest_path).read_text(encoding="utf-8"))
    verified = _bilqis_mlx_grade_a_manifest.verify_manifest(manifest, legacy_root, source_checkpoint)
    if (_bilqis_mlx_backup.digest_file(source_checkpoint) != _bilqis_mlx_source.AUDITED_PARENT.sha256 or
            verified["verified_items"] != 216):
        raise ValueError("HUMAN_TRAINER_PINNED_SOURCE_NOT_VERIFIED")
    course = _compatibility_source_bootstrap.accepted_grade_a(manifest)
    if not course.executable or course.program_complete:
        raise ValueError("HUMAN_TRAINER_BOOTSTRAP_CURRICULUM_INVALID")
    if str(legacy_root) not in _sys.path:
        _sys.path.insert(0, str(legacy_root))
    _sys.dont_write_bytecode = True
    from bilqis_school import engine
    policy_path = legacy_root / "bilqis_school" / "engine.py"
    if _pathlib.Path(engine.__file__).resolve() != policy_path:
        raise ValueError("HUMAN_TRAINER_TEACHER_IMPLEMENTATION_ROOT_MISMATCH")
    # Pin the original adaptive policy and preserve its learned strategies.
    teacher_sha = _bilqis_mlx_backup.digest_file(policy_path)
    teacher_path = (legacy_root / "runs" /
                    "primitive-consolidation-v16-triplets" / "state.json")
    historical_state = _json.loads(teacher_path.read_text(encoding="utf-8"))
    teacher = historical_state.get("teacher")
    if (not isinstance(teacher, dict) or
            len(teacher.get("strategies", {})) < 4 or
            teacher.get("events", 0) < 1 or
            len(teacher.get("global_stats", {})) != len(teacher["strategies"])):
        raise ValueError("HUMAN_TRAINER_HISTORICAL_TEACHER_STATE_INCOMPLETE")
    provenance = {
        "teacher_state_file_sha256": _bilqis_mlx_backup.digest_file(teacher_path),
        "teacher_origin_step": historical_state.get("optimizer_step"),
        "teacher_origin_events": teacher["events"],
        "teacher_origin_strategy_count": len(teacher["strategies"]),
    }
    return manifest, course, engine, teacher_sha, teacher, provenance


def _init(run_dir, manifest, course, policy_sha, historical_teacher,
          teacher_provenance, checkpoint,
          *, source_root, reserve_gib, permitted_preexisting=()):
    import mlx.core as mx
    _runtime_checkpoints._clean_staged_bundles(run_dir)
    permitted = {LOCKFILE, *permitted_preexisting}
    if (run_dir / "state.json").exists() or any(
            p.name not in permitted for p in run_dir.iterdir()):
        raise ValueError("HUMAN_TRAINER_NEW_RUN_HAS_EXISTING_CONTENT")
    _runtime_disk.assert_headroom(run_dir, required_bytes=600_000_000, reserve_gib=reserve_gib)
    parameters, optimizer, config, graph, answer_ids = _learning_student_ops._initial_model(checkpoint)
    initial_pointer = _runtime_checkpoints._bundle_pointer(
        run_dir, "initial-"+_uuid.uuid4().hex[:12], parameters, optimizer, graph,
        reserve_gib=reserve_gib)
    release, program, _ = _compatibility_executable_projection.compile_projected_executable_release(
        course, course, source_root, graph)
    state = _curriculum_scheduler.start_new(program, initial_pointer)
    release, release_file, admission = _runtime_admission._executable_factory_admission(
        run_dir, release, initial_pointer, _runtime_state._fingerprint(graph), graph)
    parameter_shapes = {name: list(param.shape) for name, param in parameters.items()}
    championship_identity = _learning_championship_identity.build_school_identity(
        course_sha256=release.execution_plan.curriculum_sha256,
        semantic_graph_sha256=_runtime_state._fingerprint(graph),
        parameter_shapes=parameter_shapes,
        factory_release_sha256=release.release_sha256)
    receipt = {
        "schema": VERSION,
        "generation": 1,
        "run_id": _uuid.uuid4().hex,
        "accepted_authority": _compatibility_source_bootstrap.AUTHORITY,
        "curriculum_mode": course.version,
        "source_manifest_sha256": manifest["manifest_sha256"],
        "teacher_source_sha256": policy_sha,
        "school": _dataclasses.asdict(state),
        "model_bundle": initial_pointer.filename,
        "capability_best": {},
        "teacher": _json.loads(_runtime_state._canonical(historical_teacher)),
        "teacher_provenance": teacher_provenance,
        "config": config,
        "parameter_shapes": parameter_shapes,
        "semantic_graph_sha256": _runtime_state._fingerprint(graph),
        "factory_release_sha256": release.release_sha256,
        "factory_release_file": release_file,
        "factory_release_schema": release.schema,
        "factory_admission_v2": _dataclasses.asdict(admission),
        "championship_school_identity": championship_identity,
        "championship_checkpoint_origins": {},
        "answer_ids": answer_ids,
        "result": "ACTIVE_GRADE_" + state.grade,
        "last_exam": None,
    }
    init_event = {"event": "SCHOOL_NEW_RUN_INITIALIZED", "generation": 1,
                      "grade": state.grade,
                      "student": initial_pointer.sha256,
                      "optimizer_step": initial_pointer.optimizer_step,
                      "exam_rubric": program.grades[0].assessment_sha256,
                      "historical_rubric": manifest["exam_rubric_sha256"],
                      "source_projection_sha256":
                          release.execution_plan.projection_digests.source,
                      "provider_descriptors_sha256":
                          release.verification.provider_descriptors_sha256,
                      "source_version": course.version,
                      "factory_release_sha256": release.release_sha256}
    receipt = _runtime_checkpoints._persist(run_dir, _runtime_checkpoints._with_delivery_outbox(receipt, (init_event,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, receipt)
    return parameters, optimizer, graph, receipt


def _resume(run_dir, manifest, course, policy_sha, *, grade_a_course,
            source_root, successor_course=None, admitted_courses=None):
    import mlx.core as mx
    path = run_dir / "state.json"
    if not path.is_file():
        raise ValueError("HUMAN_TRAINER_RESUME_REQUIRES_PRIOR_RUN")
    receipt = _json.loads(path.read_text(encoding="utf-8"))
    if (receipt.get("schema") != VERSION or receipt.get("accepted_authority") != _compatibility_source_bootstrap.AUTHORITY
            or receipt.get("source_manifest_sha256") != manifest["manifest_sha256"]
            or receipt.get("teacher_source_sha256") != policy_sha):
        raise ValueError("HUMAN_TRAINER_RESUME_SOURCE_OR_POLICY_DRIFT")
    reconciled = _runtime_checkpoints._clean_staged_bundles(run_dir)
    if any(reconciled.values()):
        _runtime_checkpoints._record(run_dir, {"event": "SCHOOL_UNPUBLISHED_STAGING_RECONCILED",
                          "grade": "A", "generation": receipt["generation"],
                          **reconciled})
    receipt = _runtime_checkpoints._recover_orphaned_commit(run_dir, receipt)
    saved_mode = receipt.get("curriculum_mode")
    sealed_v1_release = _runtime_admission._verified_legacy_upgrade_release(run_dir, receipt)
    executable = (
        _runtime_admission._read_executable_factory_release_artifact(run_dir, receipt)
        if receipt.get("factory_admission_v2") is not None else None)
    old_mode = (
        executable is None and sealed_v1_release is None and saved_mode is None)
    old_course = (
        sealed_v1_release.course if sealed_v1_release is not None else
        _compatibility_source_bootstrap.accepted_grade_a(manifest) if old_mode else course)
    school_program = (
        _factory_schedule.schedule_program_from_executable_release(executable)
        if executable is not None else
        _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, old_course))
    school = _runtime_state._state_from_json(receipt["school"], school_program)
    directory = (run_dir / receipt["model_bundle"]).resolve(strict=True)
    if directory.parent != (run_dir / "bundles").resolve(strict=True):
        raise ValueError("HUMAN_TRAINER_BUNDLE_PATH_ESCAPES_RUN")
    parameters, optimizer, bundle, graph = _runtime_mlx_checkpoint.load_semantically_bound_bundle(directory)
    if executable is not None:
        executable.verify_semantic_catalog(graph)
    else:
        _compatibility_executable_projection.verify_legacy_resume_binding(
            receipt, old_course, graph, manifest, _runtime_state._fingerprint,
            sealed_v1_release=sealed_v1_release)
    if (bundle["source_digest"] != _bilqis_mlx_source.AUDITED_PARENT.sha256 or
            bundle["safetensors_sha256"] != school.current_student.sha256 or
            bundle["optimizer_step"] != school.current_student.optimizer_step or
            school.current_student.filename != receipt["model_bundle"] or
            _runtime_state._fingerprint(graph) != receipt["semantic_graph_sha256"] or
            {name:list(value.shape) for name,value in parameters.items()} !=
            receipt["parameter_shapes"] or
            len(parameters) != 39):
        raise ValueError("HUMAN_TRAINER_RESUME_MODEL_ADAMW_OR_SEMANTIC_DRIFT")
    if _json.loads((run_dir / "states" /
                   f"{receipt['generation']:07d}.json").read_text()) != receipt:
        raise ValueError("HUMAN_TRAINER_RESUME_IMMUTABLE_STATE_DIVERGED")
    if not old_mode:
        _runtime_assessment._verify_saved_cohort(
            run_dir, receipt, old_course,
            sealed_v1_release=sealed_v1_release)
    mx.eval(parameters, optimizer.state)
    from bilqis_mlx.compatibility.frontier_recovery import recover_legacy_frontier
    receipt = recover_legacy_frontier(mx, run_dir, receipt, old_course, parameters)
    school = _runtime_state._state_from_json(receipt["school"], school_program)
    if "capability_best" not in receipt:
        # Existing full-history run: reconstruct bests from actual sealed
        # checkpoint receipts before permitting reference-aware retirement.
        first_grade = school_program.grades[0]
        counts = {
            capability.id: capability.exam_item_count
            for capability in first_grade.capabilities}
        frontier = _learning_capability_frontier.historical_frontier(
            run_dir, expected_rubric=manifest["exam_rubric_sha256"],
            expected_capabilities=counts)
        _runtime_checkpoints._verify_best_custody(run_dir, {**receipt, "capability_best": frontier})
        receipt = _runtime_checkpoints._advance(run_dir, receipt, school, frontier=frontier)
        _runtime_checkpoints._record(run_dir, {"event": "SCHOOL_CAPABILITY_FRONTIER_MIGRATED",
                          "grade": "A", "generation": receipt["generation"],
                          "champion_roles": len(frontier),
                          "whole_student_unchanged": True})
    if old_mode:
        from bilqis_mlx.compatibility.resume_migration import (
            migrate_historical_grade_a,
        )
        receipt, school = migrate_historical_grade_a(
            run_dir, receipt, school, course, old_course, manifest)
    active_course = course if old_mode else old_course
    receipt, _, _ = _runtime_release_adoption._ensure_executable_release(
        run_dir, receipt, active_course, grade_a_course, source_root, graph)
    _runtime_checkpoints._verify_best_custody(run_dir, receipt)
    # Also finishes a retirement interrupted after the prior state commit.
    _runtime_checkpoints._publish_boundary(run_dir, receipt, (), ())
    if any("breadth" not in entry for entry in
           receipt.get("graduation_perfect", {}).values()):
        with (run_dir / "events.jsonl").open(encoding="utf-8") as history:
            ranked = _learning_capability_frontier.recover_graduation_breadth(
                receipt["graduation_perfect"],
                (_json.loads(line) for line in history if line.strip()))
        # Original immutable generations stay untouched until a new boundary.
        receipt = {**receipt, "graduation_perfect": ranked}
    receipt = _learning_championship_runtime._migrate_championship_governance(run_dir, receipt, active_course)
    # Governance migration can archive formerly active champion references.
    # Re-run custody verification against that enlarged immutable reference set
    # before this resumed state is allowed to proceed to any lesson or exam.
    _runtime_checkpoints._verify_best_custody(run_dir, receipt)
    return parameters, optimizer, graph, receipt


def _resume_command(run_dir: _pathlib.Path, source_root: _pathlib.Path,
                    learning_settings: _learning_learning_experiment.Settings | None,
                    boolean_association_bridge: bool = False,
                    source_prefetch_workers: int = 2,
                    autonomous_curriculum: bool = False) -> str:
    """Only name non-default options in the next human-owned shell command."""
    from bilqis_mlx.paths import LEGACY_SOURCE, active_run_dir

    command = "npm run train -- --human-run --resume"
    if learning_settings is None:
        command += " --no-retention"
    elif learning_settings != _learning_learning_experiment.Settings():
        command += (
            " --retention-probe-each " + str(learning_settings.probe_each) +
            " --retention-mature-max-loss " + str(learning_settings.mature_max_loss) +
            " --retention-introduction-extra-loss " +
                str(learning_settings.introduction_extra_loss) +
            " --retention-protected-cap-limit " +
                str(learning_settings.protected_cap_limit))
    if learning_settings is None or _pathlib.Path(run_dir).resolve() != active_run_dir().resolve():
        command += " --run-dir " + _shlex.quote(str(run_dir))
    if _pathlib.Path(source_root).resolve() != LEGACY_SOURCE.resolve():
        command += " --legacy-code-root " + _shlex.quote(str(source_root))
    if boolean_association_bridge:
        command += " --boolean-association-bridge"
    if autonomous_curriculum:
        command += " --autonomous-curriculum"
    if source_prefetch_workers != 2:
        command += " --source-prefetch-workers " + str(source_prefetch_workers)
    return command


def session_stop_reason(*, stage: str, elapsed_seconds: float, minutes: int,
                        visits: int, max_visits: int, grade: str = "A",
                        flash_mode: bool = False) -> str | None:
    """State-machine stop condition; a due exam must not be silently skipped."""
    if stage == "WHOLE_SCHOOL_MASTERED":
        return "WHOLE_SCHOOL_MASTERED"
    if stage == "AWAITING_TEACHER_SOUP":
        # Future full-program releases must not accidentally invoke a lesson
        # with no scheduled capability or convert a soup into a student.
        return "AWAITING_TEACHER_SOUP"
    if stage == "AWAITING_NEXT_GRADE":
        return "GRADE_" + grade + "_AWAITING_NEXT_GRADE"
    if stage == "DEFERRED_STAGNATION":
        return "STAGNATION_REVIEW_REQUIRED"
    if stage.startswith("ASSESS_") and not flash_mode:
        return None
    if elapsed_seconds >= minutes * 60:
        return "TIME_LIMIT_REACHED"
    if max_visits and visits >= max_visits:
        return "VISIT_LIMIT_REACHED"
    return None
