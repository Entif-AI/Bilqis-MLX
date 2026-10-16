"""Read-only School50 adapter for the legacy Grade A and future school events.

The six panels use a grade-neutral telemetry contract. This module does not
score exams, influence teacher rewards, or touch neural state and checkpoints.
"""
from __future__ import annotations

import json
from pathlib import Path

from .school_telemetry import SchoolTelemetry, LETTER_TABLES
from .disk import headroom_snapshot
from .source import AUDITED_PARENT
from .live_grade_a import RELEASE as LIVE_GRADE_A_RELEASE
from .live_grade_b import RELEASE as LIVE_GRADE_B_RELEASE
from .live_grade_c import RELEASE as LIVE_GRADE_C_RELEASE
from .spiral_dashboard import Dashboard


def build(run_dir: Path, *, stream=None, reserve_gib: float = 100.) -> Dashboard:
    run_dir = Path(run_dir)
    board = Dashboard(stream=stream, redraw=False,
                      title="BILQIS / SCHOOL50 MLX | LETTER GRADES",
                      show_all_panels=True, tables=LETTER_TABLES)
    board.mode = "READ-ONLY"
    state_path = run_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None
    school = state["school"] if state else {}
    step = school.get("current_student", {}).get("optimizer_step", AUDITED_PARENT.optimizer_step)
    visits = school.get("visits", 0)
    phase = school.get("stage", "READY_FOR_HUMAN_GRADE_A_START")
    active = school.get("active_grades", ("A",))
    grade_index = school.get("grade_index", 0)
    current_grade = active[grade_index] if 0 <= grade_index < len(active) else active[0]
    board.push("state", {"mastery": {"phase": phase, "prefix": current_grade, "position": 0},
                         "optimizer_step": step, "grade_visits": visits,
                         "teacher": state.get("teacher") if state else None,
                         "last_run_status": state.get("result", "NOT_STARTED") if state else "NOT_STARTED"},
               redraw=False)
    board.school_telemetry = SchoolTelemetry(board, active_grades=active,
                                              champions=school.get("champions"))
    budget = headroom_snapshot(run_dir, required_bytes=600_000_000,
                               reserve_gib=reserve_gib)
    ingest(board, {"event": "SCHOOL_RESOURCE_OBSERVED",
                  "grade": current_grade, **{k: budget[k] for k in
                  ("free_bytes", "reserve_bytes", "estimated_write_bytes")}})
    board.push("system", {"kind": "SOURCE", "detail": "Source-bound FP32 + own AdamW | immutable receipts"}, redraw=False)
    is_b = bool(state and state.get("curriculum_mode") == LIVE_GRADE_B_RELEASE)
    is_c = bool(state and state.get("curriculum_mode") == LIVE_GRADE_C_RELEASE)
    live = not state or state.get("curriculum_mode") in (LIVE_GRADE_A_RELEASE, LIVE_GRADE_B_RELEASE, LIVE_GRADE_C_RELEASE)
    board.push("system", {"kind": "RUBRIC", "detail":
               ("Grades A+B+C: fixed enrollment exam; introduced stages only until full cumulative 100%"
                if is_c else "Grades A+B: generated 144 source-oracled items; same-checkpoint cumulative 100%"
                if is_b else "Grade A: generated 72 source-oracled items per cohort; 100% one checkpoint"
                if live else "Historical Grade A frozen 72-item rubric; 100% one checkpoint")},
               redraw=False)
    if live and state and (state.get("last_exam") or {}).get("cohort_sha256"):
        exam = state["last_exam"]
        board.push("system", {"kind": "COHORT", "detail":
                   f"Seed {exam['cohort_seed']} | SHA {exam['cohort_sha256'][:16]} | "
                   f"rubric {exam['exam_rubric_sha256'][:12]}"}, redraw=False)
    board.push("system", {"kind": "METRIC", "detail":
               "NOT MEASURED: independent sentinel/CE/P(C)/margin; "
               "frozen soups advise training only, never examination scoring"},
               redraw=False)
    if state and state.get("grade_soups"):
        from .grade_soup import soup_vote_count
        for grade, soup in sorted(state["grade_soups"].items()):
            effective = soup_vote_count(soup, current_grade, len(active))
            board.push("system", {"kind": "GRADE SOUP", "grade": grade,
                       "detail": (f"Frozen {grade} recipe: "
                                  f"{soup['vote_count']} mastered capability votes; "
                                  f"{effective:.2f} votes for {current_grade} lessons | "
                                  f"SHA {soup['sha256'][:12]}")}, redraw=False)
    if state and state.get("capability_best"):
        bests = state["capability_best"]
        for item in sorted(bests.values(), key=lambda x: x["capability"]):
            model = item["checkpoint"]
            board.push("system", {"kind": "CAP BEST", "grade": item["capability"].split(".")[0],
                        "detail": (f"{item['capability']} {item['correct']}/{item['total']} "
                                   f"at step {model['optimizer_step']} | {model['sha256'][:10]}")},
                       redraw=False)
    board.push("system", {"kind": "RESTART", "detail": "Saved run: train --human-run --resume"}, redraw=False)
    board.log_hint = str(run_dir / "events.jsonl")
    events = run_dir / "events.jsonl"
    if events.exists():
        # Bounded visual history, streaming replay: no whole-log materialization
        # as the school eventually expands through many letter grades.
        with events.open(encoding="utf-8") as log:
            for line in log:
                if line.strip():
                    try:
                        ingest(board, json.loads(line))
                    except (ValueError, TypeError, KeyError) as exc:
                        board.push("system", {"kind": "LOG", "detail":
                                   f"Invalid telemetry event ignored: {str(exc)[:62]}"}, redraw=False)
    if not board.rows["GRADES & MASTERY"]:
        board.rows["GRADES & MASTERY"].append({"grade": active[0], "step": step,
                 "first": "-", "latest": "-", "best": "-", "to100": "-",
                 "right_pct": "-", "outcome": phase})
    return board


def ingest(board: Dashboard, event: dict) -> None:
    """Incrementally update the same renderer used by past/future grades."""
    board.school_telemetry.ingest(event)


def render(run_dir: Path, *, stream=None) -> None:
    build(run_dir, stream=stream).draw()
