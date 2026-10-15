"""Stable root npm/operator facade; intentionally no training entrypoint yet."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .disk import assert_headroom
from .source import AUDITED_PARENT
from .spiral_dashboard import Dashboard, TABLES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = ROOT / "runs" / "school-mlx-v1"


def _inspect(run_dir: Path) -> dict:
    state = run_dir / "state.json"
    if state.is_file():
        saved = json.loads(state.read_text(encoding="utf-8"))
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
                "native_mlx_full_optimizer_verified":False,
                "neural_training_started_by_this_command":False,
                "run_dir":str(run_dir)}
    return {"status":"NOT_PREPARED_CURRICULUM_REDESIGN",
            "grade":"A","phase":"GRADE_A_SOURCE_VALIDATION_HOLD",
            "historical_seed":AUDITED_PARENT.__dict__,
            "grade_a_draft":"SIX_SOURCE_TESTED_DIRECT_PREDICATES_NOT_ADMITTED",
            "native_mlx_full_optimizer_verified":False,
            "source_grounded_grade_a_admitted":False,
            "neural_training_started_by_this_command":False,
            "run_dir":str(run_dir)}


def _print_status(result: dict) -> int:
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def status(run_dir: Path):
    return _print_status(_inspect(run_dir))


def preflight(run_dir: Path, *, resume=False):
    existing = (run_dir / "state.json").is_file()
    if resume and not existing:
        raise ValueError("RESUME_EXPLICIT_BUT_NO_SAVED_NEW_SCHOOL_RUN")
    if not resume and existing:
        raise ValueError("NEW_RUN_WOULD_OVERWRITE_SAVED_SCHOOL_USE_RESUME")
    snapshot = _inspect(run_dir)
    snapshot.update({"result":"PREFLIGHT_ONLY_NO_NEURAL_UPDATES",
                     "start_behavior":"EXPLICIT_SAVED_STATE_RESUME" if resume else "GRADE_A_NEW_RUN",
                     "blockers":["NEW_GRADE_A_SOURCE_DRAFT_NOT_FINAL_CURRICULUM_ADMITTED",
                                 "FULL_STUDENT_MLX_OPTIMIZER_CONTINUATION_NOT_PROVEN",
                                 "NEW_CAPABILITY_RUBRIC_NOT_APPROVED",
                                 "HUMAN_ONLY_NEURAL_OPTIMIZER_UPDATES"]})
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
    d.push("system", {"kind":"MLX","detail":"Full model+AdamW parity unverified; no training"},redraw=False)
    d.push("system", {"kind":"CURRICULUM","detail":"Grade A source/typed-oracle admission pending"},redraw=False)
    d.push("system", {"kind":"MODE","detail":"Six inherited School50 panels, read-only"},redraw=False)
    d.rows["GRADES & MASTERY"].append({"visit":info.get("visits",0),
      "grade":info["grade"],"step":info.get("optimizer_step") or AUDITED_PARENT.optimizer_step,
      "eligible":"-","selected":"N","prefix":"A","outcome":"CURRICULUM HOLD",
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
            p.add_argument("--resume",action="store_true")
            p.add_argument("--triplets","--triples",dest="triples",action="store_true",
                           help="Global weakest-three recovery is intrinsic to the new scheduler")
    args=parser.parse_args(argv)
    try:
        if args.action=="status":return status(args.run_dir)
        if args.action=="dashboard":return dashboard(args.run_dir)
        if args.dry_run:return preflight(args.run_dir,resume=args.resume)
        # Hard stop even when a user requests train, until real backend/parity
        # and school curriculum admission are implemented and approved.
        print("TRAINING BLOCKED: source-grounded letter grades and complete native "
              "MLX model+own-AdamW parity are not yet certified. Use "
              "npm run train -- --dry-run to inspect safely.",file=sys.stderr)
        return 2
    except (ValueError,RuntimeError,OSError,KeyError,IndexError) as err:
        print("OPERATOR BLOCKED: "+str(err),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
