"""Neural-inert repair of checkpoint-bound runtime metadata."""
from __future__ import annotations

import bilqis_mlx.curriculum.scheduler as _curriculum_scheduler
import bilqis_mlx.generated_assessment as _bilqis_mlx_generated_assessment
import bilqis_mlx.learning.learning_experiment as _learning_learning_experiment
import bilqis_mlx.learning.stagnation_control as _learning_stagnation_control
import bilqis_mlx.learning.whole_student_retention as _learning_whole_student_retention
import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.state as _runtime_state
import copy as _copy
import dataclasses as _dataclasses
import json as _json


def _require_championship_source_context_custody(condition: bool) -> None:
    if not condition:
        raise ValueError("CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_CUSTODY_DRIFT")


def _affected_championship_source_context(run_dir, epoch) -> set[str]:
    affected = set()
    for capability, role in epoch["active_roles"].items():
        evidence = (
            *role.get("qualification_witnesses", ()),
            *role.get("surviving_battery", ()),
        )
        for item in evidence:
            sha = item.get("cohort_sha256")
            assessment_rubric = item.get("rubric_sha256")
            source_oracle = item.get("source_oracle_sha256")
            if not all(isinstance(value, str) and len(value) == 64
                       for value in (sha, assessment_rubric, source_oracle)):
                raise ValueError("CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_IDENTITY_DRIFT")
            path = run_dir / "cohorts" / (sha + ".json")
            if path.is_symlink() or not path.is_file():
                raise ValueError("CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_COHORT_MISSING")
            stored = _json.loads(path.read_text())
            _require_championship_source_context_custody(
                stored.get("cohort_sha256") == sha and
                stored.get("source_manifest_sha256") == source_oracle)
            try:
                _bilqis_mlx_generated_assessment.verify_stored_cohort(stored, sha)
            except ValueError as exc:
                raise ValueError(
                    "CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_CONTENT_DRIFT") from exc
            declared_cohort_rubric = item.get("cohort_rubric_sha256")
            if declared_cohort_rubric is not None:
                # A modern witness has a distinct, authenticated source
                # rubric. It is authoritative for its own cohort and cannot
                # be replaced by either the championship title rubric or a
                # later exam's scope. Verify it rather than skipping the row.
                _require_championship_source_context_custody(
                    stored.get("rubric_sha256") == declared_cohort_rubric)
                continue
            if stored.get("rubric_sha256") != assessment_rubric:
                affected.add(capability)
                break
    return affected


def _invalidate_championship_source_context(epoch, affected: set[str]):
    reset = _copy.deepcopy(epoch)
    for capability in sorted(affected):
        prior = reset["active_roles"].pop(capability)
        reset.setdefault("invalidated_active_roles", []).append({
            "capability": capability,
            "reason": "COHORT_SOURCE_RUBRIC_CONTRADICTION",
            "role": prior,
        })
    touched_grades = {cap.partition(".")[0] for cap in affected}
    for grade in sorted(touched_grades):
        prior_soup = reset.get("active_grade_soups", {}).pop(grade, None)
        if prior_soup is not None:
            reset.setdefault("invalidated_active_soups", []).append({
                "grade": grade,
                "reason": "ROLE_SOURCE_CONTRADICTION",
                "active_grade_soup": prior_soup,
            })
    return reset


def _repair_championship_source_context(run_dir, receipt, course):
    """Archive titles minted while cohort-source and assessment rubrics were conflated."""
    epoch = receipt.get("mentor_epoch")
    if not isinstance(epoch, dict) or not epoch.get("active_roles"):
        return receipt

    affected = _affected_championship_source_context(run_dir, epoch)

    if not affected:
        return receipt

    school = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
    history = [*receipt.get("championship_epoch_history", ()), _copy.deepcopy(epoch)]
    # This is a capability-local evidence failure, not a holistic school
    # identity change. Invalidate only the affected title(s) and their grade
    # soup(s). In particular, settled matchups are permanent; clearing that
    # ledger would permit repeated title matches between the same checkpoints.
    reset = _invalidate_championship_source_context(epoch, affected)
    repaired = {
        **receipt,
        "mentor_epoch": reset,
        "championship_epoch_history": history,
    }
    record = _runtime_checkpoints._advance(
        run_dir, repaired, school,
        result=receipt.get("result"), persist=False)
    event = {
        "event": "SCHOOL_CHAMPIONSHIP_SOURCE_CONTEXT_REPAIRED",
        "generation": record["generation"],
        "source_generation": receipt["generation"],
        "student_sha256": school.current_student.sha256,
        "optimizer_step": school.current_student.optimizer_step,
        "invalidated_championship_roles": sorted(affected),
        "archived_prior_epoch": True,
        "preserved_championship_roles": sorted(reset["active_roles"]),
        "preserved_settled_matchups": len(reset.get("settled_matchups", {})),
        "actual_neural_updates": 0,
        "model_and_own_adamw_unchanged": True,
    }
    record = _runtime_checkpoints._persist(run_dir, _runtime_checkpoints._with_delivery_outbox(record, (event,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, record)
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
    school = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
    if int(optimizer.state["step"].item()) != school.current_student.optimizer_step:
        raise ValueError("HUMAN_TRAINER_VOCAB_RECONCILE_OWN_ADAMW_DRIFT")
    candidate = _runtime_checkpoints._advance(
        run_dir, {**receipt, "config": {**receipt["config"], "vocab_size": actual}},
        school, persist=False)
    event = {"event": "SCHOOL_CURRENT_VOCAB_METADATA_RECONCILED",
             "generation": candidate["generation"],
             "former_metadata_vocab_size": previous,
             "active_semantic_graph_vocab_size": actual,
             "student_sha256": school.current_student.sha256,
             "optimizer_step": school.current_student.optimizer_step,
             "model_and_optimizer_unchanged": True}
    result = _runtime_checkpoints._persist(run_dir, _runtime_checkpoints._with_delivery_outbox(candidate, (event,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, result)
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
    if settings is None or inherited.get("version") != _learning_learning_experiment.VERSION:
        raise ValueError("LEARNING_EXPERIMENT_RESUME_REQUIRES_IDENTICAL_OPT_IN")
    new = _dataclasses.asdict(settings)
    previous = inherited.get("settings")
    if previous == new:
        return receipt
    if not isinstance(previous, dict):
        raise ValueError("LEARNING_EXPERIMENT_HISTORY_INVALID")
    old = _dataclasses.asdict(_learning_learning_experiment.Settings(**previous))
    if (new["probe_each"] != old["probe_each"] or
            new["protected_cap_limit"] != old["protected_cap_limit"] or
            new["introduction_extra_loss"] != old["introduction_extra_loss"] or
            new["mature_max_loss"] >= old["mature_max_loss"]):
        raise ValueError("LEARNING_EXPERIMENT_RESUME_REQUIRES_IDENTICAL_OPT_IN")
    school = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
    if int(optimizer.state["step"].item()) != school.current_student.optimizer_step:
        raise ValueError("LEARNING_EXPERIMENT_POLICY_OWN_ADAMW_DRIFT")
    prior = list(receipt.get("learning_policy_revisions", ()))
    change = {"from": old, "to": new,
              "from_generation": receipt["generation"],
              "optimizer_step": school.current_student.optimizer_step,
              "student_sha256": school.current_student.sha256}
    candidate = _runtime_checkpoints._advance(run_dir, {**receipt,
        "learning_experiment": {"version": _learning_learning_experiment.VERSION,
                                "settings": new},
        "learning_policy_revisions": [*prior, change]}, school, persist=False)
    event = {"event": "SCHOOL_EXPERIMENTAL_RETENTION_POLICY_TIGHTENED",
             "generation": candidate["generation"], **change,
             "model_and_optimizer_unchanged": True}
    result = _runtime_checkpoints._persist(run_dir, _runtime_checkpoints._with_delivery_outbox(candidate, (event,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, result)
    return result


def _seed_saved_whole_student_peak(run_dir, receipt, course, optimizer):
    """Protect the already saved live exam before the next neural visit.

    Only an exam belonging to the current, fully durable checkpoint qualifies.
    Earlier rubric scores, orphan bundles and mismatched AdamW cannot seed it.
    """
    if receipt.get("whole_student_peaks"):
        return receipt
    school = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
    checkpoint = _dataclasses.asdict(school.current_student)
    prior = receipt.get("last_exam") or {}
    if (not prior.get("scores") or
            prior.get("student_sha256") != checkpoint["sha256"] or
            prior.get("optimizer_step") != checkpoint["optimizer_step"]):
        return receipt
    if int(optimizer.state["step"].item()) != checkpoint["optimizer_step"]:
        raise ValueError("WHOLE_STUDENT_PEAK_SEED_ADAMW_DRIFT")
    peaks, outcome = _learning_whole_student_retention.advance_peaks(
        [], curriculum_mode=receipt["curriculum_mode"],
        numeric_maximum=receipt.get("numeric_maximum"),
        rubric_sha256=prior["exam_rubric_sha256"],
        cohort_sha256=prior["cohort_sha256"],
        assessment_scope_sha256=prior["assessment_scope_sha256"],
        scores=prior["scores"], checkpoint=checkpoint)
    candidate = _runtime_checkpoints._advance(run_dir, {**receipt, "whole_student_peaks": peaks},
                         school, persist=False)
    event = {"event": "SCHOOL_EXISTING_WHOLE_STUDENT_PEAK_PRESERVED",
             "generation": candidate["generation"],
             "optimizer_step": checkpoint["optimizer_step"],
             "student_sha256": checkpoint["sha256"],
             "exam_correct": outcome["best_correct"],
             "exam_total": outcome["best_total"],
             "source_cohort_sha256": prior["cohort_sha256"],
             "model_and_optimizer_unchanged": True}
    result = _runtime_checkpoints._persist(run_dir, _runtime_checkpoints._with_delivery_outbox(candidate, (event,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, result)
    return result


def _rehabilitate_sole_grade_debt(
        program, school, stagnation, debt, *, generation):
    """Keep training when containment debt is the only work left in one grade."""
    if (stagnation is None or school.stage != "DEFERRED_STAGNATION" or
            not debt):
        return stagnation, school, ()
    grades = {capability.partition(".")[0] for capability in debt}
    if len(grades) != 1:
        return stagnation, school, ()
    stagnation, event = _learning_stagnation_control.activate_sole_grade_rehabilitation(
        stagnation, capabilities=tuple(debt), generation=generation)
    school = _curriculum_scheduler.reactivate_stagnation_debt(program, school, tuple(debt))
    return stagnation, school, (event,)


def _reconcile_stagnation_scope(run_dir, receipt, course, school):
    """Keep command-local stagnation state aligned with the live scheduler scope."""
    control = receipt.get("stagnation_session")
    if control is None:
        return receipt
    required = _curriculum_scheduler.assessment_capabilities(_runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course), school)
    updated, event = _learning_stagnation_control.reconcile_required_scope(
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
        "quarantined": list(_learning_stagnation_control.quarantined_capabilities(control)),
    })
    migrated = {
        **receipt,
        "stagnation_session": updated,
        "stagnation_scope_history": history[-32:],
    }
    record = _runtime_checkpoints._advance(
        run_dir, migrated, school, result=receipt.get("result"),
        persist=False)
    if record["generation"] != event["generation"]:
        raise ValueError("STAGNATION_SCOPE_RECONCILIATION_GENERATION_DRIFT")
    event = {**event, "grade": school.grade}
    record = _runtime_checkpoints._persist(run_dir, _runtime_checkpoints._with_delivery_outbox(record, (event,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, record)
    return record


def _advance_stagnation_after_routine(
        *, program, school, routine_assessment, routine_advanced,
        stagnation, blocked_before, active_scope, routine_measured,
        routine_warnings, generation, quarantine_suppressed=(),
        session_elapsed_seconds=None, paired_progressed=(),
        paired_progress_usable=None, progress_checkpoint=None):
    """Apply one completed routine boundary to the current session containment."""
    events = ()
    if stagnation is None:
        return stagnation, events, routine_advanced, ()
    if (session_elapsed_seconds is not None and
            paired_progress_usable is not None and
            progress_checkpoint is not None):
        stagnation = _learning_stagnation_control.observe_paired_progress(
            stagnation,
            measured_capabilities=tuple(routine_measured["scores"]),
            improved_capabilities=tuple(paired_progressed),
            measurement_usable=paired_progress_usable,
            elapsed_seconds=session_elapsed_seconds,
            progress_checkpoint=progress_checkpoint)
    if (school.stage == "ASSESS_MAIN" and
            routine_advanced.stage == "RECOVERY_1"):
        stagnation = _learning_stagnation_control.begin_recovery_cycle(
            stagnation, first_recovery=routine_advanced.first_recovery)
    elif school.stage == "ASSESS_RECOVERY_2":
        tail = _curriculum_scheduler.weakest_three(routine_assessment.scores, active_scope)
        stagnation, events = _learning_stagnation_control.complete_recovery_cycle(
            stagnation, weakest_tail=tail,
            scores=routine_measured["scores"],
            generation=generation,
            active_warnings=tuple(routine_warnings.get("active_warnings", ())),
            quarantine_suppressed=tuple(quarantine_suppressed),
            **({"elapsed_seconds": session_elapsed_seconds}
               if session_elapsed_seconds is not None else {}))
        blocked_after = _learning_stagnation_control.quarantined_capabilities(stagnation)
        if set(blocked_after) != set(blocked_before):
            retained_scores = {
                cap: score for cap, score in routine_assessment.scores.items()
                if cap not in set(blocked_after)}
            if not retained_scores:
                routine_advanced = _dataclasses.replace(
                    school, stage="DEFERRED_STAGNATION", queue=(),
                    first_recovery=(),
                    latest_rubric_digest=routine_assessment.rubric_digest)
            else:
                reduced = _curriculum_scheduler.Assessment(
                    checkpoint_sha256=routine_assessment.checkpoint_sha256,
                    optimizer_step=routine_assessment.optimizer_step,
                    course_digest=routine_assessment.course_digest,
                    rubric_digest=routine_assessment.rubric_digest,
                    scores=retained_scores,
                    evaluation_id=routine_assessment.evaluation_id +
                                  "/post-stagnation-filter")
                routine_advanced = _curriculum_scheduler.assess_withheld(
                    program, school, reduced, blocked_after,
                    rubric_capabilities=active_scope)
    if routine_advanced.stage == "DEFERRED_STAGNATION":
        stagnation, routine_advanced, rehabilitation_events = (
            _rehabilitate_sole_grade_debt(
                program, routine_advanced, stagnation,
                _learning_stagnation_control.quarantined_capabilities(stagnation),
                generation=generation))
        events = (*events, *rehabilitation_events)
    return (
        stagnation, events, routine_advanced,
        _learning_stagnation_control.quarantined_capabilities(stagnation))
