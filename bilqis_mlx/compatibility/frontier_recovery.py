"""Historical Grade-C frontier recovery from immutable admission evidence."""
from __future__ import annotations
from dataclasses import asdict
import json
from ..generated_assessment import score as score_cohort
from ..runtime.state import _seed, _fingerprint, _state_from_json
from ..runtime.mlx_checkpoint import load_semantically_bound_bundle

def _grade_c_admission_event(run_dir, current, previous, introduced_grade):
    admissions = []
    events_path = run_dir / "events.jsonl"
    if events_path.is_file():
        with events_path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                event = json.loads(line)
                if (event.get("event") == "SCHOOL_COURSE_ADMITTED" and
                        event.get("grade") == introduced_grade and
                        event.get("student_sha256") == current.get("sha256") and
                        event.get("previous_student_sha256") == previous.get("sha256")):
                    admissions.append(event)
    if len(admissions) != 1:
        raise ValueError("FIXED_FRONTIER_GRADE_C_ADMISSION_EVENT_DRIFT")
    return admissions[0]


def _grade_c_pre_admission_state(run_dir, admission, previous):
    pre_path = run_dir / "states" / f"{admission['generation'] - 1:07d}.json"
    if pre_path.is_symlink() or not pre_path.is_file():
        raise ValueError("FIXED_FRONTIER_GRADE_C_PRE_ADMISSION_STATE_MISSING")
    pre = json.loads(pre_path.read_text(encoding="utf-8"))
    pre_student = (pre.get("school") or {}).get("current_student") or {}
    if (pre_student.get("sha256") != previous.get("sha256") or
            pre_student.get("optimizer_step") != previous.get("optimizer_step")):
        raise ValueError("FIXED_FRONTIER_GRADE_C_PRE_ADMISSION_STATE_DRIFT")
    return pre


def _debt_boundary_source_exam(run_dir, pre, epoch, previous):
    expected_seed = _seed(
        pre,
        capability=(f"DEBT_ADMISSION_BOUNDARY:{pre.get('curriculum_mode')}:"
                    f"{previous['optimizer_step']}"))
    previous_caps = set(epoch.get("previous_capabilities") or ())
    matches = []
    for path in (run_dir / "cohorts").glob("*.json"):
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        rows = stored.get("rows") or ()
        if (stored.get("seed") == expected_seed and
                stored.get("schema") == pre.get("curriculum_mode") and
                {row.get("capability") for row in rows} == previous_caps):
            matches.append((path, stored))
    if len(matches) != 1:
        raise ValueError("FIXED_FRONTIER_GRADE_C_BOUNDARY_COHORT_AMBIGUOUS")
    path, stored = matches[0]
    return {
        "student_sha256": previous["sha256"],
        "optimizer_step": previous["optimizer_step"],
        "cohort_sha256": stored.get("cohort_sha256"),
        "cohort_file": str(path.relative_to(run_dir)),
        "cohort_seed": stored.get("seed"),
        "exam_rubric_sha256": stored.get("rubric_sha256"),
        "source_exam_plane": "DEBT_ADMISSION_BOUNDARY",
    }


def _verify_recovered_boundary_exam(mx, run_dir, source_exam, pre, previous, epoch):
    """Re-score the preserved parent and prove the mentor-epoch digest exactly."""
    from ..trainer import _predictions


    from ..fixed_frontier import load_frontier_cohort
    cohort = load_frontier_cohort(run_dir, source_exam)
    previous_weights, previous_optimizer, meta, previous_graph = (
        load_semantically_bound_bundle(run_dir / previous["filename"]))
    if (meta.get("safetensors_sha256") != previous["sha256"] or
            meta.get("optimizer_step") != previous["optimizer_step"]):
        raise ValueError("FIXED_FRONTIER_GRADE_C_PREVIOUS_BUNDLE_DRIFT")
    previous_guesses = _predictions(
        mx, previous_weights, list(cohort.rows), pre["config"], pre["answer_ids"])
    previous_measured = score_cohort(cohort, previous_guesses, previous)
    source_exam["scores"] = previous_measured["scores"]
    source_exam["misses_for_teacher"] = list(previous_measured["misses_for_teacher"])
    boundary = {
        "checkpoint_sha256": previous["sha256"],
        "cohort_sha256": cohort.digest,
        "rubric_sha256": source_exam.get("exam_rubric_sha256"),
        "scores": previous_measured["scores"],
    }
    expected_digest = (epoch.get("previous_boundary_exam_sha256") or
                       epoch.get("previous_graduation_exam_sha256"))
    if _fingerprint(boundary) != expected_digest:
        raise ValueError("FIXED_FRONTIER_GRADE_C_BOUNDARY_DIGEST_DRIFT")
    del previous_weights, previous_optimizer, previous_graph
    return source_exam


def _recover_grade_c_boundary_source(mx, run_dir, receipt):
    """Recover the exact pre-C boundary cohort from immutable admission evidence."""
    epoch = receipt.get("mentor_epoch") or {}
    school = receipt.get("school") or {}
    current = school.get("current_student") or {}
    baseline = epoch.get("baseline") or {}
    introduced_grade = epoch.get("introduced_grade")
    previous = (epoch.get("previous_boundary_checkpoint") or
                epoch.get("previous_graduate") or {})
    exam = receipt.get("last_exam") or {}
    if introduced_grade != "C":
        return None
    if (not introduced_grade or not receipt.get("grade_c_parent_course_digest") or
            baseline.get("sha256") != current.get("sha256") or
            baseline.get("optimizer_step") != current.get("optimizer_step") or
            exam.get("student_sha256") == current.get("sha256")):
        return None
    if (not previous.get("sha256") or
            exam.get("student_sha256") != previous.get("sha256")):
        raise ValueError("FIXED_FRONTIER_GRADE_C_LINEAGE_DRIFT")
    admission = _grade_c_admission_event(
        run_dir, current, previous, introduced_grade)
    pre = _grade_c_pre_admission_state(run_dir, admission, previous)
    source_exam = (
        _debt_boundary_source_exam(run_dir, pre, epoch, previous)
        if receipt.get("grade_c_admission_mode") == "CARRIED_MASTERY_DEBT"
        else dict(pre.get("last_exam") or {}))
    return _verify_recovered_boundary_exam(
        mx, run_dir, source_exam, pre, previous, epoch)


def _migrate_grade_c_fixed_frontier(mx, run_dir, receipt, course, parameters):
    """Idempotently bind an early Grade-C frontier to its graph-grown parent."""
    from ..trainer import _predictions, _advance, _persist, _with_delivery_outbox, _reconcile_delivery_outbox

    source_exam = _recover_grade_c_boundary_source(mx, run_dir, receipt)
    if source_exam is None:
        return receipt
    school = _state_from_json(receipt["school"], course)
    previous_caps = (receipt.get("mentor_epoch") or {}).get("previous_capabilities") or ()
    previous_grade = (
        previous_caps[-1].partition(".")[0] if previous_caps else None)
    from ..fixed_frontier import load_frontier_cohort, rebaseline_frontier_exam
    cohort = load_frontier_cohort(run_dir, source_exam)
    guesses = _predictions(
        mx, parameters, list(cohort.rows), receipt["config"], receipt["answer_ids"])
    migrated_exam = rebaseline_frontier_exam(
        run_dir, source_exam, checkpoint=asdict(school.current_student),
        predictions=guesses,
        assessment_grade=source_exam.get("assessment_grade", previous_grade),
        grade_exam_epoch=source_exam.get("grade_exam_epoch"))
    migrated = {**receipt,
                "last_exam": migrated_exam,
                "grade_c_fixed_frontier_cohort_sha256": cohort.digest}
    record = _advance(
        run_dir, migrated, school, last_exam=migrated_exam,
        result=receipt.get("result"), persist=False)
    event = {
        "event": "SCHOOL_FIXED_FRONTIER_REBASELINED",
        "generation": record["generation"],
        "grade": school.grade,
        "student_sha256": school.current_student.sha256,
        "optimizer_step": school.current_student.optimizer_step,
        "previous_student_sha256": source_exam.get("student_sha256"),
        "cohort_sha256": cohort.digest,
        "rows": len(cohort.rows),
        "actual_neural_updates": 0,
    }
    record = _persist(run_dir, _with_delivery_outbox(record, (event,)))
    _reconcile_delivery_outbox(run_dir, record)
    return record


def recover_legacy_frontier(mx, run_dir, receipt, course, parameters):
    from .live_releases import NUMERIC_RELEASE
    if receipt.get("curriculum_mode") != NUMERIC_RELEASE:
        return receipt
    return _migrate_grade_c_fixed_frontier(mx, run_dir, receipt, course, parameters)


def _measure_debt_admission_boundary(mx, run_dir, receipt, manifest, course,
                                     source_root, parameters, graph):
    """Freshly score the complete declared prior release for debt admission."""
    from ..trainer import (_draw_live_rows, _cohort_contract, _persist_live_cohort, _predictions, assessment_rubric_for_scope, make_cohort, score_cohort)
    school = _state_from_json(receipt["school"], course)
    full_scope = tuple(
        capability.id for grade in course.grades for capability in grade.capabilities)
    expected = {
        capability: count for grade in course.grades
        for capability, count in grade.exam_item_counts
    }
    if set(full_scope) != set(expected):
        raise ValueError("DEBT_ADMISSION_DECLARED_SCOPE_DRIFT")
    _, release, generator, _ = _cohort_contract(course)
    seed = _seed(
        receipt,
        capability=(
            f"DEBT_ADMISSION_BOUNDARY:{course.version}:"
            f"{school.current_student.optimizer_step}"),
    )
    rows = _draw_live_rows(source_root, graph, seed=seed, course=course)
    actual = {
        capability: sum(row["capability"] == capability for row in rows)
        for capability in full_scope
    }
    if (set(row["capability"] for row in rows) != set(full_scope) or
            actual != expected or len(rows) != sum(expected.values()) or
            len({row["id"] for row in rows}) != len(rows)):
        raise ValueError("DEBT_ADMISSION_BOUNDARY_SCOPE_INCOMPLETE")
    cohort = make_cohort(
        rows, generator_version=generator, seed=seed, rubric_version=release)
    cohort_file = _persist_live_cohort(run_dir, manifest, course, cohort)
    guesses = _predictions(
        mx, parameters, rows, receipt["config"], receipt["answer_ids"])
    scores = score_cohort(
        cohort, guesses, asdict(school.current_student))["scores"]
    if (set(scores) != set(expected) or
            any(scores[capability]["total"] != count
                for capability, count in expected.items())):
        raise ValueError("DEBT_ADMISSION_BOUNDARY_SCORE_SCOPE_DRIFT")
    return {**receipt, "debt_admission_boundary_exam": {
        "schema": "bilqis.mlx.debt-admission-boundary/v1",
        "student_sha256": school.current_student.sha256,
        "optimizer_step": school.current_student.optimizer_step,
        "cohort_sha256": cohort.digest,
        "cohort_file": cohort_file,
        "cohort_seed": cohort.seed,
        "exam_rubric_sha256": assessment_rubric_for_scope(course, full_scope),
        "assessment_scope_sha256": _fingerprint(full_scope),
        "source_exam_plane": "DEBT_ADMISSION_BOUNDARY",
        "scores": scores,
    }}
