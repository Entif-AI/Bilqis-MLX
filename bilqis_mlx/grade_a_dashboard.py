"""Neural-inert live and historical School50 view for the Grade A event ledger."""
from __future__ import annotations

import json
from pathlib import Path

from .spiral_dashboard import Dashboard
from .source import AUDITED_PARENT


def build(run_dir: Path, *, stream=None) -> Dashboard:
    run_dir = Path(run_dir)
    board = Dashboard(stream=stream, redraw=False,
                      title="BILQIS / SCHOOL50 MLX | LETTER GRADES",
                      show_all_panels=True)
    board.grade_program = ("A",)
    board.mode = "READ-ONLY"
    state_path = run_dir / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else None
    school = state["school"] if state else {}
    step = school.get("current_student", {}).get("optimizer_step", AUDITED_PARENT.optimizer_step)
    visits = school.get("visits", 0)
    phase = school.get("stage", "READY_FOR_HUMAN_GRADE_A_START")
    board.push("state", {"mastery": {"phase": phase, "prefix": "A", "position": 0},
                         "optimizer_step": step, "grade_visits": visits,
                         "teacher": state.get("teacher") if state else None,
                         "last_run_status": state.get("result", "NOT_STARTED") if state else "NOT_STARTED"},
               redraw=False)
    board.push("system", {"kind": "SOURCE", "detail": "Original FP32 + own AdamW retained"}, redraw=False)
    board.push("system", {"kind": "SCHOOL", "detail": "Accepted Grade A | 72 sealed exam items"}, redraw=False)
    board.push("system", {"kind": "RESTART", "detail": "Existing run: train --human-run --resume"}, redraw=False)
    board.log_hint = str(run_dir / "events.jsonl")
    events = run_dir / "events.jsonl"
    if events.exists():
        for line in events.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    ingest(board, json.loads(line))
                except (ValueError, TypeError, KeyError):
                    board.push("system", {"kind": "LOG", "detail": "Invalid event ignored"}, redraw=False)
    if not board.rows["GRADES & MASTERY"]:
        board.push("grade", {"grade": "A", "grade_visit": visits, "step": step,
                             "prefix": "A", "outcome": phase}, redraw=False)
    return board


def ingest(board: Dashboard, event: dict) -> None:
    kind = event.get("event")
    if kind == "GRADE_A_TEACHER_VISIT_COMMITTED":
        before = event.get("source_training_accuracy_before")
        after = event.get("source_training_accuracy_after")
        board.push("candidate", {"grade": event["capability"],
                   "attempt": event["generation"], "policy_id": event.get("teacher_policy", ""),
                   "reward": event.get("teacher_reward"), "decision": "LESSON COMMITTED",
                   "reason": f"training {before:.0%}->{after:.0%}"}, redraw=False)
        board.push("grade", {"grade": "A", "grade_visit": event["generation"],
                   "step": event["optimizer_step"], "prefix": "A",
                   "outcome": event["capability"] + " lesson; exam pending"}, redraw=False)
        board.state.update(step=event["optimizer_step"], visits=event["generation"] - 1,
                           phase=event.get("next_phase", "MAIN"))
    elif kind == "GRADE_A_EXAM_COMMITTED":
        scores = event["scores"]
        total = sum(v["total"] for v in scores.values())
        correct = sum(v["correct"] for v in scores.values())
        board.push("grade", {"grade": "A", "grade_visit": event["generation"],
                   "step": board.state.get("step"), "prefix": "A",
                   "outcome": f"SEALED EXAM {correct}/{total} | {event['phase']}",
                   "accuracy": 100 * correct / total}, redraw=False)
        for cap, score in sorted(scores.items()):
            board.rows["BRIDGE FAMILIES"].append({"grade": "A", "attempt": event["generation"],
                     "family": cap, "before": "sealed exam", "after": f"{score['correct']}/{score['total']}",
                     "gain": "-"})
        board.state["phase"] = event["phase"]
    elif kind == "GRADE_A_SESSION_STOPPED":
        reason = event["stop_reason"]
        board.mode = "STOPPED | " + reason
        board.push("system", {
            "kind": "STOP",
            "detail": f"{reason} | {event['visits_this_command']} visits | "
                      f"{event['elapsed_seconds']:.1f}s | step {event['optimizer_step']}",
        }, redraw=False)
        board.state["last_run_status"] = reason


def render(run_dir: Path, *, stream=None) -> None:
    build(run_dir, stream=stream).draw()
