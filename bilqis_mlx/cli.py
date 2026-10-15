"""Human-facing MLX operator commands; live training still gated by proof."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .disk import assert_headroom
from .source import AUDITED_PARENT
from .grade_a_release import RELEASE as GRADE_A_RELEASE
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
                "visits": school["visits"],
                "optimizer_step": student["optimizer_step"],
                "checkpoint_sha256": student["sha256"],
                "champion_pointer_count": len(school["champions"]),
                "teacher_events": saved["teacher"]["events"],
                "teacher_strategy_count": len(saved["teacher"]["strategies"]),
                "last_exam": saved["last_exam"],
                "grade_a_release": GRADE_A_RELEASE,
                "source_grounded_grade_a_admitted": True,
                **_qualification_scope(),
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
            "grade_a_release": GRADE_A_RELEASE,
            "grade_a_curriculum": "SIX_USER_ACCEPTED_SOURCE_SEALED_PREDICATES_216_ITEMS",
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
    info = _inspect(run_dir)
    d = Dashboard(redraw=False, title="BILQIS / SCHOOL50 MLX | LETTER GRADES",
                  show_all_panels=True)
    d.mode = "READ-ONLY"
    d.grade_program=("A",)
    d.push("state", {"mastery":{"phase":info["phase"],"prefix":info["grade"],
                          "position":0}, "optimizer_step":info.get("optimizer_step") or
                          AUDITED_PARENT.optimizer_step,
                     "grade_visits":info.get("visits",0),
                     "last_run_status":info["status"]},redraw=False)
    d.push("system", {"kind":"SOURCE","detail":"Complete FP32 champion pinned by SHA, never copied"},redraw=False)
    d.push("system", {"kind":"MLX","detail":"Disposable full model+AdamW parity passed; live trainer not qualified"},redraw=False)
    d.push("system", {"kind":"CURRICULUM","detail":"Grade A accepted for human experimental training; broader NI awaits proof"},redraw=False)
    d.push("system", {"kind":"MODE","detail":"Six inherited School50 panels, read-only"},redraw=False)
    d.rows["GRADES & MASTERY"].append({"visit":info.get("visits",0),
      "grade":info["grade"],"step":info.get("optimizer_step") or AUDITED_PARENT.optimizer_step,
      "eligible":"-","selected":"N","prefix":"A","outcome":info["phase"],
      "right_pct":"-"})
    d.draw()
    return 0


def main(argv=None):
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
            p.add_argument("--max-visits",type=int,default=48,
                           help="Cap complete checkpoint generations in one command (0 disables cap)")
            p.add_argument("--batch-size",type=int,default=32)
            p.add_argument("--reserve-gib",type=float,default=100.)
            p.add_argument("--triplets","--triples",dest="triples",action="store_true",
                           help="Global weakest-three recovery is intrinsic to the new scheduler")
    args=parser.parse_args(argv)
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
        from .grade_a_trainer import operate
        return _print_status(operate(
            args.run_dir, LEGACY_ROOT, ORIGINAL_CHECKPOINT, GRADE_A_MANIFEST,
            resume=args.resume, minutes=args.minutes,
            steps_per_visit=args.steps_per_visit, max_visits=args.max_visits,
            batch_size=args.batch_size, reserve_gib=args.reserve_gib))
    except KeyboardInterrupt:
        print("HUMAN TRAINING INTERRUPTED: the last completed visit/checkpoint "
              "remains the resume point. Run npm run train -- --human-run --resume.",
              file=sys.stderr)
        return 130
    except (ValueError,RuntimeError,OSError,KeyError,IndexError) as err:
        print("OPERATOR BLOCKED: "+str(err),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
