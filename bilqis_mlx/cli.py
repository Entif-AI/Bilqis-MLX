"""Human-facing MLX operator commands; live training still gated by proof."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .disk import assert_headroom
from .source import AUDITED_PARENT
from .grade_a_release import RELEASE as GRADE_A_RELEASE
from .live_grade_a import RELEASE as LIVE_GRADE_A_RELEASE
from .live_grade_b import RELEASE as LIVE_GRADE_B_RELEASE
from .spiral_dashboard import Dashboard, TABLES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = ROOT / "runs" / "school-mlx-v1"
GRADE_A_MANIFEST = ROOT / "docs" / "GRADE_A_CANDIDATE_MANIFEST_V2.json"
LEGACY_ROOT = ROOT.parent / "bilqis-triplets-v16"
ORIGINAL_CHECKPOINT = (
    LEGACY_ROOT / "runs" / "primitive-consolidation-v16-triplets"
    / AUDITED_PARENT.basename
)


def _qualification_scope() -> dict:
    """Report prior evidence accurately without replaying neural steps."""
    return {
        "disposable_full_student_optimizer_continuation": {
            "status": "PREVIOUSLY_VERIFIED_CPU_AND_APPLE_GPU",
            "scope": "ONE_DETACHED_STEP_AND_COMPLETE_39_TENSOR_ADAMW_RESTART",
            "evidence": "docs/GRADE_A_REPAIR_AND_BACKEND_20261015.md",
            "recheck": "npm run mlx:qualify",
            "freshly_rerun_by_this_command": False,
        },
        "human_live_grade_a_trainer_end_to_end_qualified": False,
        "human_experimental_trainer_implemented": True,
        "operator_release": "HUMAN_EXPLICIT_--human-run_ONLY",
    }


def _latest_session_stop(run_dir: Path, generation: int, step: int) -> dict | None:
    """The append-only event ledger owns per-invocation stop reasons."""
    events = run_dir / "events.jsonl"
    if not events.is_file():
        return None
    lines = events.read_text(encoding="utf-8").splitlines()
    if not lines:
        return None
    event = json.loads(lines[-1])
    if (event.get("event") not in ("GRADE_A_SESSION_STOPPED", "SCHOOL_SESSION_STOPPED") or
            event.get("generation") != generation or
            event.get("optimizer_step") != step):
        return None
    return {"reason": event["stop_reason"],
            "visits_this_command": event["visits_this_command"],
            "elapsed_seconds": event["elapsed_seconds"],
            "time_limit_minutes": event["minutes"],
            "max_visits": event["max_visits"],
            "disk_free_gib": round(event["free_bytes"]/1024**3, 3)
                if "free_bytes" in event else None}


def _inspect(run_dir: Path) -> dict:
    state = run_dir / "state.json"
    if state.is_file():
        saved = json.loads(state.read_text(encoding="utf-8"))
        if saved.get("schema") == "bilqis.mlx.human-grade-a-trainer/v1":
            school = saved["school"]
            active = school["active_grades"]
            grade = active[school["grade_index"]]
            student = school["current_student"]
            return {
                "status": saved["result"],
                "grade": grade, "phase": school["stage"],
                "revalidation_target_grade": school.get("revalidation_target_grade"),
                "visits": school["visits"],
                "optimizer_step": student["optimizer_step"],
                "checkpoint_sha256": student["sha256"],
                "champion_pointer_count": len(school["champions"]),
                "capability_best_pointer_count": len(saved.get("capability_best", {})),
                "capability_best_bundle_count": len({
                    item["checkpoint"]["sha256"]
                    for item in saved.get("capability_best", {}).values()}),
                "teacher_events": saved["teacher"]["events"],
                "teacher_strategy_count": len(saved["teacher"]["strategies"]),
                "last_exam": saved["last_exam"],
                "last_session_stop": _latest_session_stop(
                    run_dir, saved["generation"], student["optimizer_step"]),
                "grade_a_release": LIVE_GRADE_A_RELEASE if saved.get("curriculum_mode") == LIVE_GRADE_B_RELEASE else saved.get("curriculum_mode") or GRADE_A_RELEASE,
                "historical_source_release": GRADE_A_RELEASE,
                "grade_a_curriculum_mode": (LIVE_GRADE_A_RELEASE if saved.get("curriculum_mode") == LIVE_GRADE_B_RELEASE
                                             else saved.get("curriculum_mode", "HISTORICAL_FIXED_72")),
                "grade_b_curriculum_mode": LIVE_GRADE_B_RELEASE if saved.get("curriculum_mode") == LIVE_GRADE_B_RELEASE else None,
                "grade_b_source_admitted": saved.get("curriculum_mode") == LIVE_GRADE_B_RELEASE,
                "assessment_cohort_sha256": (saved.get("last_exam") or {}).get("cohort_sha256"),
                "source_grounded_grade_a_admitted": True,
                **_qualification_scope(),
                "human_live_grade_a_trainer_end_to_end_qualified": "A" in school["champions"],
                "neural_training_started_by_this_command": False,
                "run_dir": str(run_dir),
            }
        if saved.get("schema") != "bilqis.mlx.letter-grade/v1":
            raise ValueError("UNRECOGNIZED_SCHOOL_RUN_SCHEMA")
        grade_index = saved.get("grade_index", 0)
        active_grades = saved.get("active_grades") or []
        grade = active_grades[grade_index] if 0 <= grade_index < len(active_grades) else "INVALID"
        return {"status":"PREPARED_SOURCE_STATE_READ_ONLY",
                "grade":grade,"phase":saved.get("stage"),
                "revalidation_target_grade":saved.get("revalidation_target_grade"),
                "visits":saved.get("visits",0),
                "optimizer_step":(saved.get("current_student") or {}).get("optimizer_step"),
                "checkpoint_sha256":(saved.get("current_student") or {}).get("sha256"),
                "champion_pointer_count":len(saved.get("champions") or {}),
                **_qualification_scope(),
                "neural_training_started_by_this_command":False,
                "run_dir":str(run_dir)}
    return {"status":"GRADE_A_EXPERIMENTAL_HUMAN_LAUNCH_AVAILABLE",
            "grade":"A","phase":"READY_FOR_HUMAN_GRADE_A_START",
            "historical_seed":AUDITED_PARENT.__dict__,
            "grade_a_release": LIVE_GRADE_A_RELEASE,
            "historical_source_release": GRADE_A_RELEASE,
            "grade_a_curriculum": "SIX_SOURCE_TYPED_PREDICATES_FRESH_GENERATED_COHORTS",
            "grade_a_curriculum_mode": LIVE_GRADE_A_RELEASE,
            **_qualification_scope(),
            "source_grounded_grade_a_admitted":True,
            "neural_training_started_by_this_command":False,
            "run_dir":str(run_dir)}


def _print_status(result: dict) -> int:
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def status(run_dir: Path):
    return _print_status(_inspect(run_dir))


def preflight(run_dir: Path, *, resume=False, verify_source=False):
    existing = (run_dir / "state.json").is_file()
    if resume and not existing:
        raise ValueError("RESUME_EXPLICIT_BUT_NO_SAVED_NEW_SCHOOL_RUN")
    if not resume and existing:
        raise ValueError("NEW_RUN_WOULD_OVERWRITE_SAVED_SCHOOL_USE_RESUME")
    snapshot = _inspect(run_dir)
    snapshot.update({"result":"PREFLIGHT_ONLY_NO_NEURAL_UPDATES",
                     "start_behavior":"EXPLICIT_SAVED_STATE_RESUME" if resume else "GRADE_A_NEW_RUN",
                     "blockers":[],
                     "experimental_risks":["FIRST_HUMAN_RUN_NOT_YET_OBSERVED",
                                           "FULL_NEW_ITHKUIL_MORPHOLOGY_NOT_YET_CERTIFIED"],
                     "operator_constraint":"HUMAN_ONLY_NEURAL_OPTIMIZER_UPDATES"})
    if resume and snapshot.get("phase") == "AWAITING_NEXT_GRADE" and snapshot.get("grade") == "A":
        # Announce the actual next semantic release before the human operates.
        # This compiles/verifies source only; no checkpoint is opened for edits.
        from .grade_a_release import accepted_grade_a
        from .live_grade_a import live_course as admitted_a
        from .live_grade_b import live_course as admitted_b
        manifest = json.loads(GRADE_A_MANIFEST.read_text(encoding="utf-8"))
        next_course = admitted_b(admitted_a(accepted_grade_a(manifest)),LEGACY_ROOT)
        snapshot["start_behavior"] = "HUMAN_RESUME_ADMIT_B_FROM_MASTERY_A"
        snapshot["next_grade"] = "B"
        snapshot["next_grade_source_checked"] = next_course.executable
        snapshot["next_grade_rubric_sha256"] = next_course.grades[-1].assessment_sha256
        snapshot["next_grade_complete_assessment_items"] = sum(
            count for grade in next_course.grades for _, count in grade.exam_item_counts)
        snapshot["experimental_risks"] = [
            "GRADE_B_REAL_STUDENT_CONVERGENCE_NOT_YET_OBSERVED",
            "FULL_NEW_ITHKUIL_MORPHOLOGY_NOT_YET_CERTIFIED"]
    snapshot["grade_a_source_manifest"] = "docs/GRADE_A_CANDIDATE_MANIFEST_V2.json"
    if verify_source:
        from .grade_a_manifest import verify_manifest
        source = json.loads(GRADE_A_MANIFEST.read_text(encoding="utf-8"))
        receipt = verify_manifest(source, LEGACY_ROOT, ORIGINAL_CHECKPOINT)
        snapshot["source_manifest_preflight"] = {
            "status": "PINNED_HISTORICAL_SOURCE_VERIFIED",
            "verified_items": receipt["verified_items"],
            "exam_rubric_sha256": receipt["exam_rubric_sha256"],
            "original_candidate_manifest_release_flag": False,
            "grade_a_user_acceptance_is_separate": True,
        }
    else:
        snapshot["source_manifest_preflight"] = "NOT_RERUN_USE_--verify-source"
    # The source remains unchanged. This probes only current disk headroom.
    snapshot["disk"] = assert_headroom(ROOT, required_bytes=0)
    return _print_status(snapshot)


def dashboard(run_dir: Path):
    from .grade_a_dashboard import render
    render(run_dir)
    return 0


def human_stop_summary(result: dict) -> str:
    """A legible termination receipt for the human-operated live terminal."""
    explanations = {
        "TIME_LIMIT_REACHED": "The requested time budget was reached.",
        "VISIT_LIMIT_REACHED": "The explicitly configured --max-visits cap was reached.",
        "GRADE_A_AWAITING_NEXT_GRADE": "Grade A is mastered; the admitted Grade B starts when the human operator resumes.",
        "GRADE_B_AWAITING_NEXT_GRADE": "Grades A and B passed cumulative revalidation; awaiting Grade C admission.",
        "WHOLE_SCHOOL_MASTERED": "Every grade in the explicitly complete school program passed at one whole student.",
        "AWAITING_TEACHER_SOUP": "Whole-school consolidation requires a separately verified frozen teacher-soup continuation.",
        "DISK_RESERVE_REACHED": "Free space cannot cover the protected disk reserve plus another checkpoint.",
    }
    reason = result["stop_reason"]
    message = ("TRAINING STOPPED NORMALLY: " + reason + "\n" +
               explanations[reason] +
               f" Completed {result['visits_this_command']} visits in "
               f"{result['elapsed_seconds']:.1f} seconds, "
               f"optimizer step {result['optimizer_step']}.")
    if reason == "DISK_RESERVE_REACHED":
        message += (f"\nDisk: {result['disk_free_gib']:.2f} GiB free, "
                    f"{result['disk_reserve_gib']:.1f} GiB reserve + "
                    f"{result['disk_next_visit_gib']:.2f} GiB estimated next checkpoint. "
                    "No checkpoint cleanup or reserve reduction was performed.")
    if reason not in ("GRADE_A_AWAITING_NEXT_GRADE", "GRADE_B_AWAITING_NEXT_GRADE",
                      "WHOLE_SCHOOL_MASTERED", "AWAITING_TEACHER_SOUP"):
        message += "\nTo continue: npm run train -- --human-run --resume --minutes 90"
    return message + "\nHistorical dashboard: npm run dashboard"


def parse_args(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_subparsers(dest="action",required=True)
    for name in ("status","dashboard","train"):
        p=actions.add_parser(name)
        p.add_argument("--run-dir",type=Path,default=DEFAULT_RUN)
        if name=="train":
            p.add_argument("--dry-run",action="store_true")
            p.add_argument("--verify-source",action="store_true",
                           help="Recheck all 216 candidate records against the pinned source (neural-inert)")
            p.add_argument("--resume",action="store_true")
            p.add_argument("--human-run",action="store_true",
                           help="Explicitly authorizes actual optimizer steps by the human operator")
            p.add_argument("--minutes",type=int,default=90)
            p.add_argument("--steps-per-visit",type=int,default=16)
            p.add_argument("--max-visits",type=int,default=0,
                           help="Optional complete visit cap (default 0: use --minutes and disk reserve)")
            p.add_argument("--batch-size",type=int,default=32)
            p.add_argument("--reserve-gib",type=float,default=100.)
            p.add_argument("--triplets","--triples",dest="triples",action="store_true",
                           help="Global weakest-three recovery is intrinsic to the new scheduler")
    return parser.parse_args(argv)


def main(argv=None):
    args=parse_args(argv)
    try:
        if args.action=="status":return status(args.run_dir)
        if args.action=="dashboard":return dashboard(args.run_dir)
        if args.dry_run:return preflight(args.run_dir,resume=args.resume,
                                        verify_source=args.verify_source)
        if args.verify_source:
            raise ValueError("VERIFY_SOURCE_REQUIRES_DRY_RUN")
        if not args.human_run:
            print("TRAINING REQUIRES EXPLICIT HUMAN OPERATOR: add --human-run; "
                  "agents may run only --dry-run and tests. "
                  "Use npm run train -- --dry-run for preflight.",file=sys.stderr)
            return 2
        from .grade_a_trainer import operate, operator_view
        from .grade_a_dashboard import build, ingest
        # Interactive training owns the dashboard in its *own* terminal.
        # Non-TTY operators continue to receive machine-readable events.
        visual = sys.stdout.isatty()
        board = build(args.run_dir, reserve_gib=args.reserve_gib) if visual else None
        def on_event(event):
            ingest(board, event)
            board.mode = "LIVE"
            board.draw()
        if board is not None:
            board.draw()
        with operator_view(on_event if visual else None):
            result = operate(
                args.run_dir, LEGACY_ROOT, ORIGINAL_CHECKPOINT, GRADE_A_MANIFEST,
                resume=args.resume, minutes=args.minutes,
                steps_per_visit=args.steps_per_visit, max_visits=args.max_visits,
                batch_size=args.batch_size, reserve_gib=args.reserve_gib)
        if board is not None:
            board = build(args.run_dir, reserve_gib=args.reserve_gib)
            board.mode = "STOPPED | " + result["stop_reason"]
            board.draw()
            print("\n" + human_stop_summary(result), flush=True)
            return 0
        return _print_status(result)
    except KeyboardInterrupt:
        print("HUMAN TRAINING INTERRUPTED: the last completed visit/checkpoint "
              "remains the resume point. Run npm run train -- --human-run --resume.",
              file=sys.stderr)
        return 130
    except (ValueError,RuntimeError,OSError,KeyError,IndexError) as err:
        print("OPERATOR BLOCKED: "+str(err),file=sys.stderr)
        if "HUMAN_TRAINER_NEW_RUN_HAS_EXISTING_CONTENT" in str(err):
            print("Saved school exists. To continue it, use: "
                  "npm run train -- --human-run --resume --minutes 90", file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
