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
    from ..state_dag import read_generation
    pre = read_generation(run_dir, admission["generation"] - 1)
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
    from bilqis_mlx.learning.student_ops import _predictions


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


def recover_legacy_frontier(mx, run_dir, receipt):
    """Read and validate the historical source exam; runtime owns application."""
    from .live_releases import NUMERIC_RELEASE
    if receipt.get("curriculum_mode") != NUMERIC_RELEASE:
        return None
    return _recover_grade_c_boundary_source(mx, run_dir, receipt)
