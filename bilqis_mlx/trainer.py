"""Human-operated Grade A MLX training; never invoked by agent test paths.

The in-memory student can perform several lessons between full assessments.
Only tested capability leaders receive permanent binary status.  One bounded
working recovery snapshot preserves the continuously learning student at
assessment and operator-stop boundaries; other routine visits are provisional.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import asdict, replace
from functools import lru_cache
import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import shlex
import sys
import time
import uuid

from .backup import digest_file
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.learning.champion_confidence import MAX_INFLUENCE as MAX_CHAMPION_INFLUENCE
from bilqis_mlx.learning.champion_confidence import vote_targets_typed
from bilqis_mlx.learning.champion_confidence import POLICY as CHAMPION_CONFIDENCE_POLICY
from bilqis_mlx.learning.champion_confidence import perfect_role_roster, vote_targets
from bilqis_mlx.learning.grade_soup import (grade_soup_recipe, partitioned_recipe,
                         PARTITIONED_SCHEMA, soup_shards, needs_refresh, soup_vote_count,
                         weighted_average, save_frozen_soup, verify_frozen_soup,
                         retire_stale_soups)
from bilqis_mlx.learning.learning_experiment import (
    VERSION as LEARNING_EXPERIMENT_VERSION, Settings as LearningSettings,
    contextual_pick, paired_outcomes, decide as decide_learning_trial,
    observe_context, selection_credit, fork_student, commit_trial,
    earlier_grade_capabilities, select_source_lesson, sampled_protection,
    missing_grade_capabilities,
)
from bilqis_mlx.learning.whole_student_retention import advance_peaks
from bilqis_mlx.learning.epoch_championships import (
    active_frontier as epoch_active_frontier,
    needed_incumbents as epoch_needed_incumbents,
    advance_epoch as advance_championship_epoch,
    sanitize_role_origins as sanitize_championship_role_origins,
)
from bilqis_mlx.learning.championship_identity import (
    build_school_identity, enforce_school_identity)
from .source_adapters.school import live_source_registry
from .compatibility.executable_projection import (
    compile_projected_executable_release,
    legacy_execution_metadata,
    legacy_course_for_profile,
    resolve_legacy_resume_course,
    verify_legacy_resume_binding,
)
from .factory.assessment import qualification_complete
from .factory.schedule import ScheduleProgram, schedule_program_from_executable_release
from .factory.executable_release import (
    answer_heads_from_executable_release,
    compile_successor_profile_release,
)
from .factory.live_answers import live_answer_registry
from .profiles.school import (
    boolean_entry_profile,
    with_disabled_future_grades,
)
from .profiles.catalog import (
    next_numeric_scope_profile,
    numeric_row_in_scope,
    numeric_entry_transition,
)
from .profiles.retention import fragile_preservation_capabilities
from .compatibility.live_releases import (
    boolean_identification_answer_heads,
    initial_course,
    numeric_answer_heads,
    predecessor_course,
)
from .factory.model import AssessmentClass, LearningEvidence
from bilqis_mlx.learning.mentor_epoch import EARNED_ONLY_POLICY, begin_initial_epoch
from bilqis_mlx.learning.championship_witnesses import (
    earning_witness, verified_battery, verified_witnesses)
from bilqis_mlx.learning.capability_frontier import (
    candidate_roles, historical_frontier, pinned, promote,
    recover_graduation_breadth, retire_bundles,
)
from bilqis_mlx.runtime.disk import assert_headroom, headroom_snapshot
from .diagnostics.teaching import inspect_lesson_step, summarize_teaching_visit
from .diagnostics.exam_events import (apply_paired_checkpoint_s3,
                                      summarize_completed_exam_safely)
from .generated_assessment import (
    GENERALIZATION_LIFECYCLE, PROMOTION_ATTEMPT_LIFECYCLE,
    ROUTINE_EVAL_LIFECYCLE, make_cohort, score as score_cohort,
)
from .grade_a_manifest import verify_manifest
from .compatibility.source_bootstrap import AUTHORITY, accepted_grade_a
from .live_curriculum import (
    assessment_rubric_for_scope, cohort_contract as _cohort_contract,
    lesson_contract, numeric_maximum,
)
from bilqis_mlx.runtime.mlx_checkpoint import save_new_bundle, load_semantically_bound_bundle
from bilqis_mlx.runtime.mlx_parity import (clip_gradients, forward_arrays,
                         native_optimizer_to_mlx)
from bilqis_mlx.curriculum.scheduler import (start_new, visit, assess, assess_withheld, next_capability,
                     adopt_appended_program, adopt_revised_program,
                     append_next_grade_with_debt,
                     append_next_grade, assessment_capabilities,
                     revise_admitted_grade, replace_admitted_grade,
                     reactivate_stagnation_debt, weakest_three,
                     require_assessment_after_flash,
                     assess_flash, SchoolState, Assessment, Score)
from bilqis_mlx.learning.stagnation_control import (
    activate_sole_grade_rehabilitation,
    begin_recovery_cycle, complete_recovery_cycle, end_of_run_alerts,
    grace_suppressed_capabilities, reconcile_optimizer_step_grace,
    reconcile_required_scope,
    quarantined_capabilities, record_visit as record_stagnation_visit,
    start_session as start_stagnation_session,
)
from .semantics.abi import HISTORICAL_PREFIX_SIZE
from .source import AUDITED_PARENT
from .vocabulary_growth import extend_mlx_student
from bilqis_mlx.learning.teacher_feedback import (
    FairMissRequest, TeacherDecisionInput, active_warning_signals, reconcile_unresolved_misses,
    select_fair_miss_window, summarize_teacher_decision,
    summarize_teacher_outcomes,
)
from bilqis_mlx.runtime.timing_trace import trace_mark, trace_span
from .runtime.state import (
    _canonical, _fingerprint, _durable_json, _state_from_json, _seed,
)
from .runtime.admission import (
    admitted_release_supports_teaching_option,
    _executable_factory_admission,
    _factory_release, _persist_factory_release, _factory_admission,
    _read_executable_factory_release_artifact,
    _require_executable_factory_admission, _require_factory_admission,
)
from .runtime.assessment import (
    load_championship_cohort,
    _candidate_executable_cohort, _generalization_executable_cohort,
    _promotion_executable_cohort, _routine_executable_cohort,
    _draw_live_rows, _persist_live_cohort, _load_current_cohort,
    _verify_saved_cohort, _grade_test_cohort, _promotion_cohort,
    _generalization_cohort, _candidate_cohort, _introduced_cohort,
    _without_stagnant_capabilities, _require_active_stagnation_scope,
)

VERSION = "bilqis.mlx.human-grade-a-trainer/v1"
LOCKFILE = ".grade-a-operator.lock"
_event_view = ContextVar("grade_a_event_view", default=None)


@contextmanager
def operator_view(callback):
    token = _event_view.set(callback)
    try:
        yield
    finally:
        _event_view.reset(token)


def _ensure_factory_admission(run_dir, receipt, course, graph):
    """Neural-inert migration for historical runs that predate FactoryRelease."""
    if receipt.get("factory_admission") is not None:
        _require_factory_admission(run_dir, receipt, course)
        return receipt
    school = _state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
    release, release_file, admission = _factory_admission(
        run_dir, course, school.current_student, _fingerprint(graph))
    migrated = {**receipt,
                "factory_release_sha256": release.release_sha256,
                "factory_release_file": release_file,
                "factory_admission": asdict(admission)}
    record = _advance(run_dir, migrated, school, persist=False)
    event = {"event": "SCHOOL_FACTORY_RELEASE_MIGRATED",
             "generation": record["generation"],
             "grade": school.grade,
             "factory_release_sha256": release.release_sha256,
             "student_sha256": school.current_student.sha256,
             "optimizer_step": school.current_student.optimizer_step,
             "actual_neural_updates": 0}
    record = _persist(run_dir, _with_delivery_outbox(record, (event,)))
    _reconcile_delivery_outbox(run_dir, record)
    _require_factory_admission(run_dir, record, course)
    return record


def _migrate_executable_release(run_dir, receipt, course, grade_a_course, source_root, graph):
    school = _state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
    release, program, _ = compile_projected_executable_release(
        course, grade_a_course, source_root, graph)
    rebound = replace(school, course_digest=program.digest())
    _state_from_json(asdict(rebound), program)
    release, release_file, admission = _executable_factory_admission(
        run_dir, release, rebound.current_student,
        receipt["semantic_graph_sha256"], graph)
    migrated = dict(receipt)
    migrated.update({
        "factory_release_sha256": release.release_sha256,
        "factory_release_file": release_file,
        "factory_release_schema": release.schema,
        "factory_admission_v2": asdict(admission),
        **legacy_execution_metadata(course),
    })
    return migrated, release, program, rebound


def _ensure_executable_release(run_dir, receipt, course, grade_a_course, source_root, graph):
    if receipt.get("factory_admission_v2") is None:
        migrated, release, program, rebound = _migrate_executable_release(
            run_dir, receipt, course, grade_a_course, source_root, graph)
        receipt = _advance(run_dir, migrated, rebound)
        _require_executable_factory_admission(run_dir, receipt, graph)
        return receipt, release, program
    release = _require_executable_factory_admission(run_dir, receipt, graph)
    return receipt, release, schedule_program_from_executable_release(release)


@lru_cache(maxsize=32)
def _cached_schedule_program(run_dir_string, release_sha256, release_file):
    release = _read_executable_factory_release_artifact(
        Path(run_dir_string), {
            "factory_release_sha256": release_sha256,
            "factory_release_file": release_file,
        })
    return schedule_program_from_executable_release(release)


def _schedule_for_receipt(run_dir, receipt, course):
    if isinstance(course, ScheduleProgram):
        return course
    if receipt.get("factory_admission_v2") is not None:
        return _cached_schedule_program(
            str(Path(run_dir).resolve()),
            receipt["factory_release_sha256"],
            receipt["factory_release_file"],
        )
    from .compatibility.schedule_program import schedule_program_from_legacy_course
    return schedule_program_from_legacy_course(course)


def _championship_identity(receipt, course):
    return build_school_identity(
        course_sha256=(receipt.get("factory_admission_v2") or {}).get(
            "curriculum_sha256", course.digest()),
        semantic_graph_sha256=receipt["semantic_graph_sha256"],
        parameter_shapes=receipt["parameter_shapes"],
        factory_release_sha256=receipt["factory_release_sha256"])


def _live_championship_identity(receipt, course, graph, parameters):
    return build_school_identity(
        course_sha256=(receipt.get("factory_admission_v2") or {}).get(
            "curriculum_sha256", course.digest()),
        semantic_graph_sha256=_fingerprint(graph),
        parameter_shapes={name: list(value.shape) for name, value in parameters.items()},
        factory_release_sha256=receipt["factory_release_sha256"])


def _championship_pair_key(capability, left_sha256, right_sha256):
    return capability + "|" + "|".join(sorted((left_sha256, right_sha256)))


def _historical_championship_authority(run_dir):
    """Recover immutable matchup and checkpoint-origin facts from durable events."""
    origins = {}
    settled = {}
    duplicate_settlements = 0
    path = run_dir / "events.jsonl"
    if not path.is_file():
        return {}, {}, {}, 0
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            event = json.loads(line)
            if (event.get("event") == "SCHOOL_TEACHER_VISIT_COMMITTED" and
                    type(event.get("retained_optimizer_updates")) is int and
                    event["retained_optimizer_updates"] > 0 and
                    isinstance(event.get("recovered_at_student_sha256"), str) and
                    isinstance(event.get("grade"), str) and event["grade"]):
                origins.setdefault(event["recovered_at_student_sha256"], set()).add(
                    event["grade"])
            epoch = event.get("championship_epoch")
            if not isinstance(epoch, dict):
                continue
            for decision in epoch.get("cross_origin_decisions", ()):
                if (not isinstance(decision, dict) or
                        decision.get("decision") not in ("TITLE_WON", "TITLE_DEFENDED")):
                    continue
                capability = decision.get("capability")
                incumbent = decision.get("incumbent_sha256")
                challenger = decision.get("challenger_sha256")
                if not all(isinstance(value, str) and value for value in
                           (capability, incumbent, challenger)):
                    raise ValueError("CHAMPIONSHIP_HISTORICAL_SETTLEMENT_INVALID")
                key = _championship_pair_key(capability, incumbent, challenger)
                record = {**decision,
                          "source_generation": event.get("generation"),
                          "historical_backfill": True}
                if key in settled:
                    duplicate_settlements += 1
                else:
                    settled[key] = record
    proven = {sha: next(iter(grades)) for sha, grades in origins.items()
              if len(grades) == 1}
    ambiguous = {sha: sorted(grades) for sha, grades in origins.items()
                 if len(grades) > 1}
    return proven, ambiguous, settled, duplicate_settlements


def _migrate_championship_governance(run_dir, receipt, course):
    """Neural-inert rev7 migration from durable run evidence."""
    identity = _championship_identity(receipt, course)
    proven, ambiguous, historical_settled, duplicate_count = (
        _historical_championship_authority(run_dir))
    updated = deepcopy(receipt)
    changed = updated.get("championship_school_identity") != identity
    updated["championship_school_identity"] = identity

    origin_map = dict(updated.get("championship_checkpoint_origins", {}))
    for sha, grade in proven.items():
        existing = origin_map.get(sha)
        if existing is not None and existing != grade:
            raise ValueError("CHAMPIONSHIP_CHECKPOINT_ORIGIN_PROVENANCE_CONFLICT")
        if existing is None:
            origin_map[sha] = grade
            changed = True
    if updated.get("championship_checkpoint_origins") != origin_map:
        updated["championship_checkpoint_origins"] = origin_map
    if ambiguous:
        if updated.get("championship_checkpoint_origin_ambiguities") != ambiguous:
            changed = True
        updated["championship_checkpoint_origin_ambiguities"] = ambiguous
    else:
        if "championship_checkpoint_origin_ambiguities" in updated:
            changed = True
        updated.pop("championship_checkpoint_origin_ambiguities", None)

    program = _schedule_for_receipt(run_dir, updated, course)
    school = _state_from_json(updated["school"], program)
    current_origin = origin_map.get(school.current_student.sha256)
    if current_origin is not None:
        if updated.get("last_retained_update_grade") != current_origin:
            changed = True
        updated["last_retained_update_grade"] = current_origin
    elif school.current_student.sha256 in ambiguous:
        if "last_retained_update_grade" in updated:
            changed = True
        updated.pop("last_retained_update_grade", None)

    epoch = updated.get("mentor_epoch")
    reset = False
    origins_invalidated = False
    if epoch is not None:
        epoch = deepcopy(epoch)
        ledger = epoch.setdefault("settled_matchups", {})
        if not isinstance(ledger, dict):
            raise ValueError("CHAMPIONSHIP_SETTLED_MATCH_LEDGER_INVALID")
        for key, settlement in historical_settled.items():
            if key not in ledger:
                ledger[key] = settlement
                changed = True
        for role in epoch.get("active_roles", {}).values():
            if role.get("origin_grade") is None:
                grade = origin_map.get(role.get("checkpoint", {}).get("sha256"))
                if grade is not None:
                    role["origin_grade"] = grade
                    changed = True
        epoch, reset = enforce_school_identity(
            epoch, identity, generation=updated["generation"] + 1,
            student=asdict(school.current_student))
        if reset:
            changed = True
        else:
            epoch, origins_invalidated = sanitize_championship_role_origins(
                epoch, grades={
                    grade.id: tuple(
                        capability.id for capability in grade.capabilities)
                    for grade in program.grades})
            if origins_invalidated:
                changed = True
        updated["mentor_epoch"] = epoch

    if not changed:
        return receipt
    record = _advance(run_dir, updated, school, persist=False)
    migration = {
        "event": "SCHOOL_CHAMPIONSHIP_GOVERNANCE_MIGRATED",
        "generation": record["generation"],
        "grade": school.grade,
        "student_sha256": school.current_student.sha256,
        "optimizer_step": school.current_student.optimizer_step,
        "championship_school_identity_sha256": identity["sha256"],
        "checkpoint_origins_proven": len(origin_map),
        "checkpoint_origins_ambiguous": len(ambiguous),
        "settled_matchups_backfilled": len(historical_settled),
        "duplicate_historical_settlements_ignored": duplicate_count,
        "holistic_authority_reset": reset,
        "invalid_origin_roles_archived": origins_invalidated,
        "actual_neural_updates": 0,
    }
    record = _persist(run_dir, _with_delivery_outbox(record, (migration,)))
    _reconcile_delivery_outbox(run_dir, record)
    return record


def _bind_checkpoint_origin(receipt, checkpoint):
    """Attach the last proven retained-update grade to a newly sealed checkpoint."""
    grade = receipt.get("last_retained_update_grade")
    if grade is None:
        return receipt
    if not isinstance(grade, str) or not grade:
        raise ValueError("CHAMPIONSHIP_LAST_RETAINED_GRADE_INVALID")
    origins = dict(receipt.get("championship_checkpoint_origins", {}))
    existing = origins.get(checkpoint.sha256)
    if existing is not None and existing != grade:
        raise ValueError("CHAMPIONSHIP_CHECKPOINT_ORIGIN_PROVENANCE_CONFLICT")
    origins[checkpoint.sha256] = grade
    return {**receipt, "championship_checkpoint_origins": origins}


@contextmanager
def operator_lock(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    fd = os.open(folder / LOCKFILE, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("HUMAN_TRAINER_ANOTHER_OPERATOR_ACTIVE") from exc
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def prepare_source(legacy_root: Path, source_checkpoint: Path, manifest_path: Path):
    legacy_root = Path(legacy_root).resolve(strict=True)
    source_checkpoint = Path(source_checkpoint).resolve(strict=True)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    verified = verify_manifest(manifest, legacy_root, source_checkpoint)
    if (digest_file(source_checkpoint) != AUDITED_PARENT.sha256 or
            verified["verified_items"] != 216):
        raise ValueError("HUMAN_TRAINER_PINNED_SOURCE_NOT_VERIFIED")
    course = accepted_grade_a(manifest)
    if not course.executable or course.program_complete:
        raise ValueError("HUMAN_TRAINER_BOOTSTRAP_CURRICULUM_INVALID")
    if str(legacy_root) not in sys.path:
        sys.path.insert(0, str(legacy_root))
    sys.dont_write_bytecode = True
    from bilqis_school import engine
    policy_path = legacy_root / "bilqis_school" / "engine.py"
    if Path(engine.__file__).resolve() != policy_path:
        raise ValueError("HUMAN_TRAINER_TEACHER_IMPLEMENTATION_ROOT_MISMATCH")
    # Pin the original adaptive policy and preserve its learned strategies.
    teacher_sha = digest_file(policy_path)
    teacher_path = (legacy_root / "runs" /
                    "primitive-consolidation-v16-triplets" / "state.json")
    historical_state = json.loads(teacher_path.read_text(encoding="utf-8"))
    teacher = historical_state.get("teacher")
    if (not isinstance(teacher, dict) or
            len(teacher.get("strategies", {})) < 4 or
            teacher.get("events", 0) < 1 or
            len(teacher.get("global_stats", {})) != len(teacher["strategies"])):
        raise ValueError("HUMAN_TRAINER_HISTORICAL_TEACHER_STATE_INCOMPLETE")
    provenance = {
        "teacher_state_file_sha256": digest_file(teacher_path),
        "teacher_origin_step": historical_state.get("optimizer_step"),
        "teacher_origin_events": teacher["events"],
        "teacher_origin_strategy_count": len(teacher["strategies"]),
    }
    return manifest, course, engine, teacher_sha, teacher, provenance


def _initial_model(source_checkpoint: Path):
    import mlx.core as mx
    from bilqis_development.continuation import load
    model, optimizer, payload = load(source_checkpoint)
    if (payload["config"]["precision"] != "fp32" or
            len(payload["graph"]["tokens"]) != HISTORICAL_PREFIX_SIZE):
        raise ValueError("HUMAN_TRAINER_HISTORICAL_SEMANTIC_ABI_INVALID")
    names = {id(p): name for name, p in model.named_parameters()}
    order = [names[id(p)] for p in optimizer.param_groups[0]["params"]]
    _, mlx_optimizer = native_optimizer_to_mlx(
        optimizer.state_dict(), model.state_dict(), parameter_order=order)
    parameters = {name: mx.array(weight.detach().numpy(), dtype=mx.float32)
                  for name, weight in model.state_dict().items()}
    mx.eval(parameters, mlx_optimizer.state)
    return parameters, mlx_optimizer, payload["config"], payload["graph"], (
        model.answer_ids.cpu().numpy().tolist())


def _make_batch(rows: list[dict]):
    import numpy as np
    if not rows:
        raise ValueError("HUMAN_TRAINER_EMPTY_BATCH")
    lengths = np.asarray([len(row["tokens"]) for row in rows], dtype=np.int32)
    if min(lengths) < 1 or max(lengths) > 96:
        raise ValueError("HUMAN_TRAINER_SEQUENCE_OUTSIDE_LEGACY_CONTEXT")
    ids = np.zeros((len(rows), int(lengths.max())), dtype=np.int32)
    labels = np.zeros(len(rows), dtype=np.int32)
    for i, row in enumerate(rows):
        ids[i, :lengths[i]] = row["tokens"]
        labels[i] = {"FALSE": 0, "TRUE": 1}[row["gold"]]
    return ids, lengths, labels


def _predictions(mx, parameters, rows, config, answer_ids):
    if any(row.get("answer_kind", "binary") != "binary" for row in rows):
        from .typed_answer_training import predict_rows
        return predict_rows(mx, parameters, rows, config["answer_heads"], config)
    import numpy as np
    result = {}
    for offset in range(0, len(rows), 24):
        batch = rows[offset:offset+24]
        ids, lengths, _ = _make_batch(batch)
        logits = forward_arrays(mx, parameters, ids, lengths,
                                heads=config["heads"], layers=config["layers"],
                                answer_ids=answer_ids)
        mx.eval(logits)
        binary = np.asarray(logits)[:, :2].argmax(axis=-1)
        result.update({row["id"]: ("TRUE" if int(value) else "FALSE")
                       for row, value in zip(batch, binary)})
    return result


def _train_score(mx, parameters, rows, config, answer_ids) -> float:
    result = _predictions(mx, parameters, rows, config, answer_ids)
    return sum(result[r["id"]] == r["gold"] for r in rows) / len(rows)


def choose_lesson_batch(rows: list[dict], policy: dict,
                        seed: int, *, batch_size=32) -> list[dict]:
    """Balance both truth values; policy shapes selection, never gold answers."""
    if not rows or batch_size < 2 or batch_size % 2:
        raise ValueError("HUMAN_TRAINER_INVALID_LESSON_BATCH_SIZE")
    rng = random.Random(seed)
    if any(row.get("answer_kind", "binary") != "binary" for row in rows):
        # Sample linked direct/TRUE/FALSE views from the same verified meaning.
        # This is an answer contract, independent of old/new lesson allocation.
        sources = {}
        for row in rows:
            sources.setdefault(row["source_id"], []).append(row)
        chosen = []
        groups = list(sources.values())
        while len(chosen) < batch_size:
            chosen.extend(rng.choice(groups))
        chosen = chosen[:batch_size]
        rng.shuffle(chosen)
        return chosen
    truths = {label: [r for r in rows if r["gold"] == label]
              for label in ("FALSE", "TRUE")}
    if any(not values for values in truths.values()):
        raise ValueError("HUMAN_TRAINER_MISSING_BINARY_TRAINING_CLASS")
    if policy["depth"] >= 3:
        # No invented composite concepts: emphasize long *attested* records.
        for value in truths.values():
            value.sort(key=lambda r: (-len(r["tokens"]), r["id"]))
    if policy["contrast"] >= 0.5:
        chosen = [rng.choice(truths[label]) for _ in range(batch_size // 2)
                  for label in ("TRUE", "FALSE")]
    else:
        chosen = [rng.choice(rows) for _ in range(batch_size)]
    rng.shuffle(chosen)
    return chosen


def replay_missed_lessons(chosen: list[dict], missed: list[dict], *,
                          reserved_ids=()) -> list[dict]:
    """Guarantee every requested missed construction reaches this optimizer batch."""
    if len(missed) > len(chosen):
        raise ValueError("HUMAN_TRAINER_MISS_REPLAY_EXCEEDS_BATCH")
    result = list(chosen)
    reserved = set(reserved_ids)
    consumed = {index for index, row in enumerate(result)
                if row.get("id") in reserved}
    for item in missed:
        replacement = next((i for i, row in enumerate(result)
                            if i not in consumed and row["gold"] == item["gold"]), None)
        if replacement is None:
            raise ValueError("HUMAN_TRAINER_MISS_REPLAY_ANSWER_CLASS_CAPACITY")
        result[replacement] = item
        consumed.add(replacement)
    return result


@lru_cache(maxsize=16)
def _cached_frozen_champion(path_string, sha, step, file_size, file_mtime_ns):
    """Bound repeat source reads; never cache optimizer moments."""
    weights, own_optimizer, meta, source_graph = load_semantically_bound_bundle(
        Path(path_string))
    if (meta["safetensors_sha256"] != sha or
            meta["optimizer_step"] != step or
            meta["source_digest"] != AUDITED_PARENT.sha256):
        raise ValueError("CHAMPION_CONFIDENCE_BUNDLE_DRIFT")
    del own_optimizer
    return weights, source_graph


def _frozen_confidence_champions(run_dir, receipt, grade, graph):
    """Read active perfect capability specialists for this lesson's own grade only."""
    mentors = []
    frontier = receipt.get("graduation_perfect", {})
    soups = receipt.get("grade_soups", {})
    if frontier and not soups:
        raise ValueError("CHAMPION_CONFIDENCE_GRADE_SOUPS_MISSING_FOR_ACTIVE_ROLES")
    for item in perfect_role_roster(frontier, soups):
        votes = item.get("source_grade_votes", {}).get(grade, 0)
        capabilities = tuple(
            cap for cap in item.get("capabilities", ()) if cap.startswith(grade + "."))
        if not votes or len(capabilities) != votes:
            continue
        pointer = item["checkpoint"]
        path = run_dir / pointer["filename"]
        if (path.is_symlink() or path.parent != run_dir / "bundles" or
                not pointer["filename"].startswith("bundles/")):
            raise ValueError("CHAMPION_CONFIDENCE_UNSAFE_BUNDLE")
        content = (path / "model-and-own-adamw.safetensors").stat()
        weights, source_graph = _cached_frozen_champion(
            str(path), pointer["sha256"], pointer["optimizer_step"],
            content.st_size, content.st_mtime_ns)
        if not _compatible_graphs(source_graph, graph):
            raise ValueError("CHAMPION_CONFIDENCE_BUNDLE_DRIFT")
        mentors.append({"weights": weights, "graph": source_graph,
                        "breadth": votes,
                        "source_grade_votes": {grade: votes},
                        "capabilities": capabilities,
                        "checkpoint_sha256": pointer["sha256"]})
    return tuple(mentors)


def _mentor_sources_for_visit(run_dir, receipt, grade, graph, grade_count):
    """Select only current-epoch champions and soups after curriculum reset."""
    epoch = receipt.get("mentor_epoch")
    if epoch is None:
        return (_frozen_confidence_champions(run_dir, receipt, grade, graph),
                *_frozen_grade_soup_votes(run_dir, receipt, grade, grade_count))
    if epoch.get("source_graph_sha256") != _fingerprint(graph):
        raise ValueError("MENTOR_EPOCH_SOURCE_GRAPH_DRIFT")
    epoch_identity = epoch.get("championship_school_identity")
    receipt_identity = receipt.get("championship_school_identity")
    if (not isinstance(epoch_identity, dict) or
            not isinstance(receipt_identity, dict) or
            epoch_identity != receipt_identity):
        raise ValueError("MENTOR_EPOCH_SCHOOL_IDENTITY_RESET_REQUIRED")
    for capability, role in epoch.get("active_roles", {}).items():
        if role.get("origin_grade") != capability.partition(".")[0]:
            raise ValueError("MENTOR_EPOCH_TITLE_ORIGIN_PROVENANCE_INVALID")
    if epoch.get("guidance_policy") != EARNED_ONLY_POLICY:
        raise ValueError("MENTOR_EPOCH_FRESH_CHAMPIONS_RESET_REQUIRED")
    active = {"graduation_perfect": epoch_active_frontier(epoch),
              "grade_soups": epoch.get("active_grade_soups", {})}
    if not active["graduation_perfect"] and not active["grade_soups"]:
        return (), (), ()
    mentors = list(_frozen_confidence_champions(run_dir, active, grade, graph))
    soups, receipts = _frozen_grade_soup_votes(
        run_dir, active, grade, grade_count)
    return tuple(mentors), soups, receipts


def _cook_new_grade_soups(mx, run_dir, receipt, frontier, course, graph,
                          *, reserve_gib, existing=None):
    """Freeze newly broader or displaced grade-champion weight recipes."""
    current = dict(receipt.get("grade_soups", {}) if existing is None else existing)
    refreshed = []
    program = _schedule_for_receipt(run_dir, receipt, course)
    for grade in program.grades:
        plan = grade_soup_recipe(
            frontier, grade.id, tuple(cap.id for cap in grade.capabilities))
        if not needs_refresh(current.get(grade.id), plan):
            continue
        members = []
        catalogs = {}
        graph_digests = {}
        for item in plan["members"]:
            pointer = item["checkpoint"]
            path = run_dir / pointer["filename"]
            if path.is_symlink() or path.parent != run_dir / "bundles":
                raise ValueError("GRADE_SOUP_UNSAFE_CHAMPION_BUNDLE")
            weights, own_adamw, manifest, original_graph = load_semantically_bound_bundle(path)
            if (manifest["source_digest"] != AUDITED_PARENT.sha256 or
                    manifest["safetensors_sha256"] != pointer["sha256"] or
                    manifest["optimizer_step"] != pointer["optimizer_step"] or
                    not _compatible_graphs(original_graph, graph)):
                raise ValueError("GRADE_SOUP_CHAMPION_CUSTODY_DRIFT")
            sha = pointer["sha256"]
            graph_digest = _fingerprint(original_graph)
            if (graph_digest in catalogs and
                    original_graph != catalogs[graph_digest]):
                raise ValueError("GRADE_SOUP_INGREDIENT_GRAPH_DIGEST_COLLISION")
            catalogs[graph_digest] = original_graph
            graph_digests[sha] = graph_digest
            members.append((sha, item["votes"], weights))
            del own_adamw
        if len(catalogs) == 1:
            graph_digest, catalog = next(iter(catalogs.items()))
            combined = weighted_average(mx, [
                (votes, weights) for _, votes, weights in members])
            snapshot = save_frozen_soup(run_dir, plan, combined,
                                        reserve_gib=reserve_gib,
                                        token_count=len(catalog["tokens"]))
            snapshot["source_graph_sha256"] = graph_digest
        else:
            # Each exact source graph owns its own frozen weight mixture.
            # Append-only older prefixes may advise their supported tokens,
            # but must never masquerade as expanded embedding matrices.
            by_sha = {sha: (votes, weights) for sha, votes, weights in members}
            shards = []
            for shard_plan in partitioned_recipe(plan, graph_digests):
                graph_digest = shard_plan["source_graph_sha256"]
                combined = weighted_average(mx, [
                    by_sha[item["checkpoint"]["sha256"]]
                    for item in shard_plan["members"]])
                frozen = save_frozen_soup(
                    run_dir, shard_plan, combined, reserve_gib=reserve_gib,
                    token_count=len(catalogs[graph_digest]["tokens"]))
                frozen["source_graph_sha256"] = graph_digest
                shards.append(frozen)
            snapshot = {**plan, "schema": PARTITIONED_SCHEMA,
                        "shards": shards,
                        "partition_policy": "EXACT_SOURCE_GRAPH_NO_MIXED_PARAMETER_AVERAGE"}
        previous = current.get(grade.id)
        if previous is not None:
            snapshot["coverage_peak"] = max(
                previous["coverage_peak"], snapshot["coverage_peak"])
            snapshot["previous"] = [
                {"filename": part["filename"], "sha256": part["sha256"]}
                for part in soup_shards(previous)]
        current[grade.id] = snapshot
        refreshed.append(grade.id)
    return current, tuple(refreshed)


@lru_cache(maxsize=12)
def _cached_grade_soup(path_string, sha, token_count, stat_size, stat_mtime_ns):
    """Verify a frozen soup once per exact file identity for repeated lessons."""
    import mlx.core as mx
    path = Path(path_string)
    if digest_file(path) != sha:
        raise ValueError("GRADE_SOUP_SAVED_ARTIFACT_CHANGED")
    weights = mx.load(str(path))
    if ("embedding.weight" not in weights or
            weights["embedding.weight"].shape[0] != token_count or
            any(array.dtype != mx.float32 for array in weights.values())):
        raise ValueError("GRADE_SOUP_FROZEN_MODEL_SHAPE_DRIFT")
    return weights


def _frozen_grade_soup_votes(run_dir, receipt, lesson_grade, school_grade_count):
    """Use frozen base votes; only the foreign-grade divisor is live."""
    mentors, receipts = [], []
    for grade, snapshot in sorted(receipt.get("grade_soups", {}).items()):
        if grade != snapshot.get("grade"):
            raise ValueError("GRADE_SOUP_GRADE_POINTER_DRIFT")
        for shard in soup_shards(snapshot):
            path = run_dir / shard["filename"]
            if (path.parent != run_dir / "soups" or path.is_symlink()):
                raise ValueError("GRADE_SOUP_UNSAFE_SAVED_PATH")
            stat = path.stat()
            weights = _cached_grade_soup(
                str(path), shard["sha256"], shard["token_count"],
                stat.st_size, stat.st_mtime_ns)
            votes = soup_vote_count(shard, lesson_grade, school_grade_count)
            mentors.append({"weights": weights, "vocab_size": shard["token_count"],
                            "breadth": votes})
            receipts.append({"soup_grade": grade,
                             "recipe_sha256": snapshot["recipe_sha256"],
                             "ingredient_recipe_sha256": shard["recipe_sha256"],
                             "frozen_base_votes": shard["vote_count"],
                             "effective_votes": votes,
                             "source_graph_sha256": shard.get("source_graph_sha256")})
    return tuple(mentors), tuple(receipts)


def _confidence_guidance(mx, mentors, picked, config, answer_ids,
                         *, scope_size, teacher_distill):
    """Gold-agreeing frozen logits are small, policy-shaped gradient advice."""
    if not mentors or teacher_distill <= 0 or any(
            row.get("answer_kind", "binary") != "binary" for row in picked):
        return None
    import numpy as np
    ids, lengths, labels = _make_batch(picked)
    vote_logits = []
    for mentor in mentors:
        vocabulary = (mentor.get("vocab_size") or len(mentor["graph"]["tokens"]))
        if (max(answer_ids) >= vocabulary or
                any(max(row["tokens"]) >= vocabulary for row in picked)):
            continue
        logits = forward_arrays(mx, mentor["weights"], ids, lengths,
                                heads=config["heads"], layers=config["layers"],
                                answer_ids=answer_ids)
        mx.eval(logits)
        vote_logits.append((mentor["breadth"], np.asarray(logits)[:, :2]))
    target, influence = vote_targets(vote_logits, labels,
                                     eligible_capabilities=scope_size,
                                     teacher_distill=teacher_distill)
    return (target, influence) if np.any(influence) else None


def _typed_confidence_guidance(mx, mentors, picked, config, *, scope_size,
                               teacher_distill):
    """Source-gold-agreeing grade-soup/same-grade advice for typed heads.

    The trained student and the frozen mentors are distinct. Historical
    smaller-vocabulary soups participate only in heads their tokens support.
    """
    import numpy as np
    from .typed_answer_training import prepare_typed_batches
    if teacher_distill <= 0 or not mentors:
        return None
    batches = prepare_typed_batches(picked, config["answer_heads"])
    guidance = {}
    for kind, batch in batches.items():
        eligible = []
        answer_ids = batch["answer_ids"]
        if not answer_ids:
            continue
        for mentor in mentors:
            vocabulary = mentor.get("vocab_size") or len(mentor["graph"]["tokens"])
            if (max(answer_ids) >= vocabulary or
                    int(batch["ids"].max()) >= vocabulary):
                continue
            logits = forward_arrays(
                mx, mentor["weights"], batch["ids"], batch["lengths"],
                heads=config["heads"], layers=config["layers"], answer_ids=answer_ids)
            mx.eval(logits)
            eligible.append((mentor["breadth"], np.asarray(logits)))
        if not eligible:
            continue
        target, weight = vote_targets_typed(
            eligible, batch["target_indices"], classes=len(answer_ids),
            eligible_capabilities=scope_size, teacher_distill=teacher_distill)
        if np.any(weight):
            guidance[kind] = (target, weight)
    return guidance or None


def _compatible_graphs(earlier, current):
    """A frozen earlier teacher retains its exact historical semantic prefix."""
    count = len(earlier["tokens"])
    return (earlier["tokens"] == current["tokens"][:count] and
            earlier["nodes"] == current["nodes"][:count] and
            all(current["row_contract_sha256"].get(s) == value
                for s, value in earlier["row_contract_sha256"].items()))


def _compatible_answer_config(config, graph):
    if "answer_heads" not in config:
        return config
    heads = config["answer_heads"]
    vocabulary = len(graph["tokens"])

    def readable(kind):
        ids = heads.get(kind, {}).get("token_ids", ())
        return bool(ids) and max(ids) < vocabulary

    if "numeric_active" in heads and readable("numeric_active"):
        maximum = len(heads["numeric_active"]["values"])-1
        compatible = numeric_answer_heads(graph, maximum, prior_heads=heads)
    elif "boolean_operator" in heads and readable("boolean_operator"):
        compatible = boolean_identification_answer_heads(graph)
    else:
        raise ValueError("HUMAN_TRAINER_UNKNOWN_TYPED_ANSWER_CONFIG")
    return {**config, "answer_heads": compatible}


def _train_step(mx, parameters, optimizer, rows, config, answer_ids,
                *, champion_guidance=None):
    if any(row.get("answer_kind", "binary") != "binary" for row in rows):
        from .typed_answer_training import typed_step
        return typed_step(mx, parameters, optimizer, rows, config["answer_heads"],
                          config, champion_guidance=champion_guidance)
    import numpy as np
    ids, lengths, labels = _make_batch(rows)
    expected = mx.array(np.eye(2, dtype=np.float32)[labels])
    advice = None
    if champion_guidance is not None:
        target, weight = champion_guidance
        target = np.asarray(target, dtype=np.float32)
        weight = np.asarray(weight, dtype=np.float32)
        if (target.shape != (len(rows), 2) or weight.shape != (len(rows),) or
                not np.isfinite(target).all() or not np.isfinite(weight).all() or
                (weight < 0).any() or (weight > MAX_CHAMPION_INFLUENCE + 1e-6).any() or
                (target < 0).any() or
                not np.allclose(target.sum(axis=-1), 1., atol=1e-6)):
            raise ValueError("CHAMPION_CONFIDENCE_TRAINING_GUIDANCE_INVALID")
        advice = (mx.array(target), mx.array(weight))

    def objective(weights):
        logits = forward_arrays(mx, weights, ids, lengths,
                                heads=config["heads"], layers=config["layers"],
                                answer_ids=answer_ids)
        typed = logits[:, :2]
        normalizer = mx.logsumexp(typed, axis=-1)
        loss = mx.mean(normalizer - mx.sum(typed * expected, axis=-1))
        if advice is not None:
            # Frozen confidence teaches only through this bounded gradient;
            # no exam inference ever reads the champion-adjusted logits.
            soft_target, strength = advice
            loss = loss + mx.mean(strength *
                 (normalizer - mx.sum(typed * soft_target, axis=-1)))
        return loss

    loss, gradients = mx.value_and_grad(objective)(parameters)
    # Native torch.nn.Embedding(padding_idx=0) never trains padding row.
    pad_mask = mx.arange(parameters["embedding.weight"].shape[0])[:, None] != 0
    gradients["embedding.weight"] = mx.where(
        pad_mask, gradients["embedding.weight"],
        mx.zeros_like(gradients["embedding.weight"]))
    clipped, norm = clip_gradients(mx, gradients, max_norm=1.0)
    optimizer.update(parameters, clipped)
    mx.eval(parameters, optimizer.state, loss, norm)
    return float(loss.item()), float(norm.item())


def _persist(run_dir: Path, receipt: dict):
    """One linearizable state pointer; immutable sequence copies remain."""
    receipt = json.loads(_canonical(receipt))
    generation = receipt["generation"]
    path = run_dir / "states" / f"{generation:07d}.json"
    if path.exists():
        if path.is_symlink() or json.loads(path.read_text(encoding="utf-8")) != receipt:
            raise ValueError("HUMAN_TRAINER_IMMUTABLE_GENERATION_COLLISION")
    else:
        _durable_json(path, receipt)
    if json.loads(path.read_text(encoding="utf-8")) != receipt:
        raise ValueError("HUMAN_TRAINER_SNAPSHOT_POSTWRITE_MISMATCH")
    _durable_json(run_dir / "state.json", receipt, replace_existing=True)
    if json.loads((run_dir / "state.json").read_text(encoding="utf-8")) != receipt:
        raise ValueError("HUMAN_TRAINER_LATEST_POINTER_NOT_DURABLE")
    return receipt


def _recover_orphaned_commit(run_dir: Path, latest: dict) -> dict:
    """Complete a fully written generation whose state.json pointer lost a race to a crash.

    Call only under the exclusive operator lock and only with an already checked
    live source manifest; no model or optimizer is mutated here.
    """
    target = run_dir / "states" / f"{latest['generation']+1:07d}.json"
    if not target.exists():
        return latest
    if target.is_symlink() or not target.is_file():
        raise ValueError("HUMAN_TRAINER_RECOVERY_UNSAFE_GENERATION")
    proposed = json.loads(target.read_text(encoding="utf-8"))
    if (proposed.get("generation") != latest["generation"] + 1 or
            proposed.get("run_id") != latest.get("run_id") or
            proposed.get("schema") != latest.get("schema") or
            proposed.get("source_manifest_sha256") != latest.get("source_manifest_sha256") or
            proposed.get("teacher_source_sha256") != latest.get("teacher_source_sha256") or
            proposed.get("accepted_authority") != latest.get("accepted_authority")):
        raise ValueError("HUMAN_TRAINER_RECOVERY_INCONSISTENT_LINEAGE")
    # Verify every retained old/new whole-student pointer before publication.
    _verify_best_custody(run_dir, proposed)
    _durable_json(run_dir / "state.json", proposed, replace_existing=True)
    if json.loads((run_dir / "state.json").read_text()) != proposed:
        raise ValueError("HUMAN_TRAINER_RECOVERY_POINTER_NOT_DURABLE")
    # Publish the recovered generation's original causal events before its
    # recovery annotation, retaining a legible ordered School50 history.
    _reconcile_delivery_outbox(run_dir, proposed)
    _record(run_dir, {"event": "SCHOOL_INTERRUPT_POINTER_RECOVERED", "grade": "A",
                      "generation": proposed["generation"],
                      "student_sha256": proposed["school"]["current_student"]["sha256"],
                      "optimizer_step": proposed["school"]["current_student"]["optimizer_step"]})
    return proposed


def _record(run_dir: Path, event: dict):
    path = run_dir / "events.jsonl"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(_canonical(event) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    if _event_view.get() is None:
        print(json.dumps(event, sort_keys=True), flush=True)
    else:
        _notify_viewer(event)


def _notify_viewer(event: dict):
    """Send ephemeral operator telemetry without making it training evidence."""
    viewer = _event_view.get()
    if viewer is None:
        return
    try:
        viewer(event)
    except Exception as exc:
        print("DASHBOARD UNAVAILABLE: " + str(exc), file=sys.stderr, flush=True)


def _bundle_pointer(run_dir: Path, name: str, parameters, optimizer, graph,
                    *, reserve_gib: float):
    stage_root = run_dir / ".bundle-staging"
    if stage_root.is_symlink() or (stage_root.exists() and not stage_root.is_dir()):
        raise ValueError("HUMAN_TRAINER_UNSAFE_STAGING_ROOT")
    stage_root.mkdir(exist_ok=True)
    stage_directory = stage_root / name
    directory = run_dir / "bundles" / name
    if directory.exists() or directory.is_symlink():
        raise ValueError("HUMAN_TRAINER_BUNDLE_ALREADY_PUBLISHED")
    metadata = save_new_bundle(
        stage_directory, parameters, optimizer, source_digest=AUDITED_PARENT.sha256,
        semantic_catalog=graph, reserve_gib=reserve_gib)
    restored, restored_optimizer, manifest, restored_graph = (
        load_semantically_bound_bundle(stage_directory))
    if (metadata != manifest or restored_graph != graph or
            list(restored) != list(parameters) or
            int(restored_optimizer.state["step"].item()) != int(optimizer.state["step"].item())):
        raise ValueError("HUMAN_TRAINER_COMPLETE_CHECKPOINT_READBACK_DRIFT")
    for filename in ("model-and-own-adamw.safetensors",
                     "semantic-catalog.json", "manifest.json"):
        fd = os.open(stage_directory / filename, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    dir_fd = os.open(stage_directory, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    directory.parent.mkdir(exist_ok=True)
    # The published bundles namespace must contain ONLY complete, read-back
    # verified three-file bundles. Failed writes remain in isolated staging.
    stage_directory.rename(directory)
    fd = os.open(directory.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    stage_root.rmdir()
    return Checkpoint(metadata["safetensors_sha256"],
                      str(directory.relative_to(run_dir)),
                      metadata["optimizer_step"], True)


def _clean_staged_bundles(run_dir: Path) -> dict[str, tuple[str, ...]]:
    """Reconcile unpublished bundles without losing a possibly valid student."""
    stage = run_dir / ".bundle-staging"
    if not stage.exists() and not stage.is_symlink():
        return {"discarded": (), "quarantined": ()}
    if stage.is_symlink() or not stage.is_dir():
        raise ValueError("HUMAN_TRAINER_UNSAFE_STAGING_ROOT")
    expected = {"model-and-own-adamw.safetensors", "semantic-catalog.json",
                "manifest.json"}
    discarded, quarantined = [], []
    for folder in stage.iterdir():
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("HUMAN_TRAINER_UNKNOWN_STAGED_BUNDLE")
        files = list(folder.iterdir())
        if any(file.is_symlink() or not file.is_file() or file.name not in expected
               for file in files):
            raise ValueError("HUMAN_TRAINER_UNKNOWN_STAGED_BUNDLE_CONTENT")
        if (folder / "model-and-own-adamw.safetensors").exists():
            # Even if its manifest is incomplete, this is the only surviving
            # binary for updates possibly completed just before a crash. Keep
            # it outside active bundles for human custody recovery.
            custody = run_dir / ".bundle-quarantine"
            if custody.is_symlink() or (custody.exists() and not custody.is_dir()):
                raise ValueError("HUMAN_TRAINER_UNSAFE_BUNDLE_QUARANTINE")
            custody.mkdir(exist_ok=True)
            target = custody / folder.name
            if target.exists() or target.is_symlink():
                raise ValueError("HUMAN_TRAINER_QUARANTINE_IDENTITY_COLLISION")
            folder.rename(target)
            quarantined.append(folder.name)
        else:
            for file in files:
                file.unlink()
            folder.rmdir()
            discarded.append(folder.name)
    stage.rmdir()
    return {"discarded": tuple(discarded), "quarantined": tuple(quarantined)}


def _init(run_dir, manifest, course, policy_sha, historical_teacher,
          teacher_provenance, checkpoint,
          *, source_root, reserve_gib, permitted_preexisting=()):
    import mlx.core as mx
    _clean_staged_bundles(run_dir)
    permitted = {LOCKFILE, *permitted_preexisting}
    if (run_dir / "state.json").exists() or any(
            p.name not in permitted for p in run_dir.iterdir()):
        raise ValueError("HUMAN_TRAINER_NEW_RUN_HAS_EXISTING_CONTENT")
    assert_headroom(run_dir, required_bytes=600_000_000, reserve_gib=reserve_gib)
    parameters, optimizer, config, graph, answer_ids = _initial_model(checkpoint)
    initial_pointer = _bundle_pointer(
        run_dir, "initial-"+uuid.uuid4().hex[:12], parameters, optimizer, graph,
        reserve_gib=reserve_gib)
    release, program, _ = compile_projected_executable_release(
        course, course, source_root, graph)
    state = start_new(program, initial_pointer)
    release, release_file, admission = _executable_factory_admission(
        run_dir, release, initial_pointer, _fingerprint(graph), graph)
    parameter_shapes = {name: list(param.shape) for name, param in parameters.items()}
    championship_identity = build_school_identity(
        course_sha256=release.execution_plan.curriculum_sha256,
        semantic_graph_sha256=_fingerprint(graph),
        parameter_shapes=parameter_shapes,
        factory_release_sha256=release.release_sha256)
    receipt = {
        "schema": VERSION,
        "generation": 1,
        "run_id": uuid.uuid4().hex,
        "accepted_authority": AUTHORITY,
        "curriculum_mode": course.version,
        "source_manifest_sha256": manifest["manifest_sha256"],
        "teacher_source_sha256": policy_sha,
        "school": asdict(state),
        "model_bundle": initial_pointer.filename,
        "capability_best": {},
        "teacher": json.loads(_canonical(historical_teacher)),
        "teacher_provenance": teacher_provenance,
        "config": config,
        "parameter_shapes": parameter_shapes,
        "semantic_graph_sha256": _fingerprint(graph),
        "factory_release_sha256": release.release_sha256,
        "factory_release_file": release_file,
        "factory_release_schema": release.schema,
        "factory_admission_v2": asdict(admission),
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
    receipt = _persist(run_dir, _with_delivery_outbox(receipt, (init_event,)))
    _reconcile_delivery_outbox(run_dir, receipt)
    return parameters, optimizer, graph, receipt


def _resume(run_dir, manifest, course, policy_sha, *, grade_a_course,
            source_root, successor_course=None, admitted_courses=None):
    import mlx.core as mx
    path = run_dir / "state.json"
    if not path.is_file():
        raise ValueError("HUMAN_TRAINER_RESUME_REQUIRES_PRIOR_RUN")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if (receipt.get("schema") != VERSION or receipt.get("accepted_authority") != AUTHORITY
            or receipt.get("source_manifest_sha256") != manifest["manifest_sha256"]
            or receipt.get("teacher_source_sha256") != policy_sha):
        raise ValueError("HUMAN_TRAINER_RESUME_SOURCE_OR_POLICY_DRIFT")
    reconciled = _clean_staged_bundles(run_dir)
    if any(reconciled.values()):
        _record(run_dir, {"event": "SCHOOL_UNPUBLISHED_STAGING_RECONCILED",
                          "grade": "A", "generation": receipt["generation"],
                          **reconciled})
    receipt = _recover_orphaned_commit(run_dir, receipt)
    saved_mode = receipt.get("curriculum_mode")
    executable = (
        _read_executable_factory_release_artifact(run_dir, receipt)
        if receipt.get("factory_admission_v2") is not None else None)
    old_mode = executable is None and saved_mode is None
    old_course = (
        accepted_grade_a(manifest) if old_mode else course)
    school_program = (
        schedule_program_from_executable_release(executable)
        if executable is not None else
        _schedule_for_receipt(run_dir, receipt, old_course))
    school = _state_from_json(receipt["school"], school_program)
    directory = (run_dir / receipt["model_bundle"]).resolve(strict=True)
    if directory.parent != (run_dir / "bundles").resolve(strict=True):
        raise ValueError("HUMAN_TRAINER_BUNDLE_PATH_ESCAPES_RUN")
    parameters, optimizer, bundle, graph = load_semantically_bound_bundle(directory)
    if executable is not None:
        executable.verify_semantic_catalog(graph)
    else:
        verify_legacy_resume_binding(
            receipt, old_course, graph, manifest, _fingerprint)
    if (bundle["source_digest"] != AUDITED_PARENT.sha256 or
            bundle["safetensors_sha256"] != school.current_student.sha256 or
            bundle["optimizer_step"] != school.current_student.optimizer_step or
            school.current_student.filename != receipt["model_bundle"] or
            _fingerprint(graph) != receipt["semantic_graph_sha256"] or
            {name:list(value.shape) for name,value in parameters.items()} !=
            receipt["parameter_shapes"] or
            len(parameters) != 39):
        raise ValueError("HUMAN_TRAINER_RESUME_MODEL_ADAMW_OR_SEMANTIC_DRIFT")
    if json.loads((run_dir / "states" /
                   f"{receipt['generation']:07d}.json").read_text()) != receipt:
        raise ValueError("HUMAN_TRAINER_RESUME_IMMUTABLE_STATE_DIVERGED")
    if not old_mode:
        _verify_saved_cohort(run_dir, receipt, old_course)
    mx.eval(parameters, optimizer.state)
    from .compatibility.frontier_recovery import recover_legacy_frontier
    receipt = recover_legacy_frontier(mx, run_dir, receipt, old_course, parameters)
    school = _state_from_json(receipt["school"], school_program)
    if "capability_best" not in receipt:
        # Existing full-history run: reconstruct bests from actual sealed
        # checkpoint receipts before permitting reference-aware retirement.
        first_grade = school_program.grades[0]
        counts = {
            capability.id: capability.exam_item_count
            for capability in first_grade.capabilities}
        frontier = historical_frontier(
            run_dir, expected_rubric=manifest["exam_rubric_sha256"],
            expected_capabilities=counts)
        _verify_best_custody(run_dir, {**receipt, "capability_best": frontier})
        receipt = _advance(run_dir, receipt, school, frontier=frontier)
        _record(run_dir, {"event": "SCHOOL_CAPABILITY_FRONTIER_MIGRATED",
                          "grade": "A", "generation": receipt["generation"],
                          "champion_roles": len(frontier),
                          "whole_student_unchanged": True})
    if old_mode:
        from .compatibility.resume_migration import (
            migrate_historical_grade_a,
        )
        receipt, school = migrate_historical_grade_a(
            run_dir, receipt, school, course, old_course, manifest)
    active_course = course if old_mode else old_course
    receipt, _, _ = _ensure_executable_release(
        run_dir, receipt, active_course, grade_a_course, source_root, graph)
    _verify_best_custody(run_dir, receipt)
    # Also finishes a retirement interrupted after the prior state commit.
    _publish_boundary(run_dir, receipt, (), ())
    if any("breadth" not in entry for entry in
           receipt.get("graduation_perfect", {}).values()):
        with (run_dir / "events.jsonl").open(encoding="utf-8") as history:
            ranked = recover_graduation_breadth(
                receipt["graduation_perfect"],
                (json.loads(line) for line in history if line.strip()))
        # Original immutable generations stay untouched until a new boundary.
        receipt = {**receipt, "graduation_perfect": ranked}
    receipt = _migrate_championship_governance(run_dir, receipt, active_course)
    # Governance migration can archive formerly active champion references.
    # Re-run custody verification against that enlarged immutable reference set
    # before this resumed state is allowed to proceed to any lesson or exam.
    _verify_best_custody(run_dir, receipt)
    return parameters, optimizer, graph, receipt


def _activate_next_admitted_grade(run_dir, receipt, previous_course, successor,
                                  graph=None):
    """Compatibility shim for historical Course transition tests."""
    from .compatibility.trainer_transitions import activate_next_admitted_grade
    return activate_next_admitted_grade(
        run_dir, receipt, previous_course, successor, graph)


def _adopt_executable_profile(
        run_dir, receipt, grade_a_course, source_root, graph, profile, *,
        compiled_successor=None):
    """Adopt one same-ABI v2 profile change without release-name dispatch."""
    predecessor = _require_executable_factory_admission(run_dir, receipt, graph)
    previous_program = schedule_program_from_executable_release(predecessor)
    school = _state_from_json(receipt["school"], previous_program)
    compatibility_course = legacy_course_for_profile(
        grade_a_course, source_root, profile)
    successor = compiled_successor or compile_successor_profile_release(
        predecessor,
        profile,
        live_source_registry(),
        live_answer_registry(),
        source_root=source_root,
        graph=graph,
        verification_seed=2026101906,
        legacy_course=compatibility_course)
    successor.verify_successor_of(predecessor)
    successor.verify_semantic_catalog(graph)
    if successor.profile != profile:
        raise ValueError("FACTORY_EXECUTABLE_PROFILE_TRANSITION_MISMATCH")
    successor_program = schedule_program_from_executable_release(successor)
    appended = len(successor_program.grades) == len(previous_program.grades) + 1
    revised = (
        len(successor_program.grades) == len(previous_program.grades) and
        tuple(grade.id for grade in successor_program.grades) ==
        tuple(grade.id for grade in previous_program.grades))
    if appended:
        next_state = adopt_appended_program(
            previous_program, successor_program, school)
        revised_grade = None
    elif revised:
        next_state, revised_grade = adopt_revised_program(
            previous_program, successor_program, school)
    else:
        raise ValueError("FACTORY_EXECUTABLE_PROFILE_TRANSITION_UNSUPPORTED")
    successor, release_file, admission = _executable_factory_admission(
        run_dir, successor, next_state.current_student,
        receipt["semantic_graph_sha256"], graph)

    exam = receipt.get("last_exam") or {}
    history = list(receipt.get("championship_epoch_history", ()))
    identity = build_school_identity(
        course_sha256=successor.execution_plan.curriculum_sha256,
        semantic_graph_sha256=receipt["semantic_graph_sha256"],
        parameter_shapes=receipt["parameter_shapes"],
        factory_release_sha256=successor.release_sha256)
    if appended:
        from bilqis_mlx.learning.mentor_epoch import begin_epoch
        epoch = begin_epoch(
            previous_graduate=asdict(school.current_student),
            admitted_baseline=asdict(next_state.current_student),
            introduced_grade=next_state.grade,
            source_graph_sha256=receipt["semantic_graph_sha256"],
            previous_capabilities=tuple(
                item.capability_id
                for item in predecessor.execution_plan.capabilities),
            previous_graduation_exam={
                "checkpoint_sha256": exam.get("student_sha256"),
                "rubric_sha256": exam.get("exam_rubric_sha256"),
                "cohort_sha256": exam.get("cohort_sha256"),
                "scores": exam.get("scores"),
            })
        if receipt.get("mentor_epoch") is not None:
            history.append(receipt["mentor_epoch"])
        epoch["settled_matchups"] = deepcopy(
            (receipt.get("mentor_epoch") or {}).get("settled_matchups", {}))
        epoch["championship_school_identity"] = identity
    else:
        epoch = receipt.get("mentor_epoch")
        if epoch is not None:
            epoch, identity_event = enforce_school_identity(
                epoch, identity,
                generation=receipt["generation"] + 1,
                student=asdict(school.current_student))
            if identity_event is not None:
                history.append({
                    "kind": "profile-revision-school-identity-reset",
                    "event": identity_event,
                })
    heads = answer_heads_from_executable_release(successor, graph)
    numeric_values = heads.get("numeric_active", {}).get("values")
    config = {**receipt["config"], "answer_heads": heads}
    candidate = {
        **receipt,
        "curriculum_mode": compatibility_course.version,
        "config": config,
        "live_rubric_sha256":
            successor_program.grades[-1].assessment_sha256,
        "factory_release_sha256": successor.release_sha256,
        "factory_release_file": release_file,
        "factory_release_schema": successor.schema,
        "factory_admission_v2": asdict(admission),
        "championship_school_identity": identity,
        "mentor_epoch": epoch,
        "championship_epoch_history": history,
        "last_exam": None if revised_grade is not None else receipt.get("last_exam"),
    }
    if numeric_values is not None:
        candidate["numeric_maximum"] = len(numeric_values) - 1
    candidate.pop("qualification_cohort_v2", None)
    record = _advance(
        run_dir, candidate, next_state,
        result="ACTIVE_GRADE_" + next_state.grade, persist=False)
    event = {
        "event": "SCHOOL_EXECUTION_PROFILE_ADOPTED",
        "generation": record["generation"],
        "grade": next_state.grade,
        "profile_id": successor.profile.profile_id,
        "transition_kind": "APPEND_GRADE" if appended else "REVISE_PROFILE",
        "revised_grade": revised_grade,
        "previous_factory_release_sha256": predecessor.release_sha256,
        "factory_release_sha256": successor.release_sha256,
        "student_sha256": school.current_student.sha256,
        "optimizer_step": school.current_student.optimizer_step,
        "actual_neural_updates": 0,
    }
    record = _persist(
        run_dir, _with_delivery_outbox(record, (event,)))
    _reconcile_delivery_outbox(run_dir, record)
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


def _adopt_catalog_profile(
        mx, run_dir, receipt, grade_a_course, source_root, graph,
        parameters, optimizer, transition, *, reserve_gib, allow_mastery_debt=False,
        compiled_successor=None):
    """Adopt one append-only semantic ABI/profile expansion with zero updates."""
    predecessor = _require_executable_factory_admission(run_dir, receipt, graph)
    previous_program = schedule_program_from_executable_release(predecessor)
    school = _state_from_json(receipt["school"], previous_program)
    if allow_mastery_debt:
        exam = receipt.get("debt_admission_boundary_exam") or {}
        expected = {cap.id: cap.exam_item_count
                    for grade in previous_program.grades for cap in grade.capabilities}
        from .factory.assessment import assessment_scope_contract
        contract = assessment_scope_contract(predecessor, tuple(expected))
        if (exam.get("student_sha256") != school.current_student.sha256 or
                exam.get("optimizer_step") != school.current_student.optimizer_step or
                exam.get("factory_release_sha256") != predecessor.release_sha256 or
                exam.get("exam_rubric_sha256") != contract.rubric_sha256 or
                set(exam.get("scores", {})) != set(expected) or
                any(score.get("total") != expected[cap]
                    for cap, score in exam.get("scores", {}).items())):
            raise ValueError("DEBT_ADMISSION_REQUIRES_EXACT_COMPLETE_BOUNDARY")
        mastery_debt = tuple(cap for cap in expected
                             if exam["scores"][cap]["correct"] != expected[cap])
    else:
        _require_complete_profile_boundary(previous_program, school, receipt)
        exam = receipt.get("last_exam") or {}
        mastery_debt = ()
    compatibility_course = legacy_course_for_profile(
        grade_a_course, source_root, transition.profile)
    successor = compiled_successor or compile_successor_profile_release(
        predecessor,
        transition.profile,
        live_source_registry(),
        live_answer_registry(),
        source_root=source_root,
        graph=transition.graph,
        verification_seed=2026101907,
        legacy_course=compatibility_course)
    successor.verify_successor_of(predecessor)
    successor.verify_semantic_catalog(transition.graph)
    if successor.profile != transition.profile:
        raise ValueError("FACTORY_EXECUTABLE_PROFILE_TRANSITION_MISMATCH")
    if (successor.transition is None or
            successor.transition.semantic_geometry != "APPEND_ONLY_EXPANSION"):
        raise ValueError("FACTORY_CATALOG_TRANSITION_NOT_APPEND_ONLY")
    successor_program = schedule_program_from_executable_release(successor)
    next_state = (
        append_next_grade_with_debt(
            previous_program, successor_program, school, mastery_debt)
        if allow_mastery_debt else
        adopt_appended_program(previous_program, successor_program, school))

    grown, own_optimizer, growth = extend_mlx_student(
        parameters, optimizer, graph, transition.graph)
    pointer = _bundle_pointer(
        run_dir, "catalog-admission-" + uuid.uuid4().hex[:12],
        grown, own_optimizer, transition.graph, reserve_gib=reserve_gib)
    next_state = replace(next_state, current_student=pointer)
    successor, release_file, admission = _executable_factory_admission(
        run_dir, successor, pointer, _fingerprint(transition.graph),
        transition.graph)

    from bilqis_mlx.learning.mentor_epoch import begin_debt_epoch, begin_epoch
    boundary_exam = {
        "checkpoint_sha256": exam.get("student_sha256"),
        "rubric_sha256": exam.get("exam_rubric_sha256"),
        "cohort_sha256": exam.get("cohort_sha256"),
        "scores": exam.get("scores"),
    }
    epoch_args = dict(
        admitted_baseline=asdict(pointer),
        introduced_grade=next_state.grade,
        source_graph_sha256=_fingerprint(transition.graph),
        previous_capabilities=tuple(
            item.capability_id for item in predecessor.execution_plan.capabilities))
    epoch = (
        begin_debt_epoch(**epoch_args,
                         previous_checkpoint=asdict(school.current_student),
                         previous_boundary_exam=boundary_exam,
                         previous_mastery_debt=mastery_debt)
        if allow_mastery_debt else
        begin_epoch(**epoch_args,
                    previous_graduate=asdict(school.current_student),
                    previous_graduation_exam=boundary_exam))
    history = list(receipt.get("championship_epoch_history", ()))
    if receipt.get("mentor_epoch") is not None:
        history.append(receipt["mentor_epoch"])
    identity = build_school_identity(
        course_sha256=successor.execution_plan.curriculum_sha256,
        semantic_graph_sha256=_fingerprint(transition.graph),
        parameter_shapes={name: list(value.shape) for name, value in grown.items()},
        factory_release_sha256=successor.release_sha256)
    epoch["settled_matchups"] = deepcopy(
        (receipt.get("mentor_epoch") or {}).get("settled_matchups", {}))
    epoch["championship_school_identity"] = identity
    heads = answer_heads_from_executable_release(successor, transition.graph)
    numeric_values = heads.get("numeric_active", {}).get("values")
    updated = {
        **receipt,
        "curriculum_mode": compatibility_course.version,
        "semantic_graph_sha256": _fingerprint(transition.graph),
        "factory_release_sha256": successor.release_sha256,
        "factory_release_file": release_file,
        "factory_release_schema": successor.schema,
        "factory_admission_v2": asdict(admission),
        "parameter_shapes": {
            name: list(value.shape) for name, value in grown.items()},
        "championship_school_identity": identity,
        "config": {
            **receipt["config"],
            "vocab_size": len(transition.graph["tokens"]),
            "answer_heads": heads,
        },
        "live_rubric_sha256":
            successor_program.grades[-1].assessment_sha256,
        "numeric_maximum": (
            len(numeric_values) - 1 if numeric_values is not None else
            receipt.get("numeric_maximum")),
        "numeric_scope_final_maximum":
            transition.numeric_scope_final_maximum,
        "mentor_epoch": epoch,
        "championship_epoch_history": history,
        "last_exam": None,
    }
    from .fixed_frontier import load_frontier_cohort, rebaseline_frontier_exam
    preserved = load_frontier_cohort(run_dir, exam)
    if preserved is None:
        raise ValueError("FACTORY_CATALOG_BOUNDARY_COHORT_REQUIRED")
    updated["last_exam"] = rebaseline_frontier_exam(
        run_dir, exam, checkpoint=asdict(pointer), predictions=_predictions(
            mx, grown, list(preserved.rows), updated["config"], updated["answer_ids"]))
    updated.pop("qualification_cohort_v2", None)
    record = _advance(
        run_dir, updated, next_state, model_bundle=pointer.filename,
        result="ACTIVE_GRADE_" + next_state.grade, persist=False)
    event = {
        "event": "SCHOOL_SEMANTIC_CATALOG_PROFILE_ADOPTED",
        "generation": record["generation"],
        "grade": next_state.grade,
        "profile_id": successor.profile.profile_id,
        "semantic_geometry": successor.transition.semantic_geometry,
        "growth": growth,
        "previous_student_sha256": school.current_student.sha256,
        "student_sha256": pointer.sha256,
        "optimizer_step": pointer.optimizer_step,
        "factory_release_sha256": successor.release_sha256,
        "actual_neural_updates": 0,
    }
    record = _persist(
        run_dir, _with_delivery_outbox(record, (event,)))
    _reconcile_delivery_outbox(run_dir, record)
    return grown, own_optimizer, transition.graph, record, compatibility_course


def _adopt_jit_proposal(mx, run_dir, receipt, grade_a_course, source_root, graph,
                       parameters, optimizer, session, proposal, *, reserve_gib):
    """Use the existing student/own-AdamW admission transaction for a fresh JIT choice."""
    from .factory.candidate_realizations import admitted_candidate_graph
    from .runtime.jit_adoption import verify_current_implementations
    predecessor = _require_executable_factory_admission(run_dir, receipt, graph)
    program = schedule_program_from_executable_release(predecessor)
    school = _state_from_json(receipt["school"], program)
    staged = session.resolve_ready_proposal(school.current_student, proposal)
    successor = staged.successor
    verify_current_implementations(successor, live_source_registry(), live_answer_registry())
    appended = len(successor.execution_plan.grades) > len(predecessor.execution_plan.grades)
    if appended:
        _require_complete_profile_boundary(program, school, receipt)
    if successor.transition.semantic_geometry == "APPEND_ONLY_EXPANSION":
        from .profiles.catalog import CatalogProfileTransition
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
    """Compatibility shim for historical same-grade migration tests."""
    from .compatibility.trainer_transitions import activate_revised_admitted_grade
    return activate_revised_admitted_grade(
        run_dir, receipt, previous_course, successor, graph)


def _activate_replaced_admitted_grade(run_dir, receipt, previous_course, successor,
                                      graph=None):
    """Compatibility shim for historical grade-winnowing tests."""
    from .compatibility.trainer_transitions import activate_replaced_admitted_grade
    return activate_replaced_admitted_grade(
        run_dir, receipt, previous_course, successor, graph)


def _mentor_epoch_references(receipt):
    if receipt.get("mentor_epoch") is None:
        return ()
    from bilqis_mlx.learning.mentor_epoch import reference_checkpoints
    epochs = (*receipt.get("championship_epoch_history", ()), receipt["mentor_epoch"])
    return tuple(pointer for epoch in epochs
                 for pointer in (
                     *reference_checkpoints(epoch),
                     *(item["checkpoint"] for item in epoch_active_frontier(epoch).values())))


def _verify_frozen_soup_custody(run_dir, receipt):
    """Verify both archived and earned soups without blending their rosters."""
    epoch_soups = (entry.get("active_grade_soups", {})
                   for entry in (*receipt.get("championship_epoch_history", ()),
                                 receipt["mentor_epoch"])
                   ) if receipt.get("mentor_epoch") is not None else ()
    for grade, soup in (*receipt.get("grade_soups", {}).items(),
                        *(pair for soups in epoch_soups for pair in soups.items())):
        if grade != soup.get("grade"):
            raise ValueError("GRADE_SOUP_CUSTODY_GRADE_DRIFT")
        verify_frozen_soup(run_dir, soup)
        if soup.get("previous"):
            older = soup["previous"] if isinstance(soup["previous"], list) else [soup["previous"]]
            for old in older:
                previous = run_dir / old["filename"]
                if (previous.parent != run_dir / "soups" or previous.is_symlink() or
                        not previous.is_file() or digest_file(previous) != old["sha256"]):
                    raise ValueError("GRADE_SOUP_PREVIOUS_BACKUP_DRIFT")


def _verify_best_custody(run_dir, receipt):
    school = receipt["school"]
    historical_pending = (receipt.get("historical_capability_best", {})
                          if receipt.get("legacy_frontier_pending_replay") else {})
    sources = [school["current_student"], *school["champions"].values(),
               *receipt.get("historical_grade_champions", {}).values(),
               *(cap["checkpoint"] for cap in receipt.get("capability_best", {}).values()),
               *(cap["checkpoint"] for cap in receipt.get("graduation_perfect", {}).values()),
               *(cap["checkpoint"] for cap in historical_pending.values())]
    protected = pinned(receipt.get("capability_best", {}),
                       school["current_student"], school["champions"])
    protected |= pinned(receipt.get("graduation_perfect", {}),
                        school["current_student"], school["champions"])
    if historical_pending:
        protected |= pinned(historical_pending,
                            school["current_student"], school["champions"])
    for item in receipt.get("historical_grade_champions", {}).values():
        protected |= pinned({}, item, {})
    if receipt.get('curriculum_parent'):
        sources.append(receipt['curriculum_parent'])
        protected |= pinned({}, receipt['curriculum_parent'], {})
    for peak in receipt.get("whole_student_peaks", ()):
        if peak.get("schema") != "bilqis.mlx.whole-student-retention/v1":
            raise ValueError("WHOLE_STUDENT_PEAK_SCHEMA_DRIFT")
        source = peak["checkpoint"]
        sources.append(source)
        protected |= pinned({}, source, {})
    for source in _mentor_epoch_references(receipt):
        sources.append(source)
        protected |= pinned({}, source, {})
    for name in sorted(protected):
        root = run_dir / name
        if root.is_symlink() or root.parent != run_dir / "bundles":
            raise ValueError("HUMAN_TRAINER_CAPABILITY_CUSTODY_PATH_DRIFT")
        manifest = json.loads((root / "manifest.json").read_text())
        if digest_file(root / "model-and-own-adamw.safetensors") != manifest["safetensors_sha256"]:
            raise ValueError("HUMAN_TRAINER_CAPABILITY_CUSTODY_SHA_DRIFT")
        for ref in sources:
            if (ref["filename"] == name and
                    (manifest["safetensors_sha256"] != ref["sha256"] or
                     manifest["optimizer_step"] != ref["optimizer_step"])):
                raise ValueError("HUMAN_TRAINER_CAPABILITY_CUSTODY_REFERENCE_DRIFT")
    _verify_frozen_soup_custody(run_dir, receipt)


def _advance(run_dir, old: dict, school: SchoolState, *,
             teacher=None, model_bundle=None, last_exam=None, result=None,
             frontier=None, persist=True):
    # One snapshot captures teacher learning, school progress and model pointer.
    record = dict(old)
    record["generation"] = old["generation"] + 1
    record["school"] = asdict(school)
    if teacher is not None:
        record["teacher"] = teacher
    if model_bundle is not None:
        record["model_bundle"] = model_bundle
    if last_exam is not None:
        record["last_exam"] = last_exam
    if result is not None:
        record["result"] = result
    if frontier is not None:
        record["capability_best"] = frontier
    if persist:
        record.pop("_pending_visit_events", None)
        return _persist(run_dir, record)
    return json.loads(_canonical(record))


def _repair_scope_rubric_evidence(run_dir, receipt, course):
    """Repair evidence minted by the historical course-rubric/scope-rubric conflation."""
    exam = receipt.get("last_exam") or {}
    exam_rubric = exam.get("exam_rubric_sha256")
    scores = exam.get("scores") or {}
    epoch = receipt.get("mentor_epoch")
    frontier = receipt.get("capability_best") or {}
    if (not isinstance(exam_rubric, str) or len(exam_rubric) != 64 or
            not scores or not isinstance(epoch, dict) or not frontier):
        return receipt
    scored = set(scores)
    wrong_frontier = {
        key: item for key, item in frontier.items()
        if item.get("capability") in scored and item.get("rubric") != exam_rubric
    }
    wrong_roles = {
        cap: item for cap, item in epoch.get("active_roles", {}).items()
        if cap in scored and item.get("rubric") != exam_rubric
    }
    if not wrong_frontier and not wrong_roles:
        return receipt
    school = _state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
    history = [*receipt.get("championship_epoch_history", ()), deepcopy(epoch)]
    reset = begin_initial_epoch(
        student=asdict(school.current_student),
        introduced_grade=school.grade,
        source_graph_sha256=receipt["semantic_graph_sha256"],
        frontier={}, soups={})
    reset["settled_matchups"] = {}
    reset["championship_school_identity"] = receipt["championship_school_identity"]
    kept = {key: item for key, item in frontier.items() if key not in wrong_frontier}
    repaired = {
        **receipt,
        "capability_best": kept,
        "mentor_epoch": reset,
        "championship_epoch_history": history,
        "live_rubric_sha256": exam_rubric,
    }
    record = _advance(
        run_dir, repaired, school, frontier=kept,
        result=receipt.get("result"), persist=False)
    event = {
        "event": "SCHOOL_SCOPE_RUBRIC_EVIDENCE_REPAIRED",
        "generation": record["generation"],
        "source_generation": receipt["generation"],
        "student_sha256": school.current_student.sha256,
        "optimizer_step": school.current_student.optimizer_step,
        "assessment_rubric_sha256": exam_rubric,
        "invalidated_frontier_capabilities":
            sorted(item["capability"] for item in wrong_frontier.values()),
        "invalidated_championship_roles": sorted(wrong_roles),
        "archived_bad_epoch": True,
        "actual_neural_updates": 0,
        "model_and_own_adamw_unchanged": True,
    }
    record = _persist(run_dir, _with_delivery_outbox(record, (event,)))
    _reconcile_delivery_outbox(run_dir, record)
    return record


def _repair_championship_source_context(run_dir, receipt, course):
    """Archive titles minted while cohort-source and assessment rubrics were conflated."""
    epoch = receipt.get("mentor_epoch")
    if not isinstance(epoch, dict) or not epoch.get("active_roles"):
        return receipt

    affected = set()
    for capability, role in epoch["active_roles"].items():
        evidence = (
            *role.get("qualification_witnesses", ()),
            *role.get("surviving_battery", ()),
        )
        for item in evidence:
            if item.get("cohort_rubric_sha256") is not None:
                continue
            sha = item.get("cohort_sha256")
            assessment_rubric = item.get("rubric_sha256")
            source_oracle = item.get("source_oracle_sha256")
            if not all(isinstance(value, str) and len(value) == 64
                       for value in (sha, assessment_rubric, source_oracle)):
                raise ValueError("CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_IDENTITY_DRIFT")
            path = run_dir / "cohorts" / (sha + ".json")
            if path.is_symlink() or not path.is_file():
                raise ValueError("CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_COHORT_MISSING")
            stored = json.loads(path.read_text())
            if (stored.get("cohort_sha256") != sha or
                    stored.get("source_manifest_sha256") != source_oracle):
                raise ValueError("CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_CUSTODY_DRIFT")
            cohort = make_cohort(
                stored["rows"], generator_version=stored["generator_version"],
                seed=stored["seed"], rubric_version=stored["schema"])
            if cohort.digest != sha:
                raise ValueError("CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_CONTENT_DRIFT")
            if stored.get("rubric_sha256") != assessment_rubric:
                affected.add(capability)
                break

    if not affected:
        return receipt

    school = _state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
    history = [*receipt.get("championship_epoch_history", ()), deepcopy(epoch)]
    reset = begin_initial_epoch(
        student=asdict(school.current_student),
        introduced_grade=school.grade,
        source_graph_sha256=receipt["semantic_graph_sha256"],
        frontier={}, soups={})
    reset["settled_matchups"] = {}
    reset["championship_school_identity"] = receipt["championship_school_identity"]
    repaired = {
        **receipt,
        "mentor_epoch": reset,
        "championship_epoch_history": history,
    }
    record = _advance(
        run_dir, repaired, school,
        result=receipt.get("result"), persist=False)
    event = {
        "event": "SCHOOL_CHAMPIONSHIP_SOURCE_CONTEXT_REPAIRED",
        "generation": record["generation"],
        "source_generation": receipt["generation"],
        "student_sha256": school.current_student.sha256,
        "optimizer_step": school.current_student.optimizer_step,
        "invalidated_championship_roles": sorted(affected),
        "archived_bad_epoch": True,
        "actual_neural_updates": 0,
        "model_and_own_adamw_unchanged": True,
    }
    record = _persist(run_dir, _with_delivery_outbox(record, (event,)))
    _reconcile_delivery_outbox(run_dir, record)
    return record


def _reconcile_vocabulary_metadata(run_dir, receipt, course, parameters,
                                   optimizer, graph):
    """Repair historical stale size metadata by a NEW immutable generation.

    A bound checkpoint's source-verified graph and embedding tensor, not the
    initial inherited model config, own the current active vocabulary size.
    Historical 222-token prefix evidence and previously saved states survive.
    """
    actual = len(graph["tokens"])
    embedded = int(parameters["embedding.weight"].shape[0])
    if actual != embedded or actual < 1:
        raise ValueError("HUMAN_TRAINER_CURRENT_VOCAB_GRAPH_EMBEDDING_DRIFT")
    native = receipt["config"].get("answer_heads", {}).get("semantic_token")
    if native is not None and (
            len(native["token_ids"]) != actual or
            native["token_ids"] != list(range(actual))):
        raise ValueError("HUMAN_TRAINER_CURRENT_VOCAB_ANSWER_HEAD_DRIFT")
    previous = receipt["config"].get("vocab_size")
    if previous == actual:
        return receipt
    if type(previous) is not int or previous < 1 or previous > actual:
        raise ValueError("HUMAN_TRAINER_UNVERIFIED_VOCAB_METADATA_MIGRATION")
    school = _state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
    if int(optimizer.state["step"].item()) != school.current_student.optimizer_step:
        raise ValueError("HUMAN_TRAINER_VOCAB_RECONCILE_OWN_ADAMW_DRIFT")
    candidate = _advance(
        run_dir, {**receipt, "config": {**receipt["config"], "vocab_size": actual}},
        school, persist=False)
    event = {"event": "SCHOOL_CURRENT_VOCAB_METADATA_RECONCILED",
             "generation": candidate["generation"],
             "former_metadata_vocab_size": previous,
             "active_semantic_graph_vocab_size": actual,
             "student_sha256": school.current_student.sha256,
             "optimizer_step": school.current_student.optimizer_step,
             "model_and_optimizer_unchanged": True}
    result = _persist(run_dir, _with_delivery_outbox(candidate, (event,)))
    _reconcile_delivery_outbox(run_dir, result)
    return result


def _reconcile_learning_settings(run_dir, receipt, course, settings, optimizer):
    """Permit only narrower existing retention budgets on human resume.

    Previously selected strategy outcomes keep their historic settings. The
    full student and its AdamW are unchanged by this metadata-only boundary.
    An attempted loosening or an unreviewed probe redesign still fails closed.
    """
    inherited = receipt.get("learning_experiment")
    if inherited is None:
        return receipt
    if settings is None or inherited.get("version") != LEARNING_EXPERIMENT_VERSION:
        raise ValueError("LEARNING_EXPERIMENT_RESUME_REQUIRES_IDENTICAL_OPT_IN")
    new = asdict(settings)
    previous = inherited.get("settings")
    if previous == new:
        return receipt
    if not isinstance(previous, dict):
        raise ValueError("LEARNING_EXPERIMENT_HISTORY_INVALID")
    old = asdict(LearningSettings(**previous))
    if (new["probe_each"] != old["probe_each"] or
            new["protected_cap_limit"] != old["protected_cap_limit"] or
            new["introduction_extra_loss"] != old["introduction_extra_loss"] or
            new["mature_max_loss"] >= old["mature_max_loss"]):
        raise ValueError("LEARNING_EXPERIMENT_RESUME_REQUIRES_IDENTICAL_OPT_IN")
    school = _state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
    if int(optimizer.state["step"].item()) != school.current_student.optimizer_step:
        raise ValueError("LEARNING_EXPERIMENT_POLICY_OWN_ADAMW_DRIFT")
    prior = list(receipt.get("learning_policy_revisions", ()))
    change = {"from": old, "to": new,
              "from_generation": receipt["generation"],
              "optimizer_step": school.current_student.optimizer_step,
              "student_sha256": school.current_student.sha256}
    candidate = _advance(run_dir, {**receipt,
        "learning_experiment": {"version": LEARNING_EXPERIMENT_VERSION,
                                "settings": new},
        "learning_policy_revisions": [*prior, change]}, school, persist=False)
    event = {"event": "SCHOOL_EXPERIMENTAL_RETENTION_POLICY_TIGHTENED",
             "generation": candidate["generation"], **change,
             "model_and_optimizer_unchanged": True}
    result = _persist(run_dir, _with_delivery_outbox(candidate, (event,)))
    _reconcile_delivery_outbox(run_dir, result)
    return result


def _seed_saved_whole_student_peak(run_dir, receipt, course, optimizer):
    """Protect the already saved live exam before the next neural visit.

    Only an exam belonging to the current, fully durable checkpoint qualifies.
    Earlier rubric scores, orphan bundles and mismatched AdamW cannot seed it.
    """
    if receipt.get("whole_student_peaks"):
        return receipt
    school = _state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
    checkpoint = asdict(school.current_student)
    prior = receipt.get("last_exam") or {}
    if (not prior.get("scores") or
            prior.get("student_sha256") != checkpoint["sha256"] or
            prior.get("optimizer_step") != checkpoint["optimizer_step"]):
        return receipt
    if int(optimizer.state["step"].item()) != checkpoint["optimizer_step"]:
        raise ValueError("WHOLE_STUDENT_PEAK_SEED_ADAMW_DRIFT")
    peaks, outcome = advance_peaks(
        [], curriculum_mode=receipt["curriculum_mode"],
        numeric_maximum=receipt.get("numeric_maximum"),
        rubric_sha256=prior["exam_rubric_sha256"],
        cohort_sha256=prior["cohort_sha256"],
        assessment_scope_sha256=prior["assessment_scope_sha256"],
        scores=prior["scores"], checkpoint=checkpoint)
    candidate = _advance(run_dir, {**receipt, "whole_student_peaks": peaks},
                         school, persist=False)
    event = {"event": "SCHOOL_EXISTING_WHOLE_STUDENT_PEAK_PRESERVED",
             "generation": candidate["generation"],
             "optimizer_step": checkpoint["optimizer_step"],
             "student_sha256": checkpoint["sha256"],
             "exam_correct": outcome["best_correct"],
             "exam_total": outcome["best_total"],
             "source_cohort_sha256": prior["cohort_sha256"],
             "model_and_optimizer_unchanged": True}
    result = _persist(run_dir, _with_delivery_outbox(candidate, (event,)))
    _reconcile_delivery_outbox(run_dir, result)
    return result


def _teaching_enrichment_rows(source_root, graph, course, capability, *,
                              seed: int, enabled: bool, release=None):
    """Ask the capability's source adapter for optional source-grounded teaching."""
    if release is not None:
        from .factory.teaching import optional_teaching_rows
        return optional_teaching_rows(source_root, graph, release, live_source_registry(),
            capability=capability, seed=seed, enabled=enabled, legacy_course=course)
    return live_source_registry().optional_teaching_rows(
        course, capability=capability, source_root=source_root, graph=graph,
        seed=seed, enabled=enabled)


def _extend_binary_guidance(guidance, rows):
    """Keep existing mentor advice on the selected lesson; add zero-weight bridge rows."""
    if guidance is None or not rows:
        return guidance
    import numpy as np
    soft_target, strength = guidance
    extra_target = np.eye(2, dtype=np.float32)[
        [1 if row["gold"] == "TRUE" else 0 for row in rows]]
    return (
        np.concatenate((np.asarray(soft_target, dtype=np.float32), extra_target), axis=0),
        np.concatenate((np.asarray(strength, dtype=np.float32),
                        np.zeros(len(rows), dtype=np.float32))))


def _rehabilitate_sole_grade_debt(
        program, school, stagnation, debt, *, generation):
    """Keep training when containment debt is the only work left in one grade."""
    if (stagnation is None or school.stage != "DEFERRED_STAGNATION" or
            not debt):
        return stagnation, school, ()
    grades = {capability.partition(".")[0] for capability in debt}
    if len(grades) != 1:
        return stagnation, school, ()
    stagnation, event = activate_sole_grade_rehabilitation(
        stagnation, capabilities=tuple(debt), generation=generation)
    school = reactivate_stagnation_debt(program, school, tuple(debt))
    return stagnation, school, (event,)


def _reconcile_stagnation_scope(run_dir, receipt, course, school):
    """Keep command-local stagnation state aligned with the live scheduler scope."""
    control = receipt.get("stagnation_session")
    if control is None:
        return receipt
    required = assessment_capabilities(_schedule_for_receipt(run_dir, receipt, course), school)
    updated, event = reconcile_required_scope(
        control, required_capabilities=required,
        generation=receipt["generation"] + 1)
    if event is None:
        return receipt

    history = list(receipt.get("stagnation_scope_history", ()))
    history.append({
        "session_id": control["session_id"],
        "generation": receipt["generation"],
        "reconciled_at_grade": school.grade,
        "required_capabilities": list(control["required_capabilities"]),
        "quarantined": list(quarantined_capabilities(control)),
    })
    migrated = {
        **receipt,
        "stagnation_session": updated,
        "stagnation_scope_history": history[-32:],
    }
    record = _advance(
        run_dir, migrated, school, result=receipt.get("result"),
        persist=False)
    if record["generation"] != event["generation"]:
        raise ValueError("STAGNATION_SCOPE_RECONCILIATION_GENERATION_DRIFT")
    event = {**event, "grade": school.grade}
    record = _persist(run_dir, _with_delivery_outbox(record, (event,)))
    _reconcile_delivery_outbox(run_dir, record)
    return record


def _advance_stagnation_after_routine(
        *, program, school, routine_assessment, routine_advanced,
        stagnation, blocked_before, active_scope, routine_measured,
        routine_warnings, generation, quarantine_suppressed=()):
    """Apply one completed routine boundary to the current session containment."""
    events = ()
    if stagnation is None:
        return stagnation, events, routine_advanced, ()
    if (school.stage == "ASSESS_MAIN" and
            routine_advanced.stage == "RECOVERY_1"):
        stagnation = begin_recovery_cycle(
            stagnation, first_recovery=routine_advanced.first_recovery)
    elif school.stage == "ASSESS_RECOVERY_2":
        tail = weakest_three(routine_assessment.scores, active_scope)
        stagnation, events = complete_recovery_cycle(
            stagnation, weakest_tail=tail,
            scores=routine_measured["scores"],
            generation=generation,
            active_warnings=tuple(routine_warnings.get("active_warnings", ())),
            quarantine_suppressed=tuple(quarantine_suppressed))
        blocked_after = quarantined_capabilities(stagnation)
        if set(blocked_after) != set(blocked_before):
            retained_scores = {
                cap: score for cap, score in routine_assessment.scores.items()
                if cap not in set(blocked_after)}
            if not retained_scores:
                routine_advanced = replace(
                    school, stage="DEFERRED_STAGNATION", queue=(),
                    first_recovery=(),
                    latest_rubric_digest=routine_assessment.rubric_digest)
            else:
                reduced = Assessment(
                    checkpoint_sha256=routine_assessment.checkpoint_sha256,
                    optimizer_step=routine_assessment.optimizer_step,
                    course_digest=routine_assessment.course_digest,
                    rubric_digest=routine_assessment.rubric_digest,
                    scores=retained_scores,
                    evaluation_id=routine_assessment.evaluation_id +
                                  "/post-stagnation-filter")
                routine_advanced = assess_withheld(
                    program, school, reduced, blocked_after)
    if routine_advanced.stage == "DEFERRED_STAGNATION":
        stagnation, routine_advanced, rehabilitation_events = (
            _rehabilitate_sole_grade_debt(
                program, routine_advanced, stagnation,
                quarantined_capabilities(stagnation),
                generation=generation))
        events = (*events, *rehabilitation_events)
    return (
        stagnation, events, routine_advanced,
        quarantined_capabilities(stagnation))


def _learning_probe_rows(source_root, graph, receipt, course, school, capability,
                         settings, *, schedule_program=None, release=None):
    """Complete admitted target grade plus bounded cross-grade protection."""
    eligible = set(assessment_capabilities(
        schedule_program if schedule_program is not None else course,
        school)) | {capability}
    scores = (receipt.get("last_exam") or {}).get("scores") or {}
    from bilqis_mlx.learning.learning_experiment import whole_grade_protection
    selected = whole_grade_protection(
        eligible, capability, scores,
        cap_limit=settings.protected_cap_limit, rotation=school.visits)
    sampled = selected | {capability}
    # The target must show a positive change before a candidate is promoted.
    # A six-item panel is too coarse near mastery. Draw enough *fresh* source
    # questions to match the fixed examination's capability sample size,
    # capped at the existing maximum; keep protected probes inexpensive.
    exam_target_size = scores.get(capability, {}).get("total")
    target_each = (
        max(settings.probe_each, min(48, exam_target_size))
        if type(exam_target_size) is int and exam_target_size > 0
        else min(48, max(settings.probe_each, settings.probe_each * 2))
    )
    rows = []
    for name in sorted(sampled):
        rows.extend(_draw_live_rows(
            source_root, graph, course=course, release=release, capability=name,
            each=(target_each if name.partition(".")[0] ==
                  capability.partition(".")[0] else settings.probe_each),
            seed=_seed(receipt, capability="LEARNING_PROBE:"+name)))
    if {r["capability"] for r in rows} != sampled:
        raise ValueError("LEARNING_EXPERIMENT_PROBE_SCOPE_INCOMPLETE")
    return rows, selected, len(eligible)-len(sampled)


def _fixed_same_grade_rows(run_dir, receipt, course, school, capability, settings):
    """Reuse the last independently scored full-grade cohort, if available.

    No new test rows are generated here. The persisted cohort, rubric and
    content hash must all verify before the parent/challenger screen can
    claim a fixed-exam grade comparison.
    """
    own_grade = capability.partition(".")[0]
    exam = receipt.get("last_exam") or {}
    if (exam.get("assessment_grade") != own_grade or
            exam.get("grade_exam_epoch") != school.grade_exam_epoch):
        return ()
    required = {cap for cap in assessment_capabilities(_schedule_for_receipt(run_dir, receipt, course), school)
                if cap.partition(".")[0] == own_grade}
    exam_scores = exam.get("scores") or {}
    if not required <= set(exam_scores):
        return ()
    cohort = _verify_saved_cohort(run_dir, receipt, course)
    if cohort is None:
        raise ValueError("LEARNING_EXPERIMENT_FIXED_GRADE_COHORT_MISSING")
    rows = tuple(r for r in cohort.rows if r["capability"] in required)
    if (len(rows) != len({r["id"] for r in rows}) or
            len(rows) > len(required) * 48 or
            any(type(exam_scores[cap].get("total")) is not int or
                exam_scores[cap]["total"] < 1 or
                sum(row["capability"] == cap for row in rows) !=
                exam_scores[cap]["total"] for cap in required)):
        raise ValueError("LEARNING_EXPERIMENT_FIXED_GRADE_COHORT_INCOMPLETE")
    return rows


def _reusable_exam_identity(receipt, school, *, rubric_sha256,
                            assessment_scope_sha256):
    """Return the exact already-scored exam identity for an unchanged student."""
    exam = receipt.get("last_exam") or {}
    student = school.current_student
    if (exam.get("assessment_grade") != school.grade or
            exam.get("grade_exam_epoch") != school.grade_exam_epoch or
            exam.get("student_sha256") != student.sha256 or
            exam.get("optimizer_step") != student.optimizer_step or
            exam.get("exam_rubric_sha256") != rubric_sha256 or
            exam.get("assessment_scope_sha256") != assessment_scope_sha256):
        return None
    cohort_sha = exam.get("cohort_sha256")
    if (not isinstance(cohort_sha, str) or len(cohort_sha) != 64 or
            any(c not in "0123456789abcdef" for c in cohort_sha)):
        raise ValueError("HUMAN_TRAINER_REUSABLE_EXAM_COHORT_IDENTITY_INVALID")
    return (student.sha256, student.optimizer_step, cohort_sha,
            rubric_sha256, assessment_scope_sha256)


def _candidate_fixed_evidence(mx, run_dir, receipt, course, school, capability,
                              parent, candidate, settings):
    """Score only the fixed evidence needed after fresh grade gain is proven."""
    config, answer_ids = receipt["config"], receipt["answer_ids"]
    fixed = {"status": "NOT_MEASURED",
             "reason": "NO_COMPARABLE_COMPLETE_GRADE_EXAM"}
    frontier = {"status": "NOT_MEASURED",
                "reason": "NO_FIXED_WHOLE_SCHOOL_FRONTIER"}
    frontier_parent = frontier_candidate = {}
    from .fixed_frontier import load_frontier, screen_frontier
    frontier_rows, frontier_parent = load_frontier(
        run_dir, receipt,
        parent_sha256=school.current_student.sha256,
        parent_optimizer_step=school.current_student.optimizer_step)
    if frontier_rows:
        grade = capability.partition(".")[0]
        grade_rows = tuple(
            row for row in frontier_rows
            if row["capability"].partition(".")[0] == grade)
        if grade_rows:
            grade_parent = {
                row["id"]: frontier_parent[row["id"]] for row in grade_rows}
            grade_candidate = _predictions(
                mx, candidate, list(grade_rows), config, answer_ids)
            grade_scores = paired_outcomes(
                grade_rows, grade_parent, grade_candidate)
            fixed = {
                "status": "MEASURED", "grade": grade,
                "cohort_sha256": receipt["last_exam"]["cohort_sha256"],
                "before": sum(value["before"] for value in grade_scores.values()),
                "after": sum(value["after"] for value in grade_scores.values()),
                "total": sum(value["total"] for value in grade_scores.values()),
            }
            frontier_candidate = dict(grade_candidate)
        else:
            fixed = {
                "status": "NOT_MEASURED",
                "reason": "ACTIVE_GRADE_ABSENT_FROM_FIXED_FRONTIER",
            }
        other_rows = tuple(
            row for row in frontier_rows if row not in grade_rows)
        if other_rows:
            frontier_candidate.update(_predictions(
                mx, candidate, list(other_rows), config, answer_ids))
        frontier = screen_frontier(
            frontier_rows, frontier_parent, frontier_candidate,
            receipt["last_exam"]["cohort_sha256"])
    else:
        fixed_rows = _fixed_same_grade_rows(
            run_dir, receipt, course, school, capability, settings)
        if fixed_rows:
            parent_fixed = _predictions(
                mx, parent, list(fixed_rows), config, answer_ids)
            candidate_fixed = _predictions(
                mx, candidate, list(fixed_rows), config, answer_ids)
            scores = paired_outcomes(
                fixed_rows, parent_fixed, candidate_fixed)
            fixed = {
                "status": "MEASURED",
                "grade": capability.partition(".")[0],
                "cohort_sha256": receipt["last_exam"]["cohort_sha256"],
                "before": sum(value["before"] for value in scores.values()),
                "after": sum(value["after"] for value in scores.values()),
                "total": sum(value["total"] for value in scores.values()),
            }

    from bilqis_mlx.learning.fragile_replay import load_replay_rows, screen_replay
    replay_rows = load_replay_rows(
        run_dir, receipt,
        capabilities=fragile_preservation_capabilities())
    replay = {"status": "NOT_MEASURED",
              "reason": "FRAGILE_PRESERVATION_EXAM_NOT_YET_ADMITTED"}
    if replay_rows:
        ids = {row["id"] for row in replay_rows}
        replay_parent = (
            {rid: frontier_parent[rid] for rid in ids}
            if ids <= frontier_parent.keys() else
            _predictions(mx, parent, list(replay_rows), config, answer_ids))
        replay_candidate = (
            {rid: frontier_candidate[rid] for rid in ids}
            if ids <= frontier_candidate.keys() else
            _predictions(mx, candidate, list(replay_rows), config, answer_ids))
        replay = screen_replay(
            replay_rows, replay_parent, replay_candidate,
            receipt["last_exam"]["cohort_sha256"])
    return fixed, replay, frontier


def _candidate_grade_evidence(mx, run_dir, receipt, course, school, capability,
                              parent, candidate, probe_rows, target_parent,
                              settings):
    """Complete missing candidate scores only after a target gain is observed.

    Parent/candidate predictions are never reused across candidate weights,
    AdamW steps, source questions or source-cohort identities. A target failure
    is conclusive rejection without running redundant peer and exam inference.
    """
    config, answer_ids = receipt["config"], receipt["answer_ids"]
    target_rows = [row for row in probe_rows if row["capability"] == capability]
    target_candidate = _predictions(mx, candidate, target_rows, config, answer_ids)
    target_pair = paired_outcomes(target_rows, target_parent, target_candidate)
    required = tuple(sorted(
        name for name in assessment_capabilities(_schedule_for_receipt(run_dir, receipt, course), school)
        if name.partition(".")[0] == capability.partition(".")[0]))
    if target_pair[capability]["after"] <= target_pair[capability]["before"]:
        return (target_pair, set(), (capability,), {
            "status": "NOT_MEASURED", "reason": "TARGET_DID_NOT_GAIN"},
            {"status": "NOT_MEASURED", "reason": "TARGET_DID_NOT_GAIN"},
            {"status": "NOT_MEASURED", "reason": "TARGET_DID_NOT_GAIN"},
            "TARGET_ONLY_REJECTED")

    # This checkpoint has already been evaluated on its target. Score only
    # missing grade peers and independently selected cross-grade sentinels.
    missing = missing_grade_capabilities(required, target_pair)
    remaining = [row for row in probe_rows
                 if row["capability"] in missing or
                 row["capability"].partition(".")[0] != capability.partition(".")[0]]
    parent_scores = {**target_parent}
    candidate_scores = {**target_candidate}
    if remaining:
        parent_scores.update(_predictions(mx, parent, remaining, config, answer_ids))
        candidate_scores.update(_predictions(
            mx, candidate, remaining, config, answer_ids))
    pair = paired_outcomes(probe_rows, parent_scores, candidate_scores)
    if missing_grade_capabilities(required, pair):
        raise ValueError("LEARNING_EXPERIMENT_INCOMPLETE_SAME_GRADE_PROMOTION")
    protected = set(pair)-set(required)
    protected.update(name for name in required if name != capability)
    grade_net = sum(pair[name]["after"]-pair[name]["before"] for name in required)
    if grade_net < 0:
        return (pair, protected, required,
                {"status": "NOT_MEASURED",
                 "reason": "SAME_GRADE_NET_REGRESSION"},
                {"status": "NOT_MEASURED",
                 "reason": "SAME_GRADE_NET_REGRESSION"},
                {"status": "NOT_MEASURED",
                 "reason": "SAME_GRADE_NET_REGRESSION"},
                "GRADE_NET_REJECTED")

    fixed, replay, frontier = _candidate_fixed_evidence(
        mx, run_dir, receipt, course, school, capability, parent, candidate,
        settings)
    return (pair, protected, required, fixed, replay, frontier,
            "COMPLETE_SAME_GRADE")


def _fresh_fragile_preservation_rows(run_dir, source_root, graph, receipt,
                                     course, school, capability, *, step,
                                     batch_size, fixed_rows=None):
    """Generate fresh semantic siblings for the configured fragile safety rows.

    Rehearsal is active only after a source-verified B replay exam exists.
    The fixed examination rows themselves are never delivered to the optimizer.
    """
    from bilqis_mlx.learning.fragile_replay import (
        load_replay_rows, select_preservation_rows,
        select_structural_preservation_rows,
    )
    capabilities = fragile_preservation_capabilities()
    fixed = (tuple(fixed_rows) if fixed_rows is not None
             else load_replay_rows(
                 run_dir, receipt, capabilities=capabilities))
    if not fixed:
        return ()
    admitted = set(assessment_capabilities(_schedule_for_receipt(run_dir, receipt, course), school))
    requested = tuple(name for name in capabilities if name in admitted)
    if not requested:
        return ()
    excluded = {row["id"] for row in fixed}
    selected = []
    for name in requested:
        fixed_capability = tuple(
            row for row in fixed if row["capability"] == name)
        fresh = []
        matched = ()
        for attempt in range(3):
            fresh.extend(_draw_live_rows(
                source_root, graph,
                release=_read_executable_factory_release_artifact(run_dir, receipt),
                seed=_seed(
                    receipt,
                    capability=f"FRAGILE_PRESERVE:{name}:{attempt}",
                    step=step),
                capability=name, each=max(96, batch_size * 3), course=course))
            matched = select_structural_preservation_rows(
                fresh, fixed_capability, excluded_ids=excluded,
                rotation=max(0, step - 1) * 4, limit=4)
            if len(matched) >= 4:
                break
        delivered = list(matched)
        if len(delivered) < 4:
            try:
                fallback = select_preservation_rows(
                    fresh, capabilities=(name,), excluded_ids=excluded)
            except ValueError as exc:
                if str(exc) != "FRAGILE_PRESERVATION_INCOMPLETE_TRUTH_TABLE":
                    raise
                fallback = ()
            used = {row["id"] for row in delivered}
            for row in fallback:
                if row["id"] not in used:
                    delivered.append(row)
                    used.add(row["id"])
                if len(delivered) >= 4:
                    break
        selected.extend(delivered[:4])
    if any(row["id"] in excluded for row in selected):
        raise ValueError("FRAGILE_PRESERVATION_EXAM_ROW_LEAK")
    return tuple(selected)


def _inject_preservation_rows(chosen, preservation, *, reserved_ids=()):
    """Reserve optimizer slots for preservation without displacing exam misses."""
    result = list(chosen)
    reserved = set(reserved_ids)
    consumed = {index for index, row in enumerate(result)
                if row.get("id") in reserved}
    delivered = []
    for item in preservation:
        replacement = next((
            index for index, row in enumerate(result)
            if index not in consumed and row.get("gold") == item.get("gold")
        ), None)
        if replacement is None:
            replacement = next((
                index for index in range(len(result)) if index not in consumed
            ), None)
        if replacement is None:
            break
        result[replacement] = item
        consumed.add(replacement)
        delivered.append(item)
    if len(delivered) != len(preservation):
        raise ValueError("FRAGILE_PRESERVATION_BATCH_CAPACITY_EXHAUSTED")
    return result, tuple(delivered)


def _skip_perfect_target_visit(run_dir, receipt, school, course, capability,
                               probe_total, optimizer_step, *, teacher=None):
    """Advance the in-memory schedule without checkpointing a provisional model."""
    skipped_school = visit(_schedule_for_receipt(run_dir, receipt, course), school, capability, school.current_student)
    result = _advance(run_dir, receipt, skipped_school, teacher=teacher, persist=False)
    event = {
        "event": "SCHOOL_PERFECT_TARGET_VISIT_SKIPPED",
        "capability": capability,
        "grade": capability.partition(".")[0],
        "active_grade": skipped_school.grade,
        "generation": result["generation"],
        "optimizer_step": optimizer_step,
        "target_probe_correct": probe_total,
        "target_probe_total": probe_total,
        "retained_optimizer_updates": 0,
        "reason": "NO_POSSIBLE_STRICT_TARGET_GAIN",
    }
    result["_pending_visit_events"] = [
        *receipt.get("_pending_visit_events", ()), event]
    return result


def _skip_stagnant_target_visit(run_dir, receipt, school, course, capability,
                                optimizer_step):
    """Advance past a current-session quarantined capability without teaching."""
    skipped_school = visit(_schedule_for_receipt(run_dir, receipt, course), school, capability, school.current_student)
    result = _advance(run_dir, receipt, skipped_school, persist=False)
    event = {
        "event": "SCHOOL_STAGNANT_CAPABILITY_VISIT_SKIPPED",
        "capability": capability,
        "grade": capability.partition(".")[0],
        "active_grade": skipped_school.grade,
        "generation": result["generation"],
        "optimizer_step": optimizer_step,
        "retained_optimizer_updates": 0,
        "teacher_updated": False,
        "reason": "CURRENT_SESSION_STAGNATION_QUARANTINE",
        "required_mastery_debt": True,
    }
    result["_pending_visit_events"] = [
        *receipt.get("_pending_visit_events", ()), event]
    return result


def _take_visit(mx, run_dir, receipt, manifest, course, engine,
                params, optimizer, graph, *, steps_per_visit, batch_size, reserve_gib,
                source_root=None, learning_settings: LearningSettings | None = None,
                boolean_association_bridge: bool = False,
                source_prefetch_executor=None, source_prefetch_workers: int = 0,
                autonomy_teaching_option: str | None = None):
    school = _state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
    if (receipt.get("mentor_epoch") is not None and
            receipt.get("championship_school_identity") !=
            _live_championship_identity(receipt, course, graph, params)):
        raise ValueError("CHAMPIONSHIP_SCHOOL_IDENTITY_RESET_REQUIRED")
    cap = next_capability(school)
    if cap is None:
        raise ValueError("HUMAN_TRAINER_NO_SCHEDULED_CAPABILITY")
    stage_before = school.stage
    trace_mark(
        "VISIT_START", generation=receipt["generation"], capability=cap,
        phase=stage_before, optimizer_step=int(optimizer.state["step"].item()))
    if cap in set(quarantined_capabilities(receipt.get("stagnation_session"))):
        return _skip_stagnant_target_visit(
            run_dir, receipt, school, course, cap,
            int(optimizer.state["step"].item()))
    introduction_pass = school.stage == "MAIN"
    lesson_grade = cap.split(".", 1)[0]
    executable_release = _read_executable_factory_release_artifact(
        run_dir, receipt)
    program = schedule_program_from_executable_release(executable_release)
    if lesson_grade not in {grade.id for grade in program.grades}:
        raise ValueError("HUMAN_TRAINER_UNKNOWN_LESSON_GRADE")
    teacher = json.loads(_canonical(receipt["teacher"]))
    rng = random.Random(_seed(receipt, capability=cap))
    teacher_curriculum_scope = (str(receipt.get("curriculum_mode", "")) + "/" +
                                str(receipt.get("numeric_maximum", "")))
    with trace_span("POLICY_SELECT", capability=cap):
        if learning_settings is not None:
            policy_key, policy = contextual_pick(
                engine, teacher, cap, school.stage, rng,
                curriculum_scope=teacher_curriculum_scope)
        else:
            policy_key, policy = engine.pick(teacher, lesson_grade, rng)
    original_learning_rate = optimizer.learning_rate
    optimizer.learning_rate = float(policy["lr"])
    if source_root is None:
        raise ValueError("HUMAN_TRAINER_LIVE_SOURCE_REQUIRED")
    with trace_span("VISIT_SOURCE_DRAW", capability=cap):
        rows = _draw_live_rows(source_root, graph,
                               seed=_seed(receipt, capability=cap),
                               capability=cap, each=max(32, batch_size), course=course,
                               release=executable_release)
    # Active maxed capability roles advise only inside their own grade.
    # Frozen grade soups remain the separately diluted cross-grade voice.
    with trace_span("MENTOR_SOURCES_LOAD", capability=cap):
        confidence_champions, frozen_soups, soup_vote_receipts = _mentor_sources_for_visit(
            run_dir, receipt, lesson_grade, graph, len(program.grades))
    confidence_examples = 0
    confidence_total_weight = 0.0
    confidence_applied_steps = 0
    direct_capability_votes = {}
    direct_capabilities = []
    for mentor in confidence_champions:
        for source_grade, votes in mentor.get("source_grade_votes", {}).items():
            direct_capability_votes[source_grade] = (
                direct_capability_votes.get(source_grade, 0) + votes)
        direct_capabilities.extend(mentor.get("capabilities", ()))
    # Every unsuccessful examination construction can become direct teaching
    # material once scoring has completed. No held-out embargo survives.
    priority = [r for r in receipt.get("teacher_misses", ())
                if r["capability"] == cap]
    deferred_misses = []
    if receipt.get("numeric_maximum") is not None:
        deferred_misses = [
            row for row in priority
            if not numeric_row_in_scope(row, receipt["numeric_maximum"])]
        priority = [
            row for row in priority
            if numeric_row_in_scope(row, receipt["numeric_maximum"])]
    miss_exposures = dict(receipt.get("teacher_miss_exposures", {}))
    if any(type(count) is not int or count < 0 for count in miss_exposures.values()):
        raise ValueError("HUMAN_TRAINER_MISS_EXPOSURE_STATE_INVALID")
    selected_misses = set()
    rows.extend(priority)
    with trace_span("TRAIN_SCORE_BEFORE", capability=cap, row_count=len(rows)):
        before = _train_score(mx, params, rows, receipt["config"],
                              receipt["answer_ids"])
    parent_parameters, parent_optimizer = params, optimizer
    probe_rows = protected_caps = parent_predictions = None
    if learning_settings is not None:
        with trace_span("RETENTION_PROBE_BUILD", capability=cap):
            probe_rows, protected_caps, unsampled_caps = _learning_probe_rows(
                source_root, graph, receipt, course, school, cap, learning_settings,
                schedule_program=_schedule_for_receipt(
                    run_dir, receipt, course), release=executable_release)
        target_rows = [row for row in probe_rows if row["capability"] == cap]
        with trace_span("RETENTION_PARENT_PREDICT", capability=cap,
                        row_count=len(target_rows)):
            parent_predictions = _predictions(
                mx, parent_parameters, target_rows, receipt["config"], receipt["answer_ids"])
        if target_rows and all(parent_predictions[row["id"]] == row["gold"]
                               for row in target_rows):
            # A strict positive-gain gate cannot admit a trial whose fresh
            # target panel already scores perfectly. Preserve any accepted
            # in-memory student updates until their normal checkpoint boundary.
            parent_optimizer.learning_rate = original_learning_rate
            return _skip_perfect_target_visit(
                run_dir, receipt, school, course, cap, len(target_rows),
                int(parent_optimizer.state["step"].item()), teacher=teacher)
        with trace_span("FORK_CANDIDATE", capability=cap):
            params, optimizer = fork_student(mx, parent_parameters, parent_optimizer)
    last_loss = 0.0
    last_norm = 0.0
    methodology_steps = []
    methodology_unavailable = None
    replayed_misses = 0
    enrichment_examples = 0
    policy_control_receipts = []
    step_before = int(optimizer.state["step"].item())
    fragile_fixed_rows = ()
    if learning_settings is not None:
        from bilqis_mlx.learning.fragile_replay import load_replay_rows
        with trace_span("FRAGILE_REPLAY_LOAD", capability=cap):
            fragile_fixed_rows = load_replay_rows(
                run_dir, receipt,
                capabilities=fragile_preservation_capabilities())
    old_capabilities = (
        earlier_grade_capabilities(
            _schedule_for_receipt(run_dir, receipt, course),
            school.champions, cap)
        if learning_settings is not None else ())
    delivered_autonomy_rows = []
    autonomy_option_specimen_ids = set()
    prefetch_futures = {}
    prefetch_enabled = bool(
        learning_settings is not None and source_prefetch_executor is not None and
        source_prefetch_workers > 0 and autonomy_teaching_option is None)
    if prefetch_enabled:
        from bilqis_mlx.runtime.source_prefetch import SCHEMA as SOURCE_PREFETCH_SCHEMA, prepare_step_sources
        admitted = set(assessment_capabilities(_schedule_for_receipt(run_dir, receipt, course), school))
        fragile_requested = tuple(
            name for name in fragile_preservation_capabilities()
            if name in admitted)
        course_digest = course.digest()
        graph_digest = receipt.get("semantic_graph_sha256") or _fingerprint(graph)

        def source_request(step_index):
            selected = None
            if int(policy.get("old", 0)) > 0 and old_capabilities:
                selected = old_capabilities[(school.visits + step_index) % len(old_capabilities)]
            fresh_seed = _seed(receipt, capability=cap, step=step_index + 1)
            prior_seed = (_seed(
                receipt, capability="EXPERIMENT_OLD:" + selected, step=step_index)
                if selected is not None else None)
            fragile_seeds = {
                name: tuple(_seed(
                    receipt, capability=f"FRAGILE_PRESERVE:{name}:{attempt}",
                    step=step_index + 1) for attempt in range(3))
                for name in fragile_requested
            }
            teaching_seed = _seed(
                receipt, capability="TEACHING_ENRICHMENT:" + cap,
                step=step_index + 1)
            identity = _fingerprint({
                "schema": SOURCE_PREFETCH_SCHEMA,
                "run_id": receipt["run_id"],
                "generation": receipt["generation"],
                "source_manifest_sha256": receipt.get("source_manifest_sha256"),
                "course_digest": course_digest,
                "factory_release_sha256": executable_release.release_sha256,
                "graph_digest": graph_digest,
                "durable_parent_sha256": school.current_student.sha256,
                "parent_optimizer_step": step_before,
                "capability": cap,
                "visit_step": step_index + 1,
                "policy": policy,
                "prior_capability": selected,
                "batch_size": batch_size,
                "fresh_seed": fresh_seed,
                "prior_seed": prior_seed,
                "fragile_seeds": fragile_seeds,
                "teaching_seed": teaching_seed,
                "teaching_enrichment_enabled": boolean_association_bridge,
            })
            return {
                "identity": identity,
                "source_root": str(Path(source_root).resolve()),
                "graph": graph,
                "course": course,
                "factory_release": executable_release,
                "capability": cap,
                "batch_size": batch_size,
                "fresh_seed": fresh_seed,
                "prior_capability": selected,
                "prior_seed": prior_seed,
                "fragile_fixed_rows": tuple(fragile_fixed_rows),
                "fragile_requested": fragile_requested,
                "fragile_seeds": fragile_seeds,
                "fragile_rotation": step_index * 4,
                "teaching_seed": teaching_seed,
                "teaching_enrichment_enabled": boolean_association_bridge,
            }

        def submit_source_request(step_index):
            request = source_request(step_index)
            trace_mark(
                "STEP_SOURCE_PREFETCH_SUBMIT", capability=cap,
                visit_step=step_index + 1, identity=request["identity"])
            prefetch_futures[step_index] = (
                request, source_prefetch_executor.submit(prepare_step_sources, request))

        for step_index in range(min(source_prefetch_workers, steps_per_visit)):
            submit_source_request(step_index)
    for step in range(steps_per_visit):
        trace_mark("OPTIMIZER_STEP_START", capability=cap, visit_step=step + 1,
                   optimizer_step=int(optimizer.state["step"].item()))
        lesson_control = None
        prepared = None
        if prefetch_enabled:
            request, future = prefetch_futures.pop(step)
            with trace_span(
                    "STEP_SOURCE_PREFETCH_WAIT", capability=cap,
                    visit_step=step + 1, identity=request["identity"]):
                prepared = future.result()
            if (prepared.get("schema") != SOURCE_PREFETCH_SCHEMA or
                    prepared.get("identity") != request["identity"]):
                raise ValueError("HUMAN_TRAINER_SOURCE_PREFETCH_IDENTITY_DRIFT")
            next_step = step + source_prefetch_workers
            if next_step < steps_per_visit:
                submit_source_request(next_step)
            fresh = list(prepared["fresh"])
        else:
            with trace_span("STEP_SOURCE_DRAW", capability=cap, visit_step=step + 1):
                if autonomy_teaching_option is None:
                    fresh = _draw_live_rows(source_root, graph,
                        seed=_seed(receipt, capability=cap, step=step+1),
                        capability=cap, each=max(32, batch_size), course=course,
                        release=executable_release)
                else:
                    from .factory.teaching import draw_teaching_option_rows
                    fresh = list(draw_teaching_option_rows(
                        source_root, graph, executable_release, live_source_registry(),
                        capability=cap, option_id=autonomy_teaching_option,
                        seed=_seed(receipt, capability=cap, step=step+1),
                        each=max(32, batch_size), legacy_course=course))
                    autonomy_option_specimen_ids.update(
                        row["id"] for row in fresh)
        fresh.extend(priority)
        lesson_seed = _seed(receipt, capability=cap, step=step+1)
        with trace_span("STEP_LESSON_SELECT", capability=cap, visit_step=step + 1):
            if learning_settings is not None:
                # The same source-bound old-grade policy applies to Boolean and
                # typed lessons. Never label the target's own grade as old.
                prior = list(prepared["prior"]) if prepared is not None else []
                if prepared is None and int(policy.get("old", 0)) > 0 and old_capabilities:
                    selected = old_capabilities[(school.visits + step) % len(old_capabilities)]
                    prior = _draw_live_rows(source_root, graph, course=course,
                        release=executable_release,
                        capability=selected, each=max(batch_size, 6),
                        seed=_seed(receipt, capability="EXPERIMENT_OLD:"+selected, step=step))
                picked, control = select_source_lesson(
                    fresh, prior, policy, seed=lesson_seed, batch_size=batch_size)
                lesson_control = {**control, "eligible_prior_capabilities":
                                  len(old_capabilities)}
            else:
                picked = choose_lesson_batch(
                    fresh, policy, lesson_seed, batch_size=batch_size)
        preservation = ()
        delivered_preservation = ()
        if learning_settings is not None:
            if prepared is not None:
                preservation = tuple(prepared["preservation"])
            else:
                with trace_span("STEP_FRAGILE_PRESERVATION", capability=cap,
                                visit_step=step + 1):
                    preservation = _fresh_fragile_preservation_rows(
                        run_dir, source_root, graph, receipt, course, school, cap,
                        step=step + 1, batch_size=batch_size,
                        fixed_rows=fragile_fixed_rows)
            with trace_span("STEP_FRAGILE_PRESERVATION_INJECT", capability=cap,
                            visit_step=step + 1):
                picked, delivered_preservation = _inject_preservation_rows(
                    picked, preservation)
        preservation_ids = {row["id"] for row in delivered_preservation}
        gold_capacity = {
            gold: sum(row["gold"] == gold and row.get("id") not in preservation_ids
                      for row in picked)
            for gold in {row["gold"] for row in picked}
        }
        with trace_span("STEP_MISS_REPLAY", capability=cap, visit_step=step + 1,
                        available_misses=len(priority)):
            window = select_fair_miss_window(
                priority, FairMissRequest(
                    exposures=miss_exposures,
                    selected_this_visit=frozenset(selected_misses),
                    remaining_steps=steps_per_visit-step,
                    batch_size=batch_size,
                    gold_capacity=gold_capacity,
                ))
            picked = replay_missed_lessons(
                picked, window, reserved_ids=preservation_ids)
        if prepared is not None:
            enrichment_rows = tuple(prepared["teaching_enrichment_rows"])
        else:
            with trace_span("STEP_TEACHING_ENRICHMENT", capability=cap, visit_step=step + 1):
                enrichment_rows = _teaching_enrichment_rows(
                    source_root, graph, course, cap,
                    seed=_seed(receipt, capability="TEACHING_ENRICHMENT:" + cap,
                               step=step + 1),
                    enabled=boolean_association_bridge, release=executable_release)
        enrichment_examples += len(enrichment_rows)
        if lesson_control is not None:
            lesson_control["planned_old_grade_examples"] = lesson_control[
                "effective_old_grade_examples"]
            earlier_grades = {item.partition(".")[0] for item in old_capabilities}
            lesson_control["effective_old_grade_examples"] = sum(
                row["capability"].partition(".")[0] in earlier_grades for row in picked)
            lesson_control["selected_answer_kinds"] = sorted({
                row.get("answer_kind", "binary") for row in picked})
            lesson_control["fragile_preservation_requested"] = len(preservation)
            lesson_control["fragile_preservation_delivered"] = len(
                delivered_preservation)
            lesson_control["fragile_preservation_capabilities"] = sorted({
                row["capability"] for row in delivered_preservation})
            lesson_control["fragile_preservation_patterns"] = sorted({
                row["capability"] + ":" +
                "".join("1" if value else "0" for value in row["operand_truths"])
                for row in delivered_preservation})
            lesson_control["fragile_preservation_source"] = (
                "FRESH_SOURCE_TRUTH_TABLE_SIBLINGS")
            policy_control_receipts.append(lesson_control)
        for row in window:
            identity = row["id"]
            miss_exposures[identity] = miss_exposures.get(identity, 0) + 1
            selected_misses.add(identity)
        replayed_misses += len(window)
        with trace_span("STEP_DIAGNOSTIC_AND_GUIDANCE", capability=cap,
                        visit_step=step + 1):
            if methodology_unavailable is None:
                try:
                    methodology_steps.append(inspect_lesson_step(
                        course, cap, fresh, picked))
                except ValueError as exc:
                    # A diagnostic implementation gap must not invent a new
                    # training gate or silently change the evolved teacher.
                    methodology_unavailable = str(exc)
            typed_lesson = any(row.get("answer_kind", "binary") != "binary" for row in picked)
            if learning_settings is not None and typed_lesson:
                guidance = _typed_confidence_guidance(
                    mx, (*confidence_champions, *frozen_soups), picked, receipt["config"],
                    scope_size=len(executable_release.execution_plan.capabilities),
                    teacher_distill=float(policy.get("distill", 0.0)))
            else:
                guidance = _confidence_guidance(
                    mx, (*confidence_champions, *frozen_soups), picked, receipt["config"],
                    receipt["answer_ids"],
                    scope_size=len(executable_release.execution_plan.capabilities),
                    teacher_distill=float(policy.get("distill", 0.0)))
        if guidance is not None:
            import numpy as np
            influences = ([item[1] for item in guidance.values()]
                          if isinstance(guidance, dict) else [guidance[1]])
            confidence_examples += sum(int(np.count_nonzero(item)) for item in influences)
            confidence_total_weight += sum(float(np.sum(item)) for item in influences)
            confidence_applied_steps += 1
        training_rows = [*picked, *enrichment_rows]
        if autonomy_teaching_option is not None:
            delivered_autonomy_rows.extend(
                row for row in training_rows
                if row.get("id") in autonomy_option_specimen_ids)
        training_guidance = _extend_binary_guidance(guidance, enrichment_rows)
        with trace_span("STEP_TRAIN", capability=cap, visit_step=step + 1,
                        batch_size=len(training_rows)):
            last_loss, last_norm = _train_step(
                mx, params, optimizer, training_rows, receipt["config"],
                receipt["answer_ids"], champion_guidance=training_guidance)
        trace_mark("OPTIMIZER_STEP_END", capability=cap, visit_step=step + 1,
                   optimizer_step=int(optimizer.state["step"].item()))
    with trace_span("TRAIN_SCORE_AFTER", capability=cap, row_count=len(rows)):
        after = _train_score(mx, params, rows, receipt["config"],
                             receipt["answer_ids"])
    attempted_step = int(optimizer.state["step"].item())
    if attempted_step != step_before+steps_per_visit:
        raise ValueError("HUMAN_TRAINER_OPTIMIZER_STEP_DRIFT")
    candidate_gain = after-before
    outcome = context_credit = None
    if learning_settings is not None:
        with trace_span("RETENTION_CANDIDATE_EVIDENCE", capability=cap):
            pair, probed, current_grade, fixed_grade_evidence, replay, frontier, stage = (
                _candidate_grade_evidence(
                    mx, run_dir, receipt, course, school, cap,
                    parent_parameters, params, probe_rows,
                    parent_predictions, learning_settings))
        with trace_span("RETENTION_DECIDE", capability=cap):
            outcome = decide_learning_trial(
                pair, active_capability=cap, phase=school.stage,
                protected=probed, settings=learning_settings,
                same_grade_capabilities=current_grade,
                fixed_grade_replay=fixed_grade_evidence,
                fixed_frontier_replay=frontier,
                active_school_grade=school.grade,
                mature_grades=frozenset(school.champions),
                negative_prototypes=teacher["causal_experiment"]["negative_archetypes"],
                source_cohort_sha256=_fingerprint([
                    (r["id"],r["capability"],r["gold"],r["tokens"]) for r in probe_rows
                    if r["capability"] in pair]),
                fragile_replay=replay)
        outcome["qualification_stage"] = stage
        from bilqis_mlx.learning.matrix_strain import observe as observe_matrix_strain
        with trace_span("MATRIX_STRAIN", capability=cap):
            outcome["matrix_strain"] = observe_matrix_strain(
                mx, run_dir, receipt, parent_parameters, params)
        outcome["unsampled_admitted_capabilities"] = (
            len(set(assessment_capabilities(_schedule_for_receipt(run_dir, receipt, course), school)) | {cap})-len(pair))
        with trace_span("RETENTION_APPLY_DECISION", capability=cap,
                        decision=outcome["decision"]):
            context_credit = observe_context(
                teacher, capability=cap, phase=school.stage, policy_key=policy_key,
                decision=outcome, local_gain=candidate_gain,
                curriculum_scope=teacher_curriculum_scope)
            if outcome["decision"] == "PROVISIONAL":
                commit_trial(parent_parameters, parent_optimizer, params, optimizer)
            else:
                # The rejected candidate never owned the causal model, its
                # optimizer or the unresolved miss queue.
                parent_optimizer.learning_rate = original_learning_rate
                miss_exposures = dict(receipt.get("teacher_miss_exposures", {}))
                after = before
        params, optimizer = parent_parameters, parent_optimizer
    remaining_priority = priority
    if priority and (outcome is None or outcome["decision"] == "PROVISIONAL"):
        with trace_span("MISS_RECONCILE", capability=cap, miss_count=len(priority)):
            miss_guesses = _predictions(
                mx, params, priority, receipt["config"], receipt["answer_ids"])
            remaining_priority = reconcile_unresolved_misses(
                priority, priority, miss_guesses)
    remaining_priority_ids = {row["id"] for row in remaining_priority}
    resolved_priority_ids = {row["id"] for row in priority} - remaining_priority_ids
    for identity in resolved_priority_ids:
        miss_exposures.pop(identity, None)
    all_teacher_misses = [
        row for row in receipt.get("teacher_misses", ())
        if row["capability"] != cap
    ] + deferred_misses + remaining_priority
    all_teacher_misses.sort(key=lambda row: (row["capability"], row["id"]))
    reward = after - before
    bandit_credit = selection_credit(reward, outcome, context_credit)
    with trace_span("TEACHER_OBSERVE", capability=cap):
        engine.observe(teacher, lesson_grade, policy_key, bandit_credit)
    expected_retained = (step_before if outcome is not None and
                         outcome["decision"] == "REJECT" else attempted_step)
    attempted_optimizer_updates = attempted_step - step_before
    retained_optimizer_updates = expected_retained - step_before
    if attempted_optimizer_updates < 0:
        raise ValueError("HUMAN_TRAINER_ATTEMPTED_OPTIMIZER_STEP_REGRESSION")
    if retained_optimizer_updates < 0:
        raise ValueError("HUMAN_TRAINER_RETAINED_OPTIMIZER_STEP_REGRESSION")
    if int(optimizer.state["step"].item()) != expected_retained:
        raise ValueError("LEARNING_EXPERIMENT_RETAINED_ADAMW_STEP_DRIFT")
    # No new archive exists yet. The retained checkpoint is the last complete
    # recovery point, NOT a representation of these newly updated RAM weights.
    school = visit(_schedule_for_receipt(run_dir, receipt, course), school, cap, school.current_student)
    methodology = summarize_teaching_visit(
        course, cap, tuple(methodology_steps),
        introductory=introduction_pass,
        unmeasured_reason=methodology_unavailable)
    previous_methodology = next((
        member.get("lesson_methodology")
        for member in reversed(receipt.get("delivery_outbox", ()))
        if member.get("capability") == cap and "lesson_methodology" in member
    ), None)
    warnings = active_warning_signals(receipt.get("last_exam"), previous_methodology, cap)
    teacher_decision = summarize_teacher_decision(TeacherDecisionInput(
        capability=cap, policy_key=policy_key, warnings=warnings,
        unresolved_miss_count=len(priority),
        champion_candidate_count=0,
        prerequisite_capabilities=(
            executable_release.execution_plan.capability_map[cap].prerequisites),
        methodology=methodology,
        delivered_examples=steps_per_visit*batch_size,
        replayed_misses=replayed_misses,
        resolved_exam_misses=len(resolved_priority_ids),
        champion_prioritized=0,
        seed=_seed(receipt, capability=cap),
    ))
    event = {
        "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
        "grade": lesson_grade,
        "active_grade": school.grade,
        "generation": receipt["generation"] + 1,
        "capability": cap, "teacher_policy": policy_key,
        "strategy": policy, "loss": last_loss, "gradient_norm": last_norm,
        "source_training_accuracy_before": before,
        "source_training_accuracy_after": after,
        "teacher_reward": reward,
        "teacher_selection_reward": bandit_credit,
        "attempted_optimizer_updates": attempted_optimizer_updates,
        "source_prefetch": {
            "schema": "bilqis.mlx.source-prefetch/v1",
            "mode": "PROCESS_POOL" if prefetch_enabled else "SERIAL",
            "workers": source_prefetch_workers if prefetch_enabled else 0,
            "prepared_steps": steps_per_visit if prefetch_enabled else 0,
            "serial_steps": 0 if prefetch_enabled else steps_per_visit,
            "packet_identity_verified": prefetch_enabled,
            "neural_owner": "MAIN_LANE_ONLY",
        },
        **({"teaching_enrichment": {
            "enabled": True,
            "active_for_visit": len(executable_release.execution_plan.capability_map[cap].teaching_option_ids) > 1,
            "option_ids": list(executable_release.execution_plan.capability_map[cap].teaching_option_ids[1:]),
            "delivered_examples": enrichment_examples,
            "exam_rubric_changed": False,
        }} if boolean_association_bridge else {}),
        **({"lesson_policy_controls": {
            "optimizer_batches_observed": len(policy_control_receipts),
            "old_grade_examples_delivered": sum(
                r["effective_old_grade_examples"] for r in policy_control_receipts),
            "last_batch_controls": policy_control_receipts[-1]}}
           if policy_control_receipts else {}),
        **({"typed_policy_controls": {
            "optimizer_batches_observed": len(policy_control_receipts),
            "old_grade_examples_delivered": sum(
                r["effective_old_grade_examples"] for r in policy_control_receipts),
            "last_batch_controls": policy_control_receipts[-1]}}
           if policy_control_receipts and any(
               kind != "binary" for r in policy_control_receipts
               for kind in r["selected_answer_kinds"]) else {}),
        **({"candidate_retention": outcome, "context_teacher_credit": context_credit,
            "candidate_source_training_gain": candidate_gain,
            "candidate_attempt_optimizer_step": attempted_step,
            "retained_optimizer_updates": retained_optimizer_updates}
           if outcome is not None else {}),
        "generator_version": executable_release.source_bindings.by_capability[cap].generator_id,
        "generator_code_sha256": executable_release.execution_plan.capability_map[cap].provider_implementation_sha256,
        "lesson_source_sha256": manifest["manifest_sha256"],
        "lesson_seed": _seed(receipt, capability=cap),
        "prior_exam_misses_available": len(priority),
        "prior_exam_misses_deferred_by_scope": len(deferred_misses),
        "prior_exam_misses_remaining": len(remaining_priority),
        "prior_grade_champion_votes": {
            source_grade: votes for source_grade, votes in direct_capability_votes.items()
            if source_grade != lesson_grade},
        "champion_directed_examples_available": 0,
        "champion_confidence": {
            "policy": CHAMPION_CONFIDENCE_POLICY,
            "frozen_unique_champions": len(confidence_champions),
            "direct_capability_votes": dict(sorted(direct_capability_votes.items())),
            "direct_capabilities": sorted(direct_capabilities),
            "frozen_grade_soups": list(soup_vote_receipts),
            "teacher_distill": float(policy.get("distill", 0.0)),
            "examples_with_gold_agreeing_advice": confidence_examples,
            "total_per_row_influence": round(confidence_total_weight, 8),
            "guided_optimizer_steps": confidence_applied_steps,
        },
        "lesson_methodology": methodology,
        "teacher_decision": teacher_decision,
        "optimizer_step": int(optimizer.state["step"].item()),
        "next_phase": school.stage,
        "checkpoint_status": "PROVISIONAL_UNTIL_NEXT_RECOVERY_BOUNDARY",
        "unavailable_teacher_dimensions": (
            (["old"] if not any(r["eligible_prior_capabilities"]
                                  for r in policy_control_receipts) else []) +
            ["preview"] + ([] if confidence_applied_steps else ["distill"])),
    }
    if autonomy_teaching_option is not None and delivered_autonomy_rows:
        from .factory.teaching import describe_delivered_teaching
        delivery = describe_delivered_teaching(
            executable_release, cap, autonomy_teaching_option,
            delivered_autonomy_rows)
        teaching_file = ("autonomy/teaching/" + delivery.specimen_content_sha256 + ".json")
        _durable_json(run_dir / teaching_file, {"rows": delivered_autonomy_rows})
        event["autonomy_teaching"] = {**asdict(delivery), "specimen_file": teaching_file}
    stagnation = receipt.get("stagnation_session")
    if stagnation is not None:
        stagnation = record_stagnation_visit(
            stagnation, capability=cap, phase=stage_before,
            decision=outcome.get("decision") if isinstance(outcome, dict) else None,
            retained_optimizer_updates=retained_optimizer_updates,
            generation=event["generation"])
    pending = list(receipt.get("_pending_visit_events", ()))
    pending.append(event)
    with trace_span("VISIT_ADVANCE_STATE", capability=cap):
        result = _advance(run_dir, receipt, school, teacher=teacher, persist=False)
    if retained_optimizer_updates > 0:
        result["last_retained_update_grade"] = lesson_grade
    if learning_settings is not None:
        result["learning_experiment"] = {
            "version": LEARNING_EXPERIMENT_VERSION,
            "settings": asdict(learning_settings),
        }
    result["teacher_misses"] = all_teacher_misses
    result["teacher_miss_exposures"] = miss_exposures
    if stagnation is not None:
        result["stagnation_session"] = stagnation
    result.pop("teacher_miss_cursor", None)
    result["_pending_visit_events"] = pending
    trace_mark(
        "VISIT_END", generation=result["generation"], capability=cap,
        optimizer_step=int(optimizer.state["step"].item()),
        decision=outcome.get("decision") if isinstance(outcome, dict) else None)
    return result


def _compare_incumbents(mx, run_dir, receipt, cohort, config, answer_ids, graph):
    """Replay every unique historical and current leader on this exact cohort."""
    historic = receipt.get("historical_capability_best", {}) if receipt.get(
        "legacy_frontier_pending_replay") else {}
    current = receipt.get("capability_best", {})
    references = list(current.values()) + list(historic.values()) + list(receipt.get("graduation_perfect", {}).values())
    references.extend({"checkpoint": p} for p in
                      receipt.get("historical_grade_champions", {}).values())
    # A graduate keeps a teacher/champion vote even if its current capability
    # best slot was superseded under a newer multi-grade rubric.
    references.extend({"checkpoint": p} for p in
                      receipt["school"]["champions"].values())
    unique = {}
    for item in references:
        pointer = item["checkpoint"]
        unique[pointer["sha256"]] = pointer
    best = {}
    comparisons = []
    for sha, pointer in sorted(unique.items()):
        path = run_dir / pointer["filename"]
        if (path.parent != run_dir / "bundles" or path.is_symlink()):
            raise ValueError("HUMAN_TRAINER_INCUMBENT_UNSAFE_PATH")
        weights, own_optimizer, meta, loaded_graph = load_semantically_bound_bundle(path)
        if (not _compatible_graphs(loaded_graph, graph) or meta["safetensors_sha256"] != sha or
                meta["optimizer_step"] != pointer["optimizer_step"]):
            raise ValueError("HUMAN_TRAINER_INCUMBENT_CHECKPOINT_DRIFT")
        supported = {cap for cap in {r["capability"] for r in cohort.rows}
            if all(max(r["tokens"]) < len(loaded_graph["tokens"])
                   for r in cohort.rows if r["capability"] == cap)}
        readable = tuple(r for r in cohort.rows if r["capability"] in supported)
        if not readable:
            continue
        subset = make_cohort(readable, generator_version=cohort.generator_version,
                             seed=cohort.seed, rubric_version=cohort.rubric_version)
        guesses = _predictions(mx, weights, readable,
            _compatible_answer_config(config, loaded_graph), answer_ids)
        measured = score_cohort(subset, guesses, pointer)
        comparisons.append({"checkpoint": dict(pointer),
                            "cohort_sha256": cohort.digest,
                            "scored_capabilities": sorted(supported),
                            "unsupported_capabilities": sorted(
                                {r["capability"] for r in cohort.rows}-supported),
                            "scores": measured["scores"]})
        for cap, value in measured["scores"].items():
            prior = best.get(cap)
            if prior is None or value["correct"] > prior["correct"]:
                best[cap] = {"rubric": receipt["live_rubric_sha256"],
                             "capability": cap, **value, "checkpoint": dict(pointer),
                             "evaluation_id": "same-cohort-incumbent/" + cohort.digest}
        del weights, own_optimizer
    frontier = {item["rubric"] + ":" + cap: item for cap, item in best.items()}
    return frontier, comparisons


def _score_parent_for_paired_s3(mx, run_dir, receipt, parent, cohort, graph,
                                current_scores):
    """Read-only parent inference on this fresh cohort for S3 comparability."""
    path = run_dir / parent.filename
    try:
        if (path.is_symlink() or path.parent != run_dir / "bundles" or
                not parent.filename.startswith("bundles/")):
            raise ValueError("DIAGNOSTIC_PAIRED_S3_UNSAFE_PARENT")
        weights, own_adamw, meta, loaded_graph = load_semantically_bound_bundle(path)
        if (meta["safetensors_sha256"] != parent.sha256 or
                meta["optimizer_step"] != parent.optimizer_step or
                loaded_graph != graph):
            raise ValueError("DIAGNOSTIC_PAIRED_S3_PARENT_DRIFT")
        del own_adamw
        predictions = _predictions(
            mx, weights, tuple(cohort.rows), receipt["config"],
            receipt["answer_ids"])
        measured = score_cohort(cohort, predictions, asdict(parent))["scores"]
        del weights
        if set(measured) != set(current_scores):
            raise ValueError("DIAGNOSTIC_PAIRED_S3_SCOPE_DRIFT")
        return measured, None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return None, str(exc)


def _epoch_paired_examinations(mx, run_dir, receipt, course, school,
                               cohort, scores, predictions, graph, *,
                               challenge_grade=None):
    """Re-examine only potentially displaced epoch incumbents on these rows."""
    epoch = receipt["mentor_epoch"]
    if epoch["source_graph_sha256"] != _fingerprint(graph):
        raise ValueError("CHAMPIONSHIP_EPOCH_SOURCE_GRAPH_DRIFT")
    if (epoch.get("championship_school_identity") !=
            receipt.get("championship_school_identity")):
        raise ValueError("CHAMPIONSHIP_EPOCH_SCHOOL_IDENTITY_RESET_REQUIRED")
    executable_release = _read_executable_factory_release_artifact(
        run_dir, receipt)
    program = schedule_program_from_executable_release(executable_release)
    grades = {
        grade.id: tuple(capability.id for capability in grade.capabilities)
        for grade in program.grades}
    allowed_scope = assessment_capabilities(program, school)
    materialized = tuple(dict.fromkeys(row["capability"] for row in cohort.rows))
    if (not materialized or set(scores) != set(materialized) or
            not set(materialized) <= set(allowed_scope)):
        raise ValueError("CHAMPIONSHIP_EPOCH_INCOMPLETE_EXAM")
    scope = tuple(cap for cap in allowed_scope if cap in set(materialized))
    from .factory.assessment import assessment_scope_contract
    rubric = assessment_scope_contract(
        executable_release, scope).rubric_sha256
    cohort_rubric = cohort.rubric_version
    checkpoint_origin_grade = receipt.get(
        "championship_checkpoint_origins", {}).get(school.current_student.sha256)
    title_grade = challenge_grade or checkpoint_origin_grade or school.grade
    if title_grade not in grades:
        raise ValueError("CHAMPIONSHIP_EPOCH_CHALLENGE_GRADE_INVALID")
    if checkpoint_origin_grade not in grades:
        raise ValueError("CHAMPIONSHIP_CHECKPOINT_ORIGIN_PROVENANCE_INVALID")
    if not any(capability in scores for capability in grades[title_grade]):
        raise ValueError("CHAMPIONSHIP_EPOCH_CHALLENGE_GRADE_UNMEASURED")
    context = {
        "cohort_sha256": cohort.digest,
        "rubric_sha256": rubric,
        "cohort_rubric_sha256": cohort_rubric,
        "assessment_scope_sha256": _fingerprint(scope),
        "source_graph_sha256": _fingerprint(graph),
        "source_oracle_sha256": receipt["source_manifest_sha256"],
        # Title jurisdiction follows the capability grade being adjudicated.
        # The optimizer visit that produced this intact checkpoint remains
        # separate provenance and must never suppress valid capability evidence.
        "challenge_grade": title_grade,
        "checkpoint_origin_grade": checkpoint_origin_grade,
    }
    challenger = {**context, "checkpoint": asdict(school.current_student),
                  "scores": scores,
                  "questions": _championship_questions(cohort),
                  "correct_questions": _championship_correct_questions(cohort, predictions)}
    requested = epoch_needed_incumbents(
        epoch, grades=grades, challenger_exam=challenger)
    incumbents = {}
    for sha, pointer in sorted(requested.items()):
        if sha == school.current_student.sha256:
            incumbents[sha] = challenger
            continue
        path = run_dir / pointer["filename"]
        if (path.is_symlink() or path.parent != run_dir / "bundles" or
                not pointer["filename"].startswith("bundles/")):
            raise ValueError("CHAMPIONSHIP_EPOCH_UNSAFE_INCUMBENT")
        weights, own_adamw, meta, loaded_graph = load_semantically_bound_bundle(path)
        if (meta["safetensors_sha256"] != sha or
                meta["optimizer_step"] != pointer["optimizer_step"] or
                not _compatible_graphs(loaded_graph, graph)):
            raise ValueError("CHAMPIONSHIP_EPOCH_INCOMPARABLE_INCUMBENT_GRAPH")
        del own_adamw
        challenge_caps = set(grades[title_grade])
        grade_rows = tuple(row for row in cohort.rows
                           if row["capability"] in challenge_caps)
        grade_cohort = make_cohort(
            grade_rows, generator_version=cohort.generator_version,
            seed=cohort.seed, rubric_version=cohort.rubric_version)
        readable = _readable_championship_rows(grade_cohort, loaded_graph, receipt)
        subset = make_cohort(readable, generator_version=cohort.generator_version,
                             seed=cohort.seed, rubric_version=cohort.rubric_version) if readable else None
        config = (_compatible_answer_config(receipt["config"], loaded_graph)
                  if any(row.get("answer_kind", "binary") != "binary" for row in readable)
                  else receipt["config"])
        predictions = (_predictions(mx, weights, readable, config, receipt["answer_ids"])
                       if readable else {})
        measured = score_cohort(subset, predictions, pointer) if subset else {"scores": {}}
        incumbents[sha] = {**context, "checkpoint": dict(pointer),
                           "checkpoint_graph_sha256": _fingerprint(loaded_graph),
                           "scored_subset_sha256": subset.digest if subset else None,
                           "scores": measured["scores"],
                           "questions": _championship_questions(subset) if subset else {},
                           "correct_questions": (
                               _championship_correct_questions(subset, predictions)
                               if subset else {})}
        del weights
    return grades, challenger, incumbents


def _readable_championship_rows(cohort, graph, receipt):
    """A prefix incumbent must answer each entire comparable capability panel."""
    vocabulary = len(graph["tokens"])
    unsupported = set()
    for row in cohort.rows:
        kind = row.get("answer_kind", "binary")
        answers = (receipt["answer_ids"] if kind == "binary" else
                   receipt["config"].get("answer_heads", {}).get(kind, {}).get("token_ids", ()))
        if max(row["tokens"]) >= vocabulary or not answers or max(answers) >= vocabulary:
            unsupported.add(row["capability"])
    return tuple(row for row in cohort.rows if row["capability"] not in unsupported)


def _championship_correct_questions(cohort, predictions):
    return {cap: [{"id": row["id"], "gold": row["gold"]}
                  for row in cohort.rows
                  if row["capability"] == cap and predictions[row["id"]] == row["gold"]]
            for cap in {row["capability"] for row in cohort.rows}}


def _championship_questions(cohort):
    return {cap: [{"id": row["id"], "gold": row["gold"]}
                  for row in cohort.rows if row["capability"] == cap]
            for cap in {row["capability"] for row in cohort.rows}}


def _hydrate_championship_witnesses(mx, run_dir, receipt, epoch, graph):
    """Recover legacy earning questions from their immutable cohort and owner."""
    updated = deepcopy(epoch)
    recovered = {}
    for role in updated.get("active_roles", {}).values():
        if verified_witnesses(role):
            continue
        context = {
            "cohort_sha256": role["cohort_sha256"], "rubric_sha256": role["rubric"],
            "cohort_rubric_sha256": role.get(
                "cohort_rubric_sha256", role["rubric"]),
            "source_oracle_sha256": receipt["source_manifest_sha256"],
        }
        pointer = role["checkpoint"]
        identity = (pointer["sha256"], context["cohort_sha256"])
        if identity not in recovered:
            cohort = load_championship_cohort(run_dir, context)
            context["assessment_scope_sha256"] = role.get(
                "assessment_scope_sha256", _fingerprint(tuple(dict.fromkeys(
                    row["capability"] for row in cohort.rows))))
            path = run_dir / pointer["filename"]
            if path.is_symlink() or path.parent != run_dir / "bundles":
                raise ValueError("CHAMPIONSHIP_EARNING_CHECKPOINT_UNSAFE")
            content = (path / "model-and-own-adamw.safetensors").stat()
            weights, source_graph = _cached_frozen_champion(
                str(path), pointer["sha256"], pointer["optimizer_step"],
                content.st_size, content.st_mtime_ns)
            if not _compatible_graphs(source_graph, graph):
                raise ValueError("CHAMPIONSHIP_EARNING_GRAPH_DRIFT")
            context["source_graph_sha256"] = _fingerprint(source_graph)
            config = (_compatible_answer_config(receipt["config"], source_graph)
                      if any(row.get("answer_kind", "binary") != "binary" for row in cohort.rows)
                      else receipt["config"])
            guesses = _predictions(mx, weights, list(cohort.rows),
                                   config, receipt["answer_ids"])
            measured = score_cohort(cohort, guesses, pointer)
            recovered[identity] = {
                **context, "scores": measured["scores"],
                "questions": _championship_questions(cohort),
                "correct_questions": _championship_correct_questions(cohort, guesses)}
        earned = recovered[identity]
        if earned["scores"][role["capability"]] != {
                "correct": role["correct"], "total": role["total"]}:
            raise ValueError("CHAMPIONSHIP_EARNING_SCORE_DRIFT")
        role["qualification_witnesses"] = [earning_witness(earned, tuple(earned["scores"]))]
    return updated


def _fresh_title_current_exam(mx, receipt, cohort, pointer, parameters, graph, context,
                              capability):
    """Freshly replay the current cohort; title adjudication never reuses model answers."""
    panel_rows = [row for row in cohort.rows if row["capability"] == capability]
    if not panel_rows:
        raise ValueError("CHAMPIONSHIP_TITLE_MATCH_CURRENT_PANEL_UNMEASURED")
    panel = make_cohort(
        panel_rows,
        generator_version=cohort.generator_version, seed=cohort.seed,
        rubric_version=cohort.rubric_version)
    readable = _readable_championship_rows(panel, graph, receipt)
    if len(readable) != len(panel.rows):
        raise ValueError("CHAMPIONSHIP_TITLE_MATCH_CURRENT_PANEL_INCOMPARABLE")
    subset = make_cohort(readable, generator_version=cohort.generator_version,
                         seed=cohort.seed, rubric_version=cohort.rubric_version)
    config = (_compatible_answer_config(receipt["config"], graph)
              if any(row.get("answer_kind", "binary") != "binary" for row in readable)
              else receipt["config"])
    predictions = _predictions(mx, parameters, readable, config, receipt["answer_ids"])
    measured = score_cohort(subset, predictions, pointer)
    return {
        **context, "checkpoint": dict(pointer), "scores": measured["scores"],
        "questions": _championship_questions(subset),
        "correct_questions": _championship_correct_questions(subset, predictions),
    }


def _fresh_battery_results(mx, run_dir, receipt, role, parameters, graph):
    """Fresh model inference over one capability's surviving battery, with no answer cache."""
    selected_by_segment = {}
    batched_rows = []
    for segment in verified_battery(role):
        cohort = load_championship_cohort(run_dir, segment)
        rows = {row["id"]: row for row in cohort.rows}
        selected = []
        for question in segment["questions"]:
            row = rows.get(question["id"])
            if (row is None or row["gold"] != question["gold"] or
                    row["capability"] != question["capability"]):
                raise ValueError("CHAMPIONSHIP_BATTERY_QUESTION_DRIFT")
            selected.append(row)
        readable = _readable_championship_rows(
            make_cohort(selected, generator_version=cohort.generator_version,
                        seed=cohort.seed, rubric_version=cohort.rubric_version),
            graph, receipt)
        if len(readable) != len(selected):
            raise ValueError("CHAMPIONSHIP_BATTERY_CHECKPOINT_INCOMPARABLE")
        selected_by_segment[segment["sha256"]] = tuple(readable)
        batched_rows.extend(readable)
    if not batched_rows:
        return {}
    if len({row["id"] for row in batched_rows}) != len(batched_rows):
        raise ValueError("CHAMPIONSHIP_BATTERY_BATCH_DUPLICATE_QUESTION")
    config = (_compatible_answer_config(receipt["config"], graph)
              if any(row.get("answer_kind", "binary") != "binary"
                     for row in batched_rows)
              else receipt["config"])
    # Freshness is about when model answers are produced, not one device launch
    # per immutable evidence segment.  Verify every segment independently above,
    # then infer the complete title battery once and partition those fresh
    # answers back to their original segment receipts.
    with trace_span(
            "CHAMPIONSHIP_BATTERY_INFERENCE",
            capability=role.get("capability"),
            battery_segments=len(selected_by_segment),
            battery_rows=len(batched_rows)):
        predictions = _predictions(
            mx, parameters, batched_rows, config, receipt["answer_ids"])
    return {
        sha256: [row["id"] for row in rows
                 if predictions[row["id"]] == row["gold"]]
        for sha256, rows in selected_by_segment.items()
    }


def _fresh_title_match(mx, run_dir, receipt, epoch, cohort, challenger,
                       parameters, graph, capability):
    """Put incumbent and contender through fresh current + historic battery inference."""
    role = epoch["active_roles"][capability]
    pointer = role["checkpoint"]
    path = run_dir / pointer["filename"]
    if (path.is_symlink() or path.parent != run_dir / "bundles" or
            not pointer["filename"].startswith("bundles/")):
        raise ValueError("CHAMPIONSHIP_TITLE_MATCH_UNSAFE_INCUMBENT")
    weights, own_adamw, meta, incumbent_graph = load_semantically_bound_bundle(path)
    if (meta["safetensors_sha256"] != pointer["sha256"] or
            meta["optimizer_step"] != pointer["optimizer_step"] or
            not _compatible_graphs(incumbent_graph, graph)):
        raise ValueError("CHAMPIONSHIP_TITLE_MATCH_INCUMBENT_DRIFT")
    del own_adamw
    context = {key: challenger[key] for key in (
        "cohort_sha256", "rubric_sha256", "assessment_scope_sha256",
        "source_graph_sha256", "source_oracle_sha256",
        "cohort_rubric_sha256")}
    fresh_incumbent = _fresh_title_current_exam(
        mx, receipt, cohort, pointer, weights, incumbent_graph, context, capability)
    fresh_challenger = _fresh_title_current_exam(
        mx, receipt, cohort, challenger["checkpoint"], parameters, graph, context, capability)
    incumbent_battery = _fresh_battery_results(
        mx, run_dir, receipt, role, weights, incumbent_graph)
    challenger_battery = _fresh_battery_results(
        mx, run_dir, receipt, role, parameters, graph)
    del weights
    return {
        "incumbent_checkpoint_sha256": pointer["sha256"],
        "challenger_checkpoint_sha256": challenger["checkpoint"]["sha256"],
        "incumbent_current_exam": fresh_incumbent,
        "challenger_current_exam": fresh_challenger,
        "battery_results": {
            pointer["sha256"]: incumbent_battery,
            challenger["checkpoint"]["sha256"]: challenger_battery,
        },
    }


def _fresh_fanout_screen(mx, run_dir, receipt, epoch, cohort, challenger,
                         parameters, graph, capabilities):
    """Freshly pair the new champion with same-grade sibling incumbents once."""
    context = {key: challenger[key] for key in (
        "cohort_sha256", "rubric_sha256", "assessment_scope_sha256",
        "source_graph_sha256", "source_oracle_sha256",
        "cohort_rubric_sha256")}
    result = {}
    for capability in capabilities:
        role = epoch["active_roles"].get(capability)
        if role is None:
            continue
        pointer = role["checkpoint"]
        if pointer["sha256"] == challenger["checkpoint"]["sha256"]:
            continue
        path = run_dir / pointer["filename"]
        if (path.is_symlink() or path.parent != run_dir / "bundles" or
                not pointer["filename"].startswith("bundles/")):
            raise ValueError("CHAMPIONSHIP_FANOUT_UNSAFE_INCUMBENT")
        weights, own_adamw, meta, incumbent_graph = load_semantically_bound_bundle(path)
        if (meta["safetensors_sha256"] != pointer["sha256"] or
                meta["optimizer_step"] != pointer["optimizer_step"] or
                not _compatible_graphs(incumbent_graph, graph)):
            raise ValueError("CHAMPIONSHIP_FANOUT_INCUMBENT_DRIFT")
        del own_adamw
        incumbent_exam = _fresh_title_current_exam(
            mx, receipt, cohort, pointer, weights, incumbent_graph, context, capability)
        challenger_exam = _fresh_title_current_exam(
            mx, receipt, cohort, challenger["checkpoint"], parameters, graph,
            context, capability)
        del weights
        result[capability] = {
            "incumbent_checkpoint_sha256": pointer["sha256"],
            "challenger_checkpoint_sha256": challenger["checkpoint"]["sha256"],
            "incumbent_exam": incumbent_exam,
            "challenger_exam": challenger_exam,
        }
    return result


def _advance_exam_championship_grade(mx, run_dir, receipt, epoch, course, school,
                                     cohort, measured, predictions, parameters, graph,
                                     *, challenge_grade):
    current = {**receipt, "mentor_epoch": epoch}
    grades, challenger, incumbents = _epoch_paired_examinations(
        mx, run_dir, current, course, school, cohort, measured["scores"], predictions,
        graph, challenge_grade=challenge_grade)
    title_matches = {}
    fanout_screen = None
    proposed = epoch
    changes = decisions = ()
    for round_index in range(5):
        proposed, changes, decisions = advance_championship_epoch(
            epoch, grades=grades, challenger_exam=challenger,
            incumbent_exams=incumbents, title_matches=title_matches,
            fanout_screen=fanout_screen)
        screen_requests = [decision for decision in decisions
                           if decision["decision"] == "FANOUT_SCREEN_REQUIRED"]
        if screen_requests:
            if fanout_screen is not None or len(screen_requests) != 1:
                raise ValueError("CHAMPIONSHIP_FANOUT_SCREEN_RECURSION")
            request = screen_requests[0]
            fanout_screen = _fresh_fanout_screen(
                mx, run_dir, receipt, epoch, cohort, challenger,
                parameters, graph, request["capabilities"])
            continue
        pending = {
            decision["capability"] for decision in decisions
            if decision["decision"] in (
                "TITLE_MATCH_REQUIRED", "FANOUT_TITLE_MATCH_REQUIRED") and
            decision["capability"] not in title_matches}
        if not pending:
            return proposed, changes, decisions
        if round_index == 4:
            raise ValueError("CHAMPIONSHIP_TITLE_MATCH_RECURSION")
        for cap in sorted(pending):
            role = epoch["active_roles"][cap]
            title_matches[cap] = _fresh_title_match(
                mx, run_dir, receipt, epoch, cohort, challenger,
                parameters, graph, cap)
    raise AssertionError("unreachable")


def _advance_exam_championships(mx, run_dir, receipt, epoch, course, school,
                                cohort, measured, predictions, parameters, graph):
    """Adjudicate every measured capability grade for the intact checkpoint."""
    scores = measured["scores"]
    represented = [
        grade.id for grade in _schedule_for_receipt(run_dir, receipt, course).grades
        if any(cap.id in scores for cap in grade.capabilities)
    ]
    if not represented:
        raise ValueError("CHAMPIONSHIP_EPOCH_NO_MEASURED_TITLE_GRADE")
    updated = epoch
    changed_roles, decisions = set(), []
    for grade in represented:
        updated, changed, verdicts = _advance_exam_championship_grade(
            mx, run_dir, receipt, updated, course, school, cohort, measured,
            predictions, parameters, graph, challenge_grade=grade)
        changed_roles.update(changed)
        decisions.extend(verdicts)
    return updated, tuple(sorted(changed_roles)), tuple(decisions)


def _live_exam_factors_complete(executable_release, cohort, expected) -> bool:
    """Validate declared answer-domain coverage without knowing modality names.

    Source/construction-specific invariants belong to the registered provider
    and its independent oracle.  The generic trainer verifies only what the
    executable plan declares: exact cohort size, admitted answer kind, admitted
    gold label, and at least one observation of every declared answer value.
    """
    capability_map = executable_release.execution_plan.capability_map
    for cap, total in expected.items():
        rows = [row for row in cohort.rows if row["capability"] == cap]
        if len(rows) != total:
            return False
        families = capability_map[cap].answer_families
        family_map = {family.kind: family for family in families}
        if (not family_map or any(
                row.get("answer_kind", "binary") not in family_map or
                row["gold"] not in family_map[
                    row.get("answer_kind", "binary")].values
                for row in rows)):
            return False
        for family in families:
            observed = {
                row["gold"] for row in rows
                if row.get("answer_kind", "binary") == family.kind}
            if observed != set(family.values):
                return False
    return True


def _commit_scored_student(mx, run_dir, receipt, manifest, course, school,
                           cohort, predictions, parameters, optimizer, graph, *,
                           reserve_gib, allowed_capabilities=None):
    """Only evaluated best scores mint permanent capability candidates.

    If none improve, the single live student still needs a replaceable
    recovery point. This is NOT a champion or an additional archive slot.
    """
    executable_release = _read_executable_factory_release_artifact(
        run_dir, receipt)
    program = schedule_program_from_executable_release(executable_release)
    full_allowed = set(assessment_capabilities(program, school))
    allowed = (set(allowed_capabilities) if allowed_capabilities is not None
               else set(full_allowed))
    if not allowed or not allowed <= full_allowed:
        raise ValueError("HUMAN_TRAINER_PARTIAL_EVALUATION_SCOPE_DRIFT")
    from .factory.assessment import assessment_scope_contract
    rubric = assessment_scope_contract(
        executable_release, allowed).rubric_sha256
    known_rubrics = {
        grade.assessment_sha256 for grade in program.grades}
    live_rubric = receipt.get("live_rubric_sha256")
    if live_rubric is not None and live_rubric not in known_rubrics:
        raise ValueError("HUMAN_TRAINER_LIVE_RUBRIC_IDENTITY_DRIFT")
    expected = {
        capability.id: capability.exam_item_count
        for grade in program.grades
        for capability in grade.capabilities
        if capability.id in allowed}
    if (cohort.rubric_version != rubric or
            len(cohort.rows) != sum(expected.values())):
        raise ValueError("HUMAN_TRAINER_LIVE_RUBRIC_SCOPE_DRIFT")
    grades = score_cohort(cohort, predictions, {
        "sha256": "IN_MEMORY_CANDIDATE", "optimizer_step": int(optimizer.state["step"].item()),
        "model_and_native_adamw": True})["scores"]
    if ({cap: row["total"] for cap, row in grades.items()} != expected or
            not _live_exam_factors_complete(
                executable_release, cohort, expected)):
        raise ValueError("HUMAN_TRAINER_LIVE_EXAM_INCOMPLETE_FACTORS")
    complete_scope = allowed == full_allowed
    if complete_scope:
        replay_receipt = {**receipt, "live_rubric_sha256": rubric}
        frontier, incumbent_comparisons = _compare_incumbents(
            mx, run_dir, replay_receipt, cohort, receipt["config"],
            receipt["answer_ids"], graph)
        roles = candidate_roles(frontier, grades, rubric)
    else:
        # A quarantined capability remains mandatory graduation debt. Partial
        # ordinary scoring protects the causal student but cannot mint or move
        # championship authority from an incomplete capability inventory.
        frontier = dict(receipt.get("capability_best", {}))
        incumbent_comparisons = []
        roles = ()
    name = ("best-" if roles else "working-") + str(school.visits) + "-" + uuid.uuid4().hex[:12]
    candidate = _bundle_pointer(run_dir, name, parameters, optimizer, graph,
                                reserve_gib=reserve_gib)
    if roles:
        proof = _fingerprint({"manifest": manifest["manifest_sha256"],
                              "rubric": rubric, "cohort": cohort.digest,
                              "predictions": sorted(predictions.items()),
                              "student_sha256": candidate.sha256,
                              "optimizer_step": candidate.optimizer_step})
        frontier = promote(frontier, grades, rubric, asdict(candidate),
                           "capability-evaluation/" + proof, roles)
    return (replace(school, current_student=candidate), frontier, roles,
            incumbent_comparisons)


def _boundary_delivery_events(record, pending, roles, exam_event):
    """Freeze truthful source-scored events before publishing state.json."""
    school = record["school"]
    completed_grade = (exam_event["grade"] if exam_event is not None else
                       school["active_grades"][school["grade_index"]])
    events = []
    for provisional in pending:
        event = dict(provisional)
        event["recovered_at_student_sha256"] = school["current_student"]["sha256"]
        event["checkpoint_status"] = "RECORDED_AT_BOUNDARY"
        events.append(event)
    if roles:
        frontier = record["capability_best"]
        slots = [frontier[key] for key in sorted(frontier)
                 if frontier[key]["capability"] in roles and
                 frontier[key]["checkpoint"]["sha256"] ==
                 school["current_student"]["sha256"]]
        if ({slot["capability"] for slot in slots} != set(roles) or
                len({slot["rubric"] for slot in slots}) != 1):
            raise ValueError("HUMAN_TRAINER_CAPABILITY_BEST_RECEIPT_DRIFT")
        events.append({"event": "SCHOOL_CAPABILITY_BEST_COMMITTED",
                       "grade": completed_grade, "generation": record["generation"],
                       "capabilities": list(roles), "rubric": slots[0]["rubric"],
                       "scores": {entry["capability"]: {
                           "correct": entry["correct"], "total": entry["total"]}
                           for entry in slots},
                       "evaluation_ids": {entry["capability"]: entry["evaluation_id"]
                                          for entry in slots},
                       "student_sha256": school["current_student"]["sha256"],
                       "optimizer_step": school["current_student"]["optimizer_step"]})
    if exam_event is not None:
        # A freshly enrolled numeric staircase intentionally has no prior
        # grade examination. A stop-boundary candidate comparison is valid.
        active_soups = (record["mentor_epoch"].get("active_grade_soups", {})
                        if record.get("mentor_epoch") is not None
                        else record.get("grade_soups", {}))
        for grade in (record.get("last_exam") or {}).get("grade_soups_refreshed", ()):
            snapshot = active_soups[grade]
            for shard in soup_shards(snapshot):
                event = {
                    "event": "SCHOOL_GRADE_SOUP_FROZEN",
                    "generation": record["generation"], "grade": grade,
                    "filename": shard["filename"], "sha256": shard["sha256"],
                    "recipe_sha256": shard["recipe_sha256"],
                    "vote_count": shard["vote_count"],
                    "covered_capabilities": shard.get(
                        "covered_capabilities", shard["perfect_capabilities"]),
                    "source_champion_shas": [item["checkpoint"]["sha256"]
                                              for item in shard["members"]],
                    "frozen_source_weights_only": True,
                }
                if snapshot.get("schema") == PARTITIONED_SCHEMA:
                    event.update({
                        "logical_grade_recipe_sha256": snapshot["recipe_sha256"],
                        "logical_grade_vote_count": snapshot["vote_count"],
                        "source_graph_sha256": shard["source_graph_sha256"],
                    })
                events.append(event)
        events.append(dict(exam_event))
    return tuple(events)


def _with_delivery_outbox(record: dict, events) -> dict:
    """Commit event intent atomically with the immutable student generation."""
    if not record.get("run_id") or type(record.get("generation")) is not int:
        raise ValueError("HUMAN_TRAINER_OUTBOX_MISSING_LINEAGE")
    prepared = dict(record)
    prepared.pop("_pending_visit_events", None)
    if not events:
        raise ValueError("HUMAN_TRAINER_OUTBOX_REQUIRES_EVENT")
    outbox = []
    for index, event in enumerate(events):
        if not isinstance(event, dict) or not event.get("event") or "event_id" in event:
            raise ValueError("HUMAN_TRAINER_OUTBOX_UNTRUSTED_EVENT")
        copy = json.loads(_canonical(event))
        copy["event_id"] = _fingerprint(["school-generation-event/v1",
                                         record["run_id"], record["generation"],
                                         index, copy])
        outbox.append(copy)
    prepared["delivery_outbox"] = outbox
    return prepared


def _reconcile_delivery_outbox(run_dir: Path, record: dict):
    """Replay missing events; never duplicate or amend prior ledger history.

    Caller must hold the exclusive operator lock. JSONL write+fsync can succeed
    even if the process dies before acknowledging it, so dedupe by the exact
    immutable generation event ID *and* payload rather than a stale boolean.
    """
    outbox = record.get("delivery_outbox")
    if outbox is None:
        return False
    if not isinstance(outbox, list) or not outbox:
        raise ValueError("HUMAN_TRAINER_OUTBOX_INVALID")
    expected = {}
    for index, event in enumerate(outbox):
        if not isinstance(event, dict) or "event_id" not in event:
            raise ValueError("HUMAN_TRAINER_OUTBOX_EVENT_ID_MISSING")
        payload = {k:v for k,v in event.items() if k != "event_id"}
        identity = _fingerprint(["school-generation-event/v1", record["run_id"],
                                 record["generation"], index, payload])
        if event["event_id"] != identity or identity in expected:
            raise ValueError("HUMAN_TRAINER_OUTBOX_LINEAGE_DRIFT")
        expected[identity] = event
    observed = set()
    journal = run_dir / "events.jsonl"
    if journal.exists():
        if journal.is_symlink() or not journal.is_file():
            raise ValueError("HUMAN_TRAINER_OUTBOX_UNSAFE_LEDGER")
        with journal.open(encoding="utf-8") as stream:
            for line in stream:
                item = json.loads(line)
                identity = item.get("event_id")
                if identity in expected:
                    if item != expected[identity]:
                        raise ValueError("HUMAN_TRAINER_OUTBOX_LEDGER_CONTENT_DRIFT")
                    observed.add(identity)
    for event in outbox:
        if event["event_id"] not in observed:
            _record(run_dir, event)
    return True


def _publish_boundary(run_dir, record, pending, roles, *, exam_event=None):
    """Publish visits only after model and teacher are durably recoverable."""
    student_school = record["school"]
    # The scheduler may have moved B -> A for cumulative revalidation before
    # this grade-B examination's capability winners are published. Preserve
    # the *completed assessment grade* instead of the next scheduled grade.
    active_grade = (exam_event["grade"] if exam_event is not None else
                    student_school["active_grades"][student_school["grade_index"]])
    if record.get("delivery_outbox") is not None:
        if pending or roles or exam_event is not None:
            expect = _with_delivery_outbox(
                record, _boundary_delivery_events(record, pending, roles, exam_event))
            if expect["delivery_outbox"] != record["delivery_outbox"]:
                raise ValueError("HUMAN_TRAINER_OUTBOX_BOUNDARY_ARGUMENT_DRIFT")
        _reconcile_delivery_outbox(run_dir, record)
    else:
        # Old Grade A states predate immutable event publication. Keep their
        # established behavior and their source receipts byte-for-byte.
        for event in _boundary_delivery_events(record, pending, roles, exam_event):
            _record(run_dir, event)
    school = student_school
    retained = pinned(record.get("capability_best", {}), school["current_student"],
                      school["champions"])
    if record.get('curriculum_parent'):
        retained |= pinned({}, record['curriculum_parent'], {})
    for peak in record.get("whole_student_peaks", ()):
        retained |= pinned({}, peak["checkpoint"], {})
    for source in _mentor_epoch_references(record):
        retained |= pinned({}, source, {})
    retained |= pinned(record.get("graduation_perfect", {}),
                       school["current_student"], school["champions"])
    for item in record.get("historical_grade_champions", {}).values():
        retained |= pinned({}, item, {})
    if record.get("legacy_frontier_pending_replay"):
        retained |= pinned(record.get("historical_capability_best", {}),
                           school["current_student"], school["champions"])
    _quarantine_newer_uncommitted_bundles(run_dir, retained,
                                          school["current_student"]["optimizer_step"])
    removed = retire_bundles(run_dir, retained)
    if removed:
        _record(run_dir, {"event": "SCHOOL_CHECKPOINTS_RETIRED", "grade": active_grade,
                          "generation": record["generation"],
                          "count": len(removed), "protected_count": len(retained)})
    # The old frozen recipes are unique experiment evidence, not debris.
    # Do not delete either historical or new-epoch soup bytes from this fork.
    retired_soups = (retire_stale_soups(run_dir, record.get("grade_soups", {}))
                     if record.get("mentor_epoch") is None else ())
    if retired_soups:
        _record(run_dir, {"event": "SCHOOL_OLD_GRADE_SOUPS_RETIRED",
                          "generation": record["generation"],
                          "grade": active_grade, "count": len(retired_soups)})


def _quarantine_newer_uncommitted_bundles(run_dir: Path, retained: set[str],
                                          current_optimizer_step: int) -> tuple[str, ...]:
    """Never prune a post-update model published before its pointer crashed."""
    root = run_dir / "bundles"
    if not root.exists():
        return ()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("HUMAN_TRAINER_UNCOMMITTED_BUNDLE_UNSAFE_PATH")
    quarantined = []
    for candidate in sorted(root.iterdir()):
        if candidate.name == ".DS_Store" and not candidate.is_symlink() and candidate.is_file():
            # Keep Finder's bookkeeping from aborting an otherwise valid
            # human-run checkpoint transaction. Never touch model files.
            candidate.unlink()
            continue
        relative = "bundles/" + candidate.name
        if relative in retained:
            continue
        if candidate.is_symlink() or not candidate.is_dir():
            raise ValueError("HUMAN_TRAINER_UNCOMMITTED_BUNDLE_UNSAFE_PATH")
        weights, own_adamw, metadata, graph = load_semantically_bound_bundle(candidate)
        if (metadata["source_digest"] != AUDITED_PARENT.sha256 or
                metadata["optimizer_step"] < 0):
            raise ValueError("HUMAN_TRAINER_UNCOMMITTED_BUNDLE_SOURCE_DRIFT")
        del weights, own_adamw, graph
        if metadata["optimizer_step"] <= current_optimizer_step:
            continue
        target_parent = run_dir / ".bundle-quarantine"
        if target_parent.is_symlink() or (target_parent.exists() and
                                          not target_parent.is_dir()):
            raise ValueError("HUMAN_TRAINER_UNSAFE_BUNDLE_QUARANTINE")
        target_parent.mkdir(exist_ok=True)
        target = target_parent / candidate.name
        if target.exists() or target.is_symlink():
            raise ValueError("HUMAN_TRAINER_QUARANTINE_IDENTITY_COLLISION")
        candidate.rename(target)
        quarantined.append(candidate.name)
        fd = os.open(target_parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        _record(run_dir, {"event": "SCHOOL_NEWER_UNCOMMITTED_BUNDLE_QUARANTINED",
                          "grade": "A", "filename": str(target.relative_to(run_dir)),
                          "optimizer_step": metadata["optimizer_step"],
                          "student_sha256": metadata["safetensors_sha256"],
                          "prior_committed_optimizer_step": current_optimizer_step})
    return tuple(quarantined)


def _resume_command(run_dir: Path, source_root: Path,
                    learning_settings: LearningSettings | None,
                    boolean_association_bridge: bool = False,
                    source_prefetch_workers: int = 2,
                    autonomous_curriculum: bool = False) -> str:
    """Only name non-default options in the next human-owned shell command."""
    from .paths import LEGACY_SOURCE, active_run_dir

    command = "npm run train -- --human-run --resume"
    if learning_settings is None:
        command += " --no-retention"
    elif learning_settings != LearningSettings():
        command += (
            " --retention-probe-each " + str(learning_settings.probe_each) +
            " --retention-mature-max-loss " + str(learning_settings.mature_max_loss) +
            " --retention-introduction-extra-loss " +
                str(learning_settings.introduction_extra_loss) +
            " --retention-protected-cap-limit " +
                str(learning_settings.protected_cap_limit))
    if learning_settings is None or Path(run_dir).resolve() != active_run_dir().resolve():
        command += " --run-dir " + shlex.quote(str(run_dir))
    if Path(source_root).resolve() != LEGACY_SOURCE.resolve():
        command += " --legacy-code-root " + shlex.quote(str(source_root))
    if boolean_association_bridge:
        command += " --boolean-association-bridge"
    if autonomous_curriculum:
        command += " --autonomous-curriculum"
    if source_prefetch_workers != 2:
        command += " --source-prefetch-workers " + str(source_prefetch_workers)
    return command


def _school_result_label(school):
    return (("GRADE_" + school.grade + "_MASTERED_AWAITING_NEXT_GRADE")
            if school.stage == "AWAITING_NEXT_GRADE" else
            ("GRADE_" + school.revalidation_target_grade +
             "_REVALIDATING_" + school.grade)
            if school.revalidation_target_grade else
            "ACTIVE_GRADE_" + school.grade)


def _promotion_due_after_routine(before, after) -> bool:
    """Whether a perfect routine evaluation would advance the school state.

    Passing an intermediate introduction tranche is not graduation. Moving to
    another grade, beginning/advancing a cumulative revalidation sweep, or
    reaching a curriculum boundary is.
    """
    return (
        after.grade != before.grade
        or after.revalidation_target_grade != before.revalidation_target_grade
        or after.stage in {
            "AWAITING_NEXT_GRADE", "AWAITING_TEACHER_SOUP",
            "WHOLE_SCHOOL_MASTERED",
        }
    )


def _assessment_scope_sha256(full_scope, scores) -> str:
    """Bind an assessment scope to the capabilities actually represented."""
    score_ids = set(scores)
    selected = tuple(cap for cap in full_scope if cap in score_ids)
    if not selected or set(selected) != score_ids:
        raise ValueError("HUMAN_TRAINER_EXAM_SCORE_SCOPE_DRIFT")
    return _fingerprint(selected)


def _measure_debt_admission_boundary(mx, run_dir, receipt, manifest, course,
                                     source_root, parameters, graph):
    """Measure the exact complete admitted plan before explicit debt admission."""
    release = _require_executable_factory_admission(run_dir, receipt, graph)
    program = schedule_program_from_executable_release(release)
    school = _state_from_json(receipt["school"], program)
    full_scope = tuple(cap.capability_id for cap in release.execution_plan.capabilities)
    cohort, pointer = _routine_executable_cohort(
        run_dir, receipt, manifest, release, live_source_registry(),
        source_root, graph, capabilities=full_scope,
        assessment_epoch=school.grade_exam_epoch, legacy_course=course)
    guesses = _predictions(
        mx, parameters, list(cohort.rows), receipt["config"], receipt["answer_ids"])
    measured = score_cohort(cohort, guesses, asdict(school.current_student))
    return {**receipt, "debt_admission_boundary_exam": {
        **pointer,
        "schema": "bilqis.mlx.debt-admission-boundary/v2",
        "student_sha256": school.current_student.sha256,
        "optimizer_step": school.current_student.optimizer_step,
        "exam_rubric_sha256": pointer["rubric_sha256"],
        "assessment_scope_sha256": _fingerprint(full_scope),
        "source_exam_plane": "DEBT_ADMISSION_BOUNDARY",
        "scores": measured["scores"],
        "misses_for_teacher": list(measured["misses_for_teacher"]),
    }}


def _take_exam(mx, run_dir, receipt, manifest, course, source_root,
               source_checkpoint, parameters, optimizer, graph, *, reserve_gib,
               scheduler_only: bool = False):
    executable_release = _read_executable_factory_release_artifact(
        run_dir, receipt)
    program = schedule_program_from_executable_release(executable_release)
    school = _state_from_json(receipt["school"], program)
    if not school.stage.startswith("ASSESS_"):
        raise ValueError("HUMAN_TRAINER_EXAM_OUTSIDE_SCHEDULED_BOUNDARY")
    if (receipt.get("championship_school_identity") !=
            _live_championship_identity(receipt, course, graph, parameters)):
        raise ValueError("CHAMPIONSHIP_SCHOOL_IDENTITY_RESET_REQUIRED")
    stagnation = receipt.get("stagnation_session")
    blocked_before = quarantined_capabilities(stagnation)
    full_scope = assessment_capabilities(program, school)
    active_scope = tuple(cap for cap in full_scope if cap not in set(blocked_before))
    _require_active_stagnation_scope(active_scope)
    parent_checkpoint = school.current_student
    source_registry = live_source_registry()
    routine_cohort, routine_pointer = _routine_executable_cohort(
        run_dir, receipt, manifest, executable_release, source_registry,
        source_root, graph, capabilities=active_scope,
        assessment_epoch=school.grade_exam_epoch, legacy_course=course)
    routine_file = routine_pointer["cohort_file"]
    rubric = routine_pointer["rubric_sha256"]
    generator = routine_cohort.generator_version
    routine_rows = list(routine_cohort.rows)
    routine_scope_sha = _assessment_scope_sha256(
        full_scope, {cap: None for cap in active_scope})
    candidate_cohort = None
    candidate_measured = None
    frontier = dict(receipt.get("capability_best", {}))
    roles = ()
    compared = []
    if scheduler_only:
        if int(optimizer.state["step"].item()) != school.current_student.optimizer_step:
            raise ValueError("FLASH_SCHEDULER_EXAM_REQUIRES_CHECKPOINTED_STUDENT")
    else:
        candidate_cohort, _ = _candidate_executable_cohort(
            run_dir, receipt, manifest, executable_release, source_registry,
            source_root, graph, capabilities=active_scope,
            legacy_course=course)
        candidate_guesses = _predictions(
            mx, parameters, list(candidate_cohort.rows),
            receipt["config"], receipt["answer_ids"])
        school, frontier, roles, compared = _commit_scored_student(
            mx, run_dir, receipt, manifest, course, school,
            candidate_cohort, candidate_guesses,
            parameters, optimizer, graph, reserve_gib=reserve_gib,
            allowed_capabilities=active_scope)
        receipt = _bind_checkpoint_origin(receipt, school.current_student)
        candidate_measured = score_cohort(
            candidate_cohort, candidate_guesses, asdict(school.current_student))

    routine_guesses = _predictions(
        mx, parameters, routine_rows, receipt["config"], receipt["answer_ids"])
    routine_measured = score_cohort(
        routine_cohort, routine_guesses, asdict(school.current_student))
    championship_exams = ([] if scheduler_only else [
        (candidate_cohort, candidate_measured, candidate_guesses),
        (routine_cohort, routine_measured, routine_guesses)])
    parent_routine_scores, parent_routine_issue = _score_parent_for_paired_s3(
        mx, run_dir, receipt, parent_checkpoint, routine_cohort, graph,
        routine_measured["scores"])
    routine_assessment = Assessment(
        checkpoint_sha256=school.current_student.sha256,
        optimizer_step=school.current_student.optimizer_step,
        course_digest=program.digest(),
        rubric_digest=rubric,
        scores={cap: Score(**entry)
                for cap, entry in routine_measured["scores"].items()},
        evaluation_id="source-oracled-routine-cohort/" + routine_cohort.digest + "/" +
                      school.current_student.sha256)
    routine_advanced = (
        assess_withheld(program, school, routine_assessment, blocked_before)
        if blocked_before else
        assess_flash(program, school, routine_assessment)
        if scheduler_only else
        assess(program, school, routine_assessment))

    routine_last_exam = {
        "assessment_grade": school.grade,
        "grade_exam_epoch": school.grade_exam_epoch,
        "exam_plane": "ROUTINE",
        "grade_test_lifecycle": ROUTINE_EVAL_LIFECYCLE,
        "assessment_scope_sha256": routine_scope_sha,
        "evaluation_id": routine_assessment.evaluation_id,
        "exam_rubric_sha256": routine_assessment.rubric_digest,
        "cohort_sha256": routine_cohort.digest,
        "cohort_file": routine_file,
        "cohort_seed": routine_cohort.seed,
        "generator_version": generator,
        "misses_for_teacher": list(routine_measured["misses_for_teacher"]),
        "student_sha256": routine_assessment.checkpoint_sha256,
        "optimizer_step": routine_assessment.optimizer_step,
        "scores": routine_measured["scores"],
    }
    routine_warnings = summarize_completed_exam_safely(
        run_dir, receipt, routine_last_exam)
    routine_warnings = apply_paired_checkpoint_s3(
        routine_warnings,
        parent_scores=parent_routine_scores,
        current_scores=routine_measured["scores"],
        parent_sha256=parent_checkpoint.sha256,
        current_sha256=school.current_student.sha256,
        parent_step=parent_checkpoint.optimizer_step,
        current_step=school.current_student.optimizer_step,
        cohort_sha256=routine_cohort.digest,
        unavailable_reason=parent_routine_issue)
    quarantine_suppressed = grace_suppressed_capabilities(
        receipt.get("stagnation_grace"), required_capabilities=full_scope,
        optimizer_step=routine_assessment.optimizer_step)
    stagnation, stagnation_events, routine_advanced, blocked_after = (
        _advance_stagnation_after_routine(
            program=program,
            school=school,
            routine_assessment=routine_assessment,
            routine_advanced=routine_advanced,
            stagnation=stagnation, blocked_before=blocked_before,
            active_scope=active_scope, routine_measured=routine_measured,
            routine_warnings=routine_warnings,
            generation=receipt["generation"] + 1,
            quarantine_suppressed=quarantine_suppressed))

    qualification = None
    generalization = None
    generalization_passed = False
    burned_generalization = list(
        receipt.get("burned_generalization_cohorts_v2", ()))
    exam_plane = "ROUTINE"
    cohort = routine_cohort
    cohort_pointer = routine_pointer
    cohort_file = routine_file
    rows = routine_rows
    guesses = routine_guesses
    measured = routine_measured
    assessment = routine_assessment
    advanced = routine_advanced
    if not scheduler_only and _promotion_due_after_routine(school, routine_advanced):
        promotion_cohort, qualification = _promotion_executable_cohort(
            run_dir, receipt, manifest, executable_release, source_registry,
            source_root, graph, capabilities=active_scope,
            assessment_epoch=school.grade_exam_epoch, legacy_course=course)
        promotion_file = qualification["cohort_file"]
        promotion_rows = list(promotion_cohort.rows)
        promotion_guesses = _predictions(
            mx, parameters, promotion_rows,
            receipt["config"], receipt["answer_ids"])
        promotion_measured = score_cohort(
            promotion_cohort, promotion_guesses, asdict(school.current_student))
        championship_exams.append((promotion_cohort, promotion_measured, promotion_guesses))
        promotion_assessment = Assessment(
            checkpoint_sha256=school.current_student.sha256,
            optimizer_step=school.current_student.optimizer_step,
            course_digest=program.digest(),
            rubric_digest=rubric,
            scores={cap: Score(**entry)
                    for cap, entry in promotion_measured["scores"].items()},
            evaluation_id="source-oracled-promotion-cohort/" +
                          promotion_cohort.digest + "/" +
                          school.current_student.sha256)
        exam_plane = "PROMOTION"
        cohort = promotion_cohort
        cohort_pointer = qualification
        cohort_file = promotion_file
        rows = promotion_rows
        guesses = promotion_guesses
        measured = promotion_measured
        assessment = promotion_assessment
        promotion_advanced = assess(program, school, promotion_assessment)
        advanced = promotion_advanced
        if _promotion_due_after_routine(school, promotion_advanced):
            promotion_evidence = LearningEvidence(
                AssessmentClass.PROMOTION,
                promotion_cohort.digest,
                promotion_assessment.checkpoint_sha256,
                promotion_assessment.optimizer_step,
                True,
            )
            generalization_cohort, generalization = (
                _generalization_executable_cohort(
                    run_dir, receipt, manifest, executable_release,
                    source_registry, source_root, graph,
                    capabilities=active_scope,
                    assessment_epoch=school.grade_exam_epoch,
                    promotion_pointer=qualification,
                    exposed_specimen_ids=tuple(
                        row["id"] for row in routine_cohort.rows),
                    legacy_course=course))
            generalization_file = generalization["cohort_file"]
            generalization_rows = list(generalization_cohort.rows)
            generalization_guesses = _predictions(
                mx, parameters, generalization_rows,
                receipt["config"], receipt["answer_ids"])
            generalization_measured = score_cohort(
                generalization_cohort, generalization_guesses,
                asdict(school.current_student))
            championship_exams.append((generalization_cohort, generalization_measured,
                                        generalization_guesses))
            generalization_assessment = Assessment(
                checkpoint_sha256=school.current_student.sha256,
                optimizer_step=school.current_student.optimizer_step,
                course_digest=program.digest(),
                rubric_digest=rubric,
                scores={cap: Score(**entry)
                        for cap, entry in generalization_measured["scores"].items()},
                evaluation_id="source-oracled-generalization-cohort/" +
                              generalization_cohort.digest + "/" +
                              school.current_student.sha256)
            exam_plane = "GENERALIZATION"
            cohort = generalization_cohort
            cohort_pointer = generalization
            cohort_file = generalization_file
            rows = generalization_rows
            guesses = generalization_guesses
            measured = generalization_measured
            assessment = generalization_assessment
            advanced = assess(program, school, generalization_assessment)
            generalization_evidence = LearningEvidence(
                AssessmentClass.GENERALIZATION,
                generalization_cohort.digest,
                generalization_assessment.checkpoint_sha256,
                generalization_assessment.optimizer_step,
                _promotion_due_after_routine(school, advanced),
            )
            generalization_passed = qualification_complete(
                promotion_evidence, generalization_evidence)
            burned_generalization.append(generalization)

    scores = {k: {"correct": v.correct, "total": v.total}
              for k, v in assessment.scores.items()}
    final_scope_sha = _assessment_scope_sha256(full_scope, scores)
    epoch = receipt.get("mentor_epoch")
    championship_decisions = ()
    graduation_roles = ()
    championship_roles = ()
    if epoch is None and not scheduler_only:
        epoch = begin_initial_epoch(
            student=asdict(school.current_student), introduced_grade=school.grade,
            source_graph_sha256=_fingerprint(graph),
            frontier=receipt.get("graduation_perfect", {}),
            soups=receipt.get("grade_soups", {}))
        epoch["settled_matchups"] = {}
        epoch["championship_school_identity"] = receipt["championship_school_identity"]
    if scheduler_only:
        perfect = receipt.get("graduation_perfect", {})
        frozen_soups = receipt.get("grade_soups", {})
        soup_changes = ()
    else:
        epoch = _hydrate_championship_witnesses(mx, run_dir, receipt, epoch, graph)
        changed_roles, decisions = set(), []
        for examined, result, predicted in championship_exams:
            epoch, changed, verdicts = _advance_exam_championships(
                mx, run_dir, receipt, epoch, course, school,
                examined, result, predicted, parameters, graph)
            changed_roles.update(changed)
            decisions.extend(verdicts)
        championship_roles = tuple(sorted(changed_roles))
        championship_decisions = tuple(decisions)
        new_soups, soup_changes = _cook_new_grade_soups(
            mx, run_dir, receipt, epoch_active_frontier(epoch), course, graph,
            existing=epoch.get("active_grade_soups", {}), reserve_gib=reserve_gib)
        epoch["active_grade_soups"] = new_soups
        # Keep all original champion/grade-soup evidence immutable in the
        # archival state fields. Only the epoch earns new active roles.
        perfect = receipt.get("graduation_perfect", {})
        frozen_soups = receipt.get("grade_soups", {})
    last_exam = {
        "assessment_grade": school.grade,
        "grade_exam_epoch": school.grade_exam_epoch,
        "exam_plane": exam_plane,
        "grade_test_lifecycle": (
            GENERALIZATION_LIFECYCLE if generalization is not None else
            PROMOTION_ATTEMPT_LIFECYCLE if qualification is not None else
            ROUTINE_EVAL_LIFECYCLE),
        "assessment_scope_sha256": final_scope_sha,
        "evaluation_id": assessment.evaluation_id,
        "exam_rubric_sha256": assessment.rubric_digest,
        "cohort_sha256": cohort.digest,
        "cohort_file": cohort_file,
        "cohort_seed": cohort.seed,
        "factory_release_sha256": cohort_pointer["factory_release_sha256"],
        "capabilities": list(cohort_pointer["capabilities"]),
        "rubric_sha256": cohort_pointer["rubric_sha256"],
        "source_sha256": cohort_pointer["source_sha256"],
        "routine_cohort_sha256": routine_cohort.digest,
        "routine_cohort_file": routine_file,
        "routine_cohort_seed": routine_cohort.seed,
        "routine_scores": routine_measured["scores"],
        "graduation_perfect_roles": list(graduation_roles),
        "championship_roles": list(championship_roles),
        "grade_soups_refreshed": list(soup_changes),
        "championship_decisions": list(championship_decisions),
        "generator_version": generator,
        "incumbent_comparisons": compared,
        "misses_for_teacher": list(measured["misses_for_teacher"]),
        "student_sha256": assessment.checkpoint_sha256,
        "optimizer_step": assessment.optimizer_step,
        "scores": scores,
        "withheld_capabilities": list(blocked_before),
        "stagnation_quarantined": list(blocked_after),
        "routine_learning_diagnostics": routine_warnings,
        "flash_scheduler_only": scheduler_only,
    }
    if candidate_cohort is not None:
        last_exam["candidate_cohort_sha256"] = candidate_cohort.digest
    if qualification is not None:
        last_exam["promotion_cohort_sha256"] = qualification["cohort_sha256"]
    if generalization is not None:
        last_exam["generalization_cohort_sha256"] = generalization["cohort_sha256"]
        last_exam["generalization_passed"] = generalization_passed
    peaks, retention_status = advance_peaks(
        receipt.get("whole_student_peaks", []),
        curriculum_mode=receipt["curriculum_mode"],
        numeric_maximum=receipt.get("numeric_maximum"),
        rubric_sha256=assessment.rubric_digest,
        cohort_sha256=cohort.digest,
        assessment_scope_sha256=last_exam["assessment_scope_sha256"],
        scores=scores, checkpoint=asdict(school.current_student))
    last_exam["whole_student_retention"] = retention_status
    pending = (*receipt.get("_pending_visit_events", ()), *stagnation_events)
    exam_warnings = summarize_completed_exam_safely(run_dir, receipt, last_exam)
    if cohort.digest == routine_cohort.digest:
        paired_parent_scores = parent_routine_scores
        paired_parent_issue = parent_routine_issue
    else:
        paired_parent_scores, paired_parent_issue = _score_parent_for_paired_s3(
            mx, run_dir, receipt, parent_checkpoint, cohort, graph, scores)
    exam_warnings = apply_paired_checkpoint_s3(
        exam_warnings,
        parent_scores=paired_parent_scores,
        current_scores=scores,
        parent_sha256=parent_checkpoint.sha256,
        current_sha256=school.current_student.sha256,
        parent_step=parent_checkpoint.optimizer_step,
        current_step=school.current_student.optimizer_step,
        cohort_sha256=cohort.digest,
        unavailable_reason=paired_parent_issue)
    last_exam["learning_diagnostics"] = exam_warnings
    teacher_outcomes = summarize_teacher_outcomes(receipt.get("last_exam"), last_exam, pending)
    last_exam["teacher_outcomes"] = teacher_outcomes
    # Exam golds become eligible *after* the complete examination. Retain
    # tokens and source provenance so the next weakest-three visits can train
    # directly on missed semantics, with no answer leakage during scoring.
    priority = reconcile_unresolved_misses(
        receipt.get("teacher_misses", ()), rows, guesses)
    if blocked_after:
        blocked_set = set(blocked_after)
        priority = [row for row in priority if row["capability"] not in blocked_set]
    unresolved_ids = {row["id"] for row in priority}
    miss_exposures = {
        identity: count for identity, count in
        receipt.get("teacher_miss_exposures", {}).items()
        if identity in unresolved_ids and type(count) is int and count >= 0
    }
    for identity in unresolved_ids:
        miss_exposures.setdefault(identity, 0)
    migrated_receipt = {**receipt, "teacher_misses": priority,
                        "whole_student_peaks": peaks,
                        "graduation_perfect": perfect,
                        "grade_soups": frozen_soups,
                        "teacher_miss_exposures": miss_exposures,
                        "legacy_frontier_pending_replay": False,
                        "live_rubric_sha256": assessment.rubric_digest}
    if stagnation is not None:
        migrated_receipt["stagnation_session"] = stagnation
    if qualification is not None and not generalization_passed:
        # A failed fixed promotion cohort remains the same classroom criterion,
        # including while fresh-generalization misses are taught afterward.
        migrated_receipt["qualification_cohort_v2"] = qualification
        migrated_receipt.pop("qualification_cohort", None)
    elif generalization_passed:
        migrated_receipt.pop("qualification_cohort_v2", None)
        migrated_receipt.pop("qualification_cohort", None)
    if burned_generalization:
        migrated_receipt["burned_generalization_cohorts_v2"] = burned_generalization
        migrated_receipt.pop("burned_generalization_cohorts", None)
    if generalization is not None:
        migrated_receipt["last_generalization_cohort_v2"] = generalization
        migrated_receipt.pop("last_generalization_cohort", None)
    if epoch is not None:
        migrated_receipt["mentor_epoch"] = epoch
    migrated_receipt.pop("teacher_miss_cursor", None)
    result = _advance(
        run_dir, migrated_receipt, advanced, frontier=frontier,
        model_bundle=school.current_student.filename, last_exam=last_exam,
        result=_school_result_label(advanced), persist=False)
    exam_event = {
        "event": ("SCHOOL_FLASH_ROUTINE_EXAM_COMMITTED" if scheduler_only
                  else "SCHOOL_LIVE_EXAM_COMMITTED"),
        "grade": school.grade, "generation": result["generation"],
        "grade_exam_epoch": school.grade_exam_epoch,
        "exam_plane": exam_plane,
        "grade_test_lifecycle": last_exam["grade_test_lifecycle"],
        "assessment_scope_sha256": last_exam["assessment_scope_sha256"],
        "introduction_stage": school.introduction_stage,
        "scores": scores, "phase": advanced.stage,
        "student_sha256": assessment.checkpoint_sha256,
        "optimizer_step": assessment.optimizer_step,
        "rubric": assessment.rubric_digest,
        "cohort_sha256": cohort.digest, "generator_version": generator,
        "cohort_seed": cohort.seed, "cohort_file": last_exam["cohort_file"],
        "routine_cohort_sha256": routine_cohort.digest,
        "incumbent_comparisons": compared,
        "teacher_miss_count": len(priority),
        "learning_diagnostics": exam_warnings,
        "teacher_outcomes": teacher_outcomes,
        "whole_student_retention": retention_status,
        "flash_scheduler_only": scheduler_only,
        "withheld_capabilities": list(blocked_before),
        "qualification_authority_changed": False if scheduler_only else None,
        "champions_changed": False if scheduler_only else None,
    }
    if qualification is not None:
        exam_event["qualification_cohort_sha256"] = qualification["cohort_sha256"]
    if epoch is not None:
        exam_event["championship_epoch"] = {
            "baseline_sha256": epoch["baseline"]["sha256"],
            "earned_roles": [] if scheduler_only else list(championship_roles),
            "active_role_count": len(epoch.get("active_roles", {})),
            "active_soup_grades": sorted(epoch.get("active_grade_soups", {})),
            "cross_origin_decisions": [] if scheduler_only else list(championship_decisions),
        }
    result = _persist(run_dir, _with_delivery_outbox(
        result, _boundary_delivery_events(result, pending, roles, exam_event)))
    _publish_boundary(run_dir, result, pending, roles, exam_event=exam_event)
    return result


def _flush_working_student(mx, run_dir, receipt, manifest, course, parameters,
                           optimizer, graph, *, reserve_gib, source_root):
    """Protect an unfinished grade cycle when the human stops mid-cycle."""
    pending = receipt.get("_pending_visit_events", ())
    if not pending:
        return receipt
    executable_release = _read_executable_factory_release_artifact(
        run_dir, receipt)
    program = schedule_program_from_executable_release(executable_release)
    school = _state_from_json(receipt["school"], program)
    stagnation = receipt.get("stagnation_session")
    blocked = quarantined_capabilities(stagnation)
    active_scope = tuple(
        cap for cap in assessment_capabilities(program, school)
        if cap not in set(blocked))
    if not active_scope:
        raise ValueError("STAGNATION_STOP_EVALUATION_HAS_NO_ACTIVE_CAPABILITIES")
    source_registry = live_source_registry()
    exam_cohort, _ = _routine_executable_cohort(
        run_dir, receipt, manifest, executable_release, source_registry,
        source_root, graph, capabilities=active_scope,
        assessment_epoch=school.grade_exam_epoch, legacy_course=course)
    cohort, _ = _candidate_executable_cohort(
        run_dir, receipt, manifest, executable_release, source_registry,
        source_root, graph, capabilities=active_scope, legacy_course=course)
    rubric = cohort.rubric_version
    generator = cohort.generator_version
    rows = list(cohort.rows)
    guesses = _predictions(mx, parameters, rows, receipt["config"], receipt["answer_ids"])
    current, frontier, roles, compared = _commit_scored_student(
        mx, run_dir, receipt, manifest, course, school, cohort, guesses,
        parameters, optimizer, graph, reserve_gib=reserve_gib,
        allowed_capabilities=active_scope)
    # The operator may stop between scheduled full exams. Score one fresh
    # routine cohort at this durable stop boundary; this records a recoverable
    # peak without creating or extending a promotion attempt.
    exam_guesses = _predictions(
        mx, parameters, list(exam_cohort.rows), receipt["config"], receipt["answer_ids"])
    exam_scores = score_cohort(exam_cohort, exam_guesses,
                               asdict(current.current_student))["scores"]
    peaks, retention_status = advance_peaks(
        receipt.get("whole_student_peaks", []),
        curriculum_mode=receipt["curriculum_mode"],
        numeric_maximum=receipt.get("numeric_maximum"),
        rubric_sha256=rubric, cohort_sha256=exam_cohort.digest,
        assessment_scope_sha256=_fingerprint(active_scope),
        scores=exam_scores, checkpoint=asdict(current.current_student))
    stop_receipt = {**receipt, "legacy_frontier_pending_replay": False,
                    "whole_student_peaks": peaks,
                    "live_rubric_sha256": rubric}
    stop_receipt = _bind_checkpoint_origin(stop_receipt, current.current_student)
    record = _advance(run_dir, stop_receipt,
                      current, frontier=frontier,
                      model_bundle=current.current_student.filename, persist=False)
    comparison_event = {
        "event": "SCHOOL_LIVE_CANDIDATE_COMPARED", "grade": school.grade,
        "generation": record["generation"],
        "rubric": rubric,
        "cohort_sha256": cohort.digest, "generator_version": generator,
        "scores": score_cohort(cohort, guesses,
            asdict(current.current_student))["scores"],
        "student_sha256": current.current_student.sha256,
        "optimizer_step": current.current_student.optimizer_step,
        "incumbent_comparisons": compared,
        "stagnation_quarantined": list(blocked)}
    comparison_event["whole_student_retention"] = retention_status
    record = _persist(run_dir, _with_delivery_outbox(
        record, _boundary_delivery_events(record, pending, roles, comparison_event)))
    _publish_boundary(run_dir, record, pending, roles, exam_event=comparison_event)
    return record


def _flush_flash_student(run_dir, receipt, course, parameters, optimizer, graph,
                         *, reserve_gib):
    """Persist the causal student without performing qualification work."""
    pending = tuple(receipt.get("_pending_visit_events", ()))
    if not pending:
        return receipt
    school = _state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
    due = require_assessment_after_flash(_schedule_for_receipt(run_dir, receipt, course), school)
    optimizer_step = int(optimizer.state["step"].item())
    if optimizer_step == school.current_student.optimizer_step:
        candidate = school.current_student
    else:
        name = "flash-working-" + str(school.visits) + "-" + uuid.uuid4().hex[:12]
        candidate = _bundle_pointer(
            run_dir, name, parameters, optimizer, graph, reserve_gib=reserve_gib)
    due = replace(due, current_student=candidate)
    receipt = _bind_checkpoint_origin(receipt, candidate)
    record = _advance(
        run_dir, receipt, due, model_bundle=candidate.filename,
        result=_school_result_label(due), persist=False)
    flash_event = {
        "event": "SCHOOL_FLASH_CHECKPOINT_COMMITTED",
        "grade": due.grade,
        "generation": record["generation"],
        "optimizer_step": candidate.optimizer_step,
        "student_sha256": candidate.sha256,
        "phase": due.stage,
        "assessment_deferred": True,
        "qualification_authority_changed": False,
        "champions_changed": False,
        "pending_visit_count": len(pending),
    }
    boundary_pending = (*pending, flash_event)
    record = _persist(run_dir, _with_delivery_outbox(
        record, _boundary_delivery_events(record, boundary_pending, (), None)))
    _publish_boundary(run_dir, record, boundary_pending, (), exam_event=None)
    return record


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


def operate(run_dir: Path, source_root: Path, source_checkpoint: Path,
            manifest_path: Path, *, resume: bool = False, minutes: int = 90,
            max_visits: int = 0, steps_per_visit: int = 16,
            batch_size: int = 32, reserve_gib: float = 100.,
            numeric_staircase: bool = False,
            boolean_composite: bool = False,
            boolean_idboolops: bool = False,
            full_grade_b: bool = False,
            retention_enabled: bool = True,
            experiment_probe_each: int = 6,
            experiment_mature_max_loss: int = 1,
            experiment_introduction_extra_loss: int = 2,
            experiment_protected_cap_limit: int = 8,
            stagnation_grace_grade: str | None = None,
            stagnation_grace_steps: int = 0,
            admit_next_grade_with_debt: bool = False,
            source_prefetch_workers: int = 2,
            flash_mode: bool = False,
            boolean_association_bridge: bool = False,
            autonomous_curriculum: bool = False,
            experiment_budget_guard=None) -> dict:
    """ENTRYPOINT FOR THE HUMAN'S SHELL ONLY. Never call in agent tests."""
    trace_mark(
        "OPERATE_START", resume=resume, max_visits=max_visits,
        steps_per_visit=steps_per_visit, batch_size=batch_size,
        source_prefetch_workers=source_prefetch_workers,
        flash_mode=flash_mode,
        boolean_association_bridge=boolean_association_bridge,
        autonomous_curriculum=autonomous_curriculum,
        boolean_composite=boolean_composite,
        boolean_idboolops=boolean_idboolops,
        admit_next_grade_with_debt=admit_next_grade_with_debt,
        full_grade_b=full_grade_b)
    if (type(minutes) is not int or not 1 <= minutes <= 1440 or
            type(steps_per_visit) is not int or not 1 <= steps_per_visit <= 2048 or
            type(max_visits) is not int or max_visits < 0 or
            type(batch_size) is not int or batch_size < 2 or batch_size % 2 or
            type(source_prefetch_workers) is not int or
            not 0 <= source_prefetch_workers <= 2):
        raise ValueError("HUMAN_TRAINER_INVALID_OPERATOR_LIMITS")
    grace_requested = stagnation_grace_grade is not None or stagnation_grace_steps != 0
    if grace_requested and (
            not resume or not isinstance(stagnation_grace_grade, str) or
            not stagnation_grace_grade or type(stagnation_grace_steps) is not int or
            stagnation_grace_steps <= 0):
        raise ValueError("STAGNATION_GRACE_REQUIRES_EXPLICIT_RESUME_REQUEST")
    if flash_mode and not resume:
        raise ValueError("FLASH_MODE_REQUIRES_RESUME")
    if boolean_composite and not resume:
        raise ValueError("BOOLEAN_COMPOSITE_REQUIRES_RESUME")
    if boolean_idboolops and not resume:
        raise ValueError("BOOLEAN_IDBOOLOPS_REQUIRES_RESUME")
    if boolean_association_bridge and not resume:
        raise ValueError("BOOLEAN_ASSOCIATION_BRIDGE_REQUIRES_RESUME")
    if admit_next_grade_with_debt and not resume:
        raise ValueError("DEBT_GRADE_ADMISSION_REQUIRES_RESUME")
    if admit_next_grade_with_debt and numeric_staircase:
        raise ValueError("DEBT_GRADE_ADMISSION_INCOMPATIBLE_WITH_NUMERIC_STAIRCASE")
    if autonomous_curriculum and not retention_enabled:
        raise ValueError("AUTONOMOUS_CURRICULUM_REQUIRES_RETENTION")
    if autonomous_curriculum and flash_mode:
        raise ValueError("AUTONOMOUS_CURRICULUM_INCOMPATIBLE_WITH_FLASH_MODE")
    if experiment_budget_guard is not None and not callable(experiment_budget_guard):
        raise TypeError("EXPERIMENT_BUDGET_GUARD_INVALID")
    if experiment_budget_guard is not None:
        experiment_budget_guard(600_000_000)
    if boolean_association_bridge:
        saved_path = Path(run_dir).expanduser().resolve() / "state.json"
        if not saved_path.is_file():
            raise ValueError("TEACHING_ENRICHMENT_REQUIRES_ADMITTED_FACTORY_RELEASE")
        from .boolean_association import VERSION as BOOLEAN_ASSOCIATION_OPTION
        saved_release = json.loads(saved_path.read_text(encoding="utf-8"))
        if not admitted_release_supports_teaching_option(
                Path(run_dir).expanduser().resolve(), saved_release,
                BOOLEAN_ASSOCIATION_OPTION):
            raise ValueError("TEACHING_ENRICHMENT_NOT_ADMITTED_BY_FACTORY_RELEASE")
    if retention_enabled:
        # Experiments never attach to the canonical run in another checkout.
        # The independent snapshot/copy step is a deliberate operator action.
        isolated_root = (Path(__file__).resolve().parents[1] / "runs").resolve()
        target = Path(run_dir).expanduser().resolve()
        if target == isolated_root or isolated_root not in target.parents:
            raise ValueError("LEARNING_EXPERIMENT_REQUIRES_ISOLATED_WORKTREE_RUN")
    elif resume:
        # Fail before GPU loading, orphan recovery, or any state mutation when
        # a protected student's policy would otherwise be silently disabled.
        saved_path = Path(run_dir).expanduser().resolve() / "state.json"
        if (saved_path.is_file() and json.loads(saved_path.read_text()).get(
                "learning_experiment") is not None):
            raise ValueError("LEARNING_EXPERIMENT_PROTECTED_RESUME_REQUIRES_RETENTION")
    import mlx.core as mx
    mx.set_default_device(mx.gpu)
    with trace_span("PREPARE_SOURCE"):
        manifest, historical_course, engine, teacher_sha, historical_teacher, provenance = prepare_source(
            source_root, source_checkpoint, manifest_path)
    course_a = initial_course(historical_course)
    # Build only verified source-bound metadata; no student, optimizer or
    # checkpoint is touched while preparing a future grade's course.
    course_b = None
    course_c = None
    staircase_course = None
    course = course_a
    run_dir = Path(run_dir).expanduser().resolve()
    start = time.monotonic()
    with operator_lock(run_dir), ExitStack() as resources:
        trace_mark("OPERATOR_LOCK_ACQUIRED")
        if resume:
            saved = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
            pending = run_dir / "states" / f"{saved['generation'] + 1:07d}.json"
            if pending.exists() and (pending.is_symlink() or not pending.is_file()):
                raise ValueError("HUMAN_TRAINER_PENDING_GENERATION_UNSAFE_PATH")
            pending_state = (json.loads(pending.read_text(encoding="utf-8"))
                             if pending.exists() else None)
            if saved.get("factory_admission_v2") is not None:
                saved_release = _read_executable_factory_release_artifact(
                    run_dir, saved)
                course = legacy_course_for_profile(
                    course_a, source_root, saved_release.profile)
                admitted_courses = None
            else:
                course, admitted_courses = resolve_legacy_resume_course(
                    historical_course, source_root, saved, course_a,
                    pending=pending_state)
            with trace_span("RESUME_STUDENT"):
                params, optimizer, graph, receipt = _resume(
                    run_dir, manifest, course, teacher_sha,
                    grade_a_course=course_a, source_root=source_root,
                    admitted_courses=admitted_courses)
            admitted_v2 = _require_executable_factory_admission(
                run_dir, receipt, graph)
            course = legacy_course_for_profile(
                course_a, source_root, admitted_v2.profile)
            active_grade_count = len(admitted_v2.execution_plan.grades)
            target_boolean_profile = None
            if active_grade_count <= 2 and not autonomous_curriculum:
                target_boolean_profile = with_disabled_future_grades(
                    boolean_entry_profile(full=full_grade_b),
                    tuple(
                        grade.grade_id
                        for grade in admitted_v2.curriculum.grades[2:]))
            if (target_boolean_profile is not None and
                    receipt["school"]["stage"] == "AWAITING_NEXT_GRADE" and
                    active_grade_count == 1):
                receipt, course, admitted_v2, _ = _adopt_executable_profile(
                    run_dir, receipt, course_a, source_root, graph,
                    target_boolean_profile)
            elif (target_boolean_profile is not None and
                  active_grade_count == 2 and
                  admitted_v2.profile != target_boolean_profile):
                current_program = schedule_program_from_executable_release(
                    admitted_v2)
                current_school = _state_from_json(
                    receipt["school"], current_program)
                if current_school.grade == current_program.grades[-1].id:
                    receipt, course, admitted_v2, _ = _adopt_executable_profile(
                        run_dir, receipt, course_a, source_root, graph,
                        target_boolean_profile)
            admitted_v2 = _require_executable_factory_admission(
                run_dir, receipt, graph)
            if ((receipt["school"]["stage"] == "AWAITING_NEXT_GRADE" or
                 admit_next_grade_with_debt) and
                    (not autonomous_curriculum or admit_next_grade_with_debt) and
                    len(admitted_v2.execution_plan.grades) == 2 and
                    len(admitted_v2.curriculum.grades) > 2):
                if admit_next_grade_with_debt:
                    receipt = _measure_debt_admission_boundary(
                        mx, run_dir, receipt, manifest, course, source_root,
                        params, graph)
                catalog_transition = numeric_entry_transition(
                    admitted_v2, graph,
                    full_boolean=full_grade_b,
                    maximum=3 if numeric_staircase else 10)
                params, optimizer, graph, receipt, course = (
                    _adopt_catalog_profile(
                        mx, run_dir, receipt, course_a, source_root, graph,
                        params, optimizer, catalog_transition,
                        reserve_gib=reserve_gib,
                        allow_mastery_debt=admit_next_grade_with_debt))
            receipt = _repair_scope_rubric_evidence(run_dir, receipt, course)
            receipt = _repair_championship_source_context(run_dir, receipt, course)
        else:
            if numeric_staircase:
                raise ValueError('NUMERIC_STAIRCASE_REQUIRES_RESUME')
            params, optimizer, graph, receipt = _init(
                run_dir, manifest, course, teacher_sha,
                historical_teacher, provenance, source_checkpoint,
                source_root=source_root, reserve_gib=reserve_gib,
                permitted_preexisting=(
                    (".experiment-run.json",)
                    if experiment_budget_guard is not None else ()))
        receipt, executable_release, schedule_program = _ensure_executable_release(
            run_dir, receipt, course, course_a, source_root, graph)
        with trace_span("RECONCILE_VOCABULARY"):
            receipt = _reconcile_vocabulary_metadata(
                run_dir, receipt, course, params, optimizer, graph)
        learning_settings = (LearningSettings(
            probe_each=experiment_probe_each,
            mature_max_loss=experiment_mature_max_loss,
            introduction_extra_loss=experiment_introduction_extra_loss,
            protected_cap_limit=experiment_protected_cap_limit)
            if retention_enabled else None)
        with trace_span("RECONCILE_LEARNING_SETTINGS"):
            receipt = _reconcile_learning_settings(
                run_dir, receipt, course, learning_settings, optimizer)
        if learning_settings is not None:
            with trace_span("SEED_WHOLE_STUDENT_PEAK"):
                receipt = _seed_saved_whole_student_peak(
                    run_dir, receipt, course, optimizer)
        autonomy_session = None
        if autonomous_curriculum:
            from .runtime.autonomy_live import LiveAutonomySession
            autonomy_session = LiveAutonomySession.open(
                run_dir, source_root, executable_release)
        source_prefetch_executor = None
        if learning_settings is not None and source_prefetch_workers:
            from bilqis_mlx.runtime.source_prefetch import (
                source_prefetch_pool,
            )
            source_prefetch_executor = resources.enter_context(
                source_prefetch_pool(source_prefetch_workers))
        school = _state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
        if autonomy_session is not None:
            autonomy_session.recover_teaching(
                receipt, school.current_student)
        if (stagnation_grace_grade is not None and
                stagnation_grace_grade not in set(school.active_grades)):
            raise ValueError("STAGNATION_GRACE_GRADE_NOT_ACTIVE")
        grace, grace_created = reconcile_optimizer_step_grace(
            receipt.get("stagnation_grace"),
            requested_grade=stagnation_grace_grade,
            requested_steps=stagnation_grace_steps,
            optimizer_step=school.current_student.optimizer_step)
        if grace != receipt.get("stagnation_grace"):
            receipt = _advance(
                run_dir, {**receipt, "stagnation_grace": grace}, school,
                result=receipt["result"])
            if grace_created:
                _record(run_dir, {
                    "event": "SCHOOL_STAGNATION_GRACE_CONFIGURED",
                    "generation": receipt["generation"],
                    "grade": grace["grade"],
                    "started_optimizer_step": grace["started_optimizer_step"],
                    "optimizer_step_budget": grace["optimizer_step_budget"],
                    "until_optimizer_step": grace["until_optimizer_step"],
                    "reason": grace["reason"],
                    "model_and_optimizer_unchanged": True,
                })
        previous_stagnation = receipt.get("stagnation_session")
        prior_debt = quarantined_capabilities(previous_stagnation)
        school = _state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
        deferred_before_reentry = school.stage == "DEFERRED_STAGNATION"
        if prior_debt and deferred_before_reentry:
            school = reactivate_stagnation_debt(_schedule_for_receipt(run_dir, receipt, course), school, prior_debt)
            receipt = {**receipt, "school": asdict(school)}
        history = list(receipt.get("stagnation_history", ()))
        if previous_stagnation is not None:
            history.append({
                "session_id": previous_stagnation["session_id"],
                "started_generation": previous_stagnation["started_generation"],
                "ended_before_generation": receipt["generation"],
                "quarantined": list(prior_debt),
                "alerts": list(end_of_run_alerts(previous_stagnation)),
            })
        receipt["stagnation_history"] = history[-16:]
        receipt["stagnation_session"] = start_stagnation_session(
            session_id=uuid.uuid4().hex, generation=receipt["generation"],
            required_capabilities=assessment_capabilities(_schedule_for_receipt(run_dir, receipt, course), school))
        debt_grades = {capability.partition(".")[0] for capability in prior_debt}
        grace_reentry = grace_suppressed_capabilities(
            receipt.get("stagnation_grace"), required_capabilities=tuple(prior_debt),
            optimizer_step=school.current_student.optimizer_step)
        if (prior_debt and deferred_before_reentry and len(debt_grades) == 1 and
                set(grace_reentry) != set(prior_debt)):
            receipt["stagnation_session"], rehabilitation_event = (
                activate_sole_grade_rehabilitation(
                    receipt["stagnation_session"],
                    capabilities=tuple(prior_debt),
                    generation=receipt["generation"]))
            pending = list(receipt.get("_pending_visit_events", ()))
            pending.append(rehabilitation_event)
            receipt["_pending_visit_events"] = pending
        school = _state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
        _record(run_dir, {
            "event": "SCHOOL_SESSION_STARTED",
            "generation": receipt["generation"],
            "run_id": receipt["run_id"],
            "grade": school.grade,
            "grade_phase": school.stage,
            "optimizer_step": school.current_student.optimizer_step,
            "checkpoint_sha256": school.current_student.sha256,
            "committed_total_visits": school.visits,
            "source_prefetch_workers": (source_prefetch_workers
                                         if source_prefetch_executor is not None else 0),
            "flash_mode": flash_mode,
            "boolean_association_bridge": boolean_association_bridge,
            "autonomous_curriculum": autonomous_curriculum,
        })
        visits = 0
        while True:
            if experiment_budget_guard is not None:
                experiment_budget_guard(600_000_000)
            final_numeric_scope = receipt.get("numeric_scope_final_maximum")
            if final_numeric_scope is not None:
                admitted_v2 = _require_executable_factory_admission(
                    run_dir, receipt, graph)
                active_program = schedule_program_from_executable_release(
                    admitted_v2)
                active_school = _state_from_json(
                    receipt["school"], active_program)
                next_numeric_profile = next_numeric_scope_profile(
                    admitted_v2, final_maximum=final_numeric_scope)
                if (next_numeric_profile is not None and
                        active_school.stage == "AWAITING_NEXT_GRADE"):
                    receipt, course, executable_release, schedule_program = (
                        _adopt_executable_profile(
                            run_dir, receipt, course_a, source_root, graph,
                            next_numeric_profile))
            school = _state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
            receipt = _reconcile_stagnation_scope(
                run_dir, receipt, course, school)
            school = _state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
            autonomy_teaching_work = None
            budget_reason = session_stop_reason(
                stage="MAIN", elapsed_seconds=time.monotonic() - start, minutes=minutes,
                visits=visits, max_visits=max_visits)
            if (autonomy_session is not None and school.stage == "AWAITING_NEXT_GRADE" and
                    budget_reason is None):
                autonomy_session.refresh_release(
                    _read_executable_factory_release_artifact(run_dir, receipt))
                proposal, proposal_file = autonomy_session.propose_source_frontier_work(
                    school.current_student, graph)
                if proposal.disposition.value == "PROPOSAL":
                    params, optimizer, graph, receipt, course = _adopt_jit_proposal(
                        mx, run_dir, receipt, course_a, source_root, graph, params, optimizer,
                        autonomy_session, proposal, reserve_gib=reserve_gib)
                    autonomy_session.refresh_release(
                        _read_executable_factory_release_artifact(run_dir, receipt))
                    _record(run_dir, {
                        "event": "SCHOOL_AUTONOMY_JIT_PROPOSAL_ADOPTED",
                        "generation": receipt["generation"],
                        "proposal_sha256": proposal.proposal_sha256,
                        "proposal_file": proposal_file,
                        "factory_release_sha256": receipt["factory_release_sha256"],
                        "actual_neural_updates": 0,
                    })
                    continue
            reason = session_stop_reason(
                stage=("MAIN" if autonomy_session is not None and
                       school.stage == "AWAITING_NEXT_GRADE" else school.stage),
                elapsed_seconds=time.monotonic() - start,
                minutes=minutes, visits=visits, max_visits=max_visits,
                grade=school.grade, flash_mode=flash_mode)
            if reason is not None:
                break
            if school.stage.startswith("ASSESS_"):
                if flash_mode:
                    # Flash may skip expensive championship/promotion work, but
                    # it may not skip the fresh cumulative evidence needed to
                    # choose recovery work or advance the cross-grade spiral.
                    receipt = _flush_flash_student(
                        run_dir, receipt, course, params, optimizer, graph,
                        reserve_gib=reserve_gib)
                    receipt = _take_exam(
                        mx, run_dir, receipt, manifest, course, source_root,
                        source_checkpoint, params, optimizer, graph,
                        reserve_gib=reserve_gib, scheduler_only=True)
                    if experiment_budget_guard is not None:
                        experiment_budget_guard(0)
                    school = _state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
                    if school.stage.startswith("ASSESS_"):
                        # Scheduler-only evidence found no remaining imperfect
                        # grade. Preserve the qualification debt for a full
                        # authoritative exam rather than minting mastery in flash.
                        reason = "FLASH_QUALIFICATION_REQUIRED"
                        break
                    continue
                with trace_span(
                        "ASSESSMENT", generation=receipt["generation"],
                        phase=school.stage, grade=school.grade):
                    receipt = _take_exam(
                        mx, run_dir, receipt, manifest, course, source_root,
                        source_checkpoint, params, optimizer, graph,
                        reserve_gib=reserve_gib)
                if experiment_budget_guard is not None:
                    experiment_budget_guard(0)
                continue
            if autonomous_curriculum:
                from .factory.autonomy import (
                    AutonomyActionKind)
                from .runtime.autonomy_live import scheduled_teaching_matches

                current_release = _read_executable_factory_release_artifact(run_dir, receipt)
                autonomy_session.refresh_release(current_release)
                action = autonomy_session.action(school.current_student)
                if action.deferred_obligation_ids:
                    selected_work = (
                        action.evidence_work or
                        (action.teaching_work
                         if action.kind is AutonomyActionKind.TEACHING
                         else None))
                    _record(run_dir, {
                        "event": "SCHOOL_AUTONOMY_REMEDIATION_DEFERRED",
                        "generation": receipt["generation"],
                        "grade": school.grade,
                        "deferred_obligations":
                            list(action.deferred_obligation_ids),
                        "selected_capability": (
                            selected_work.capability_id
                            if selected_work is not None else None),
                        "student_sha256": school.current_student.sha256,
                        "optimizer_step":
                            school.current_student.optimizer_step,
                        "actual_neural_updates": 0,
                    })
                if action.kind is AutonomyActionKind.SAFE_HOLD:
                    frontier_result = (
                        autonomy_session.propose_source_frontier_work(
                            school.current_student, graph))
                    if frontier_result is not None:
                        proposal, proposal_file = frontier_result
                        reason = (
                            "AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED"
                            if proposal.disposition.value ==
                            "SOURCE_DEVELOPMENT"
                            else "AUTONOMY_JIT_PROPOSAL_READY")
                        _record(run_dir, {
                            "event": (
                                "SCHOOL_AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED"
                                if proposal.disposition.value ==
                                "SOURCE_DEVELOPMENT"
                                else "SCHOOL_AUTONOMY_JIT_PROPOSAL_READY"),
                            "generation": receipt["generation"],
                            "grade": school.grade,
                            "deferred_obligations":
                                list(action.deferred_obligation_ids),
                            "proposal_sha256": proposal.proposal_sha256,
                            "proposal_file": proposal_file,
                            "frontier_sha256": proposal.frontier_sha256,
                            "candidate_gate_count":
                                len(proposal.candidate_gates),
                            "selected_candidate_ids":
                                list(proposal.selected_candidate_ids),
                            "student_sha256":
                                school.current_student.sha256,
                            "optimizer_step":
                                school.current_student.optimizer_step,
                            "model_and_optimizer_unchanged": True,
                        })
                    else:
                        reason = "AUTONOMY_SAFE_HOLD"
                        _record(run_dir, {
                            "event": "SCHOOL_AUTONOMY_SAFE_HOLD",
                            "generation": receipt["generation"],
                            "grade": school.grade,
                            "deferred_obligations":
                                list(action.deferred_obligation_ids),
                            "student_sha256":
                                school.current_student.sha256,
                            "optimizer_step":
                                school.current_student.optimizer_step,
                            "model_and_optimizer_unchanged": True,
                        })
                    break
                if action.kind is AutonomyActionKind.SOURCE_COVERAGE:
                    reason = "AUTONOMY_SOURCE_COVERAGE_REQUIRED"
                    _record(run_dir, {
                        "event": "SCHOOL_AUTONOMY_SOURCE_COVERAGE_BLOCKED",
                        "generation": receipt["generation"],
                        "grade": school.grade,
                        "debt": action.source_coverage_debt,
                        "model_and_optimizer_unchanged": True,
                    })
                    break
                if action.kind is AutonomyActionKind.LEARNING_EVIDENCE:
                    optimizer_step = int(optimizer.state["step"].item())
                    if optimizer_step != school.current_student.optimizer_step:
                        raise ValueError(
                            "AUTONOMY_EVIDENCE_REQUIRES_DURABLE_CHECKPOINT")
                    work = action.evidence_work
                    evidence = autonomy_session.measure(
                        graph, work,
                        checkpoint={
                            **asdict(school.current_student),
                            "model_and_native_adamw": True,
                        },
                        seed=_seed(
                            receipt,
                            capability="AUTONOMY_EVIDENCE:" +
                            work.obligation.obligation_id,
                            step=len(autonomy_session.ledger.receipts) + 1),
                        predictor=lambda rows: _predictions(
                            mx, params, list(rows), receipt["config"],
                            receipt["answer_ids"]),
                    )
                    _record(run_dir, {
                        "event": "SCHOOL_AUTONOMY_EVIDENCE_RECORDED",
                        "generation": receipt["generation"],
                        "grade": school.grade,
                        "capability": work.capability_id,
                        "obligation": work.obligation.obligation_id,
                        "passed": evidence.passed,
                        "cohort_sha256": evidence.cohort_sha256,
                        "student_sha256": evidence.checkpoint_sha256,
                        "optimizer_step": evidence.optimizer_step,
                    })
                    if evidence.passed:
                        advanced = autonomy_session.advance_if_complete(
                            school, work.capability_id)
                        if advanced != school:
                            receipt = _advance(
                                run_dir, receipt, advanced,
                                result=_school_result_label(advanced))
                            visits += 1
                            _record(run_dir, {
                                "event":
                                    "SCHOOL_AUTONOMY_EVIDENCE_VISIT_COMPLETED",
                                "generation": receipt["generation"],
                                "grade": advanced.grade,
                                "capability": work.capability_id,
                                "optimizer_step":
                                    advanced.current_student.optimizer_step,
                                "student_sha256":
                                    advanced.current_student.sha256,
                                "retained_optimizer_updates": 0,
                            })
                    continue
                if action.kind is AutonomyActionKind.QUALIFICATION:
                    scheduled = next_capability(school)
                    if (scheduled is not None and
                            scheduled in set(autonomy_session.evidence_complete(school.current_student))):
                        advanced = visit(
                            course, school, scheduled,
                            school.current_student)
                        receipt = _advance(
                            run_dir, receipt, advanced,
                            result=_school_result_label(advanced))
                        visits += 1
                        _record(run_dir, {
                            "event":
                                "SCHOOL_AUTONOMY_QUALIFIED_VISIT_COMPLETED",
                            "generation": receipt["generation"],
                            "grade": advanced.grade,
                            "capability": scheduled,
                            "optimizer_step":
                                advanced.current_student.optimizer_step,
                            "student_sha256":
                                advanced.current_student.sha256,
                            "retained_optimizer_updates": 0,
                        })
                        continue
                elif action.kind is AutonomyActionKind.TEACHING:
                    target = action.teaching_work.capability_id
                    if not scheduled_teaching_matches(school, target):
                        rerouted = autonomy_session.reroute_teaching(
                            school, target)
                        receipt = _advance(
                            run_dir, receipt, rerouted,
                            result=_school_result_label(rerouted))
                        school = rerouted
                        _record(run_dir, {
                            "event": "SCHOOL_AUTONOMY_TEACHING_REROUTED",
                            "generation": receipt["generation"],
                            "grade": school.grade,
                            "capability": target,
                            "student_sha256": school.current_student.sha256,
                            "optimizer_step":
                                school.current_student.optimizer_step,
                            "actual_neural_updates": 0,
                        })
                    if not scheduled_teaching_matches(school, target):
                        raise ValueError(
                            "AUTONOMY_TEACHING_REROUTE_FAILED")
                    autonomy_teaching_work = action.teaching_work
            with trace_span("DISK_HEADROOM", visit_index=visits + 1):
                budget = headroom_snapshot(run_dir, required_bytes=600_000_000,
                                           reserve_gib=reserve_gib)
            if not budget["sufficient"]:
                reason = "DISK_RESERVE_REACHED"
                break
            # Retain the original fail-closed checkpoint preflight against
            # disk changes between telemetry and the actual write boundary.
            with trace_span("DISK_HEADROOM_ASSERT", visit_index=visits + 1):
                assert_headroom(run_dir, required_bytes=600_000_000,
                                reserve_gib=reserve_gib)
            with trace_span(
                    "VISIT_TOTAL", visit_index=visits + 1,
                    generation=receipt["generation"], phase=school.stage,
                    grade=school.grade):
                parent_for_visit = school
                pending_before = len(receipt.get("_pending_visit_events", ()))
                receipt = _take_visit(
                    mx, run_dir, receipt, manifest, course, engine,
                    params, optimizer, graph, steps_per_visit=steps_per_visit,
                    batch_size=batch_size, reserve_gib=reserve_gib,
                    source_root=source_root, learning_settings=learning_settings,
                    boolean_association_bridge=boolean_association_bridge,
                    autonomy_teaching_option=(autonomy_teaching_work.teaching_option_ids[0]
                                              if autonomy_teaching_work is not None else None),
                    source_prefetch_executor=source_prefetch_executor,
                    source_prefetch_workers=(source_prefetch_workers
                                             if source_prefetch_executor is not None else 0))
            visits += 1
            if autonomous_curriculum:
                # Autonomy evidence may only refer to a complete, read-back
                # verified model+AdamW checkpoint. Publish every autonomous
                # teaching visit immediately instead of carrying RAM-only state.
                autonomy_visit = (receipt.get("_pending_visit_events") or [{}])[-1]
                delivery = autonomy_visit.get("autonomy_teaching")
                receipt = _flush_working_student(
                    mx, run_dir, receipt, manifest, course,
                    params, optimizer, graph, reserve_gib=reserve_gib,
                    source_root=source_root)
                if experiment_budget_guard is not None:
                    experiment_budget_guard(0)
                school_after_flush = _state_from_json(
                    receipt["school"],
                    _schedule_for_receipt(run_dir, receipt, course))
                if autonomy_teaching_work is not None:
                    failed = autonomy_teaching_work.failed_evidence
                    current = school_after_flush.current_student
                    durable_autonomy_visit = None
                    if delivery is not None:
                        digest = delivery.get("specimen_content_sha256")
                        durable_autonomy_visit = next((
                            event for event in reversed(
                                receipt.get("delivery_outbox", ()))
                            if (isinstance(
                                    event.get("autonomy_teaching"), dict) and
                                event["autonomy_teaching"].get(
                                    "specimen_content_sha256") == digest)
                        ), None)
                        if durable_autonomy_visit is None:
                            raise ValueError(
                                "AUTONOMY_TEACHING_DURABLE_EVENT_MISSING")
                    if (delivery is not None and
                            current.sha256 != failed.checkpoint_sha256 and
                            current.optimizer_step > failed.optimizer_step):
                        intervention = autonomy_session.recover_teaching(
                            receipt, current)
                        if intervention is None:
                            raise ValueError(
                                "AUTONOMY_TEACHING_DURABLE_RECEIPT_MISSING")
                        _record(run_dir, {
                            "event":
                                "SCHOOL_AUTONOMY_TEACHING_RECORDED",
                            "generation": receipt["generation"],
                            "grade": school_after_flush.grade,
                            "capability":
                                autonomy_teaching_work.capability_id,
                            "obligation": failed.obligation_id,
                            "parent_student_sha256":
                                failed.checkpoint_sha256,
                            "student_sha256": current.sha256,
                            "optimizer_step": current.optimizer_step,
                        })
                    elif (delivery is not None and
                            current.sha256 == failed.checkpoint_sha256 and
                            current.optimizer_step == failed.optimizer_step and
                            durable_autonomy_visit.get(
                                "retained_optimizer_updates") == 0):
                        rejected = (
                            autonomy_session.rejected_attempt_from_event(
                                durable_autonomy_visit, failed))
                        _record(run_dir, {
                            "event":
                                "SCHOOL_AUTONOMY_TEACHING_REJECTED_RECORDED",
                            "generation": receipt["generation"],
                            "grade": school_after_flush.grade,
                            "capability":
                                autonomy_teaching_work.capability_id,
                            "obligation": failed.obligation_id,
                            "attempt_id": rejected.attempt_id,
                            "retention_reason":
                                rejected.retention_reason,
                            "student_sha256": current.sha256,
                            "optimizer_step": current.optimizer_step,
                            "candidate_optimizer_step":
                                rejected.candidate_optimizer_step,
                            "retained_optimizer_updates": 0,
                        })
            pending_visits = receipt.get("_pending_visit_events", ())
            if len(pending_visits) > pending_before:
                latest_visit = pending_visits[-1]
                if type(latest_visit.get("attempted_optimizer_updates")) is int:
                    # Project the complete visit into the live dashboard now,
                    # but preserve the durable checkpoint-gated event ledger.
                    # The telemetry layer deduplicates this exact generation
                    # when the real receipt is published at the boundary.
                    _notify_viewer({
                        **latest_visit,
                        "_live_ephemeral": True,
                        "_dashboard_redraw": False,
                    })
            after_visit = _state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
        with trace_span("FLUSH_FLASH_STUDENT" if flash_mode else "FLUSH_WORKING_STUDENT",
                        visits=visits):
            if experiment_budget_guard is not None:
                experiment_budget_guard(600_000_000)
            if flash_mode:
                receipt = _flush_flash_student(
                    run_dir, receipt, course, params, optimizer, graph,
                    reserve_gib=reserve_gib)
            else:
                receipt = _flush_working_student(
                    mx, run_dir, receipt, manifest, course, params, optimizer, graph,
                    reserve_gib=reserve_gib, source_root=source_root)
        if experiment_budget_guard is not None:
            experiment_budget_guard(0)
        school = _state_from_json(receipt["school"], _schedule_for_receipt(run_dir, receipt, course))
        budget = headroom_snapshot(run_dir, required_bytes=600_000_000,
                                   reserve_gib=reserve_gib)
        elapsed_seconds = round(time.monotonic() - start, 3)
        stagnation_alerts = end_of_run_alerts(receipt.get("stagnation_session"))
        stagnation_quarantined = quarantined_capabilities(
            receipt.get("stagnation_session"))
        _record(run_dir, {
            "event": "SCHOOL_SESSION_STOPPED", "stop_reason": reason,
            "generation": receipt["generation"], "run_id": receipt["run_id"],
            "optimizer_step": school.current_student.optimizer_step,
            "checkpoint_sha256": school.current_student.sha256,
            "visits_this_command": visits, "committed_total_visits": school.visits,
            "minutes": minutes, "max_visits": max_visits,
            "elapsed_seconds": elapsed_seconds,
            "grade_phase": school.stage, "grade": school.grade,
            "source_prefetch_workers": (source_prefetch_workers
                                         if source_prefetch_executor is not None else 0),
            "flash_mode": flash_mode,
            "boolean_association_bridge": boolean_association_bridge,
            "autonomous_curriculum": autonomous_curriculum,
            "resume_required": school.stage != "AWAITING_NEXT_GRADE",
            "stagnation_session_id": receipt.get("stagnation_session", {}).get(
                "session_id"),
            "stagnation_quarantined": list(stagnation_quarantined),
            "stagnation_alerts": list(stagnation_alerts),
            **{k: budget[k] for k in ("free_bytes", "reserve_bytes", "estimated_write_bytes")},
        })
        # Reclaim superseded JSON snapshot storage after the committed stop
        # receipt. Lossless compression retains exact source bytes and SHA
        # readback; all complete model/AdamW checkpoints remain untouched.
        from .state_archive import compact_states
        try:
            with trace_span("STATE_ARCHIVE_COMPACT"):
                maintenance = compact_states(run_dir, max_files=64)
        except (OSError, ValueError) as exc:
            maintenance = {"error": str(exc), "compressed_generations": 0}
            _record(run_dir, {"event": "SCHOOL_STATE_ARCHIVE_BLOCKED",
                              "generation": receipt["generation"],
                              "reason": str(exc)})
        trace_mark(
            "OPERATE_END", stop_reason=reason, visits=visits,
            optimizer_step=school.current_student.optimizer_step)
        return {
            "status": receipt["result"],
            "stop_reason": reason,
            "elapsed_seconds": elapsed_seconds,
            "time_limit_minutes": minutes,
            "max_visits": max_visits,
            "disk_free_gib": round(budget["free_bytes"] / 1024**3, 3),
            "disk_reserve_gib": round(budget["reserve_bytes"] / 1024**3, 3),
            "disk_next_visit_gib": round(budget["estimated_write_bytes"] / 1024**3, 3),
            "grade": school.grade,
            "phase": school.stage,
            "visits_this_command": visits,
            "committed_total_visits": school.visits,
            "optimizer_step": school.current_student.optimizer_step,
            "checkpoint_sha256": school.current_student.sha256,
            "latest_exam": receipt["last_exam"],
            "stagnation_quarantined": list(stagnation_quarantined),
            "stagnation_alerts": list(stagnation_alerts),
            "stagnation_grace": receipt.get("stagnation_grace"),
            "experimental_retention": learning_settings is not None,
            "retention_enabled": learning_settings is not None,
            "source_prefetch_workers": (source_prefetch_workers
                                         if source_prefetch_executor is not None else 0),
            "flash_mode": flash_mode,
            "boolean_association_bridge": boolean_association_bridge,
            "state_archive": maintenance,
            "safe_resume_command": _resume_command(
                run_dir, source_root, learning_settings,
                boolean_association_bridge=boolean_association_bridge,
                autonomous_curriculum=autonomous_curriculum,
                source_prefetch_workers=source_prefetch_workers),
            "original_source_checkpoint_modified": False,
        }
