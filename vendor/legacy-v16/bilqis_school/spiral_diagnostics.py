"""Optional School50 operator console, deliberately excluded from training recipe.

`--watch` reads the durable state of an already-running v4 trainer, printing
candidate and grade evidence after each saved grade boundary. `train` wraps
the unchanged runner and observes candidate decisions as they occur. Neither
mode writes to the student, optimizer, teacher, source history or run state.
"""
from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path
import sys
import time


DEFAULT_RUN = Path(__file__).resolve().parents[1] / "runs/school50-cumulative-numeric-spiral-v4"
CYCLE = tuple(f"M{i:02d}" for i in range(1, 9)) + tuple(f"G{i:02d}" for i in range(1, 23))
TERMINAL = {"EXPLICIT_COMPLETE_PASS_CAP", "EXPLICIT_GRADE_VISIT_CAP",
            "GRACEFUL_OPERATOR_STOP", "TIME_BUDGET_EXHAUSTED",
            "ATTEMPTED_UPDATE_SAFETY_CAP", "STORAGE_RESERVE_PAUSE",
            "NO_HOLISTIC_OR_NUMERIC_PROGRESS_AFTER_REPEATED_PASSES"}


def _percent(number):
    return "n/a" if number is None else f"{100 * number:.1f}%"


def _delta(number):
    return "n/a" if number is None else f"{100 * number:+.1f}pp"


def _number(number, digits=4):
    return "n/a" if number is None else f"{number:+.{digits}f}"


def _mean(scores):
    return sum(scores.values()) / len(scores) if scores else None


def _soup(record):
    measurements = record.get("loss_last") or {}
    allocation = record.get("allocation") or {}
    batch_size = sum(n for n in allocation.values() if isinstance(n, int))
    correct = measurements.get("trusted_soup_rows")
    coverage = (f"{100*correct/batch_size:.1f}% ({correct}/{batch_size})"
                if isinstance(correct, int) and batch_size else "n/a")
    def metric(key):
        val = measurements.get(key)
        return f"{val:.4f}" if isinstance(val, (float,int)) else "n/a"
    return (f"soup KL={metric('soup_kl')} "
            f"cov={coverage} supervised CE={metric('supervised')} "
            f"parent KL={metric('parent_kl')}")


def _correct_change(before, after, label):
    if not before or not after:
        return ""
    old, new = before.get("correct"), after.get("correct")
    total = after.get("questions", before.get("questions", "?"))
    if old is None or new is None:
        return ""
    return (f"{label} {old}/{total}->{new}/{total} ({new-old:+d}) "
            f"CE {before.get('ce',float('nan')):.3f}->{after.get('ce',float('nan')):.3f}")


def _sentinel(record):
    old, new = record.get("sentinel_before"), record.get("sentinel_after")
    if not old or not new:
        return "sentinel not sampled"
    fields = (("accuracy", "acc", True), ("cross_entropy", "CE", False),
              ("correct_probability", "p(correct)", False),
              ("margin", "margin", False))
    return "sentinel " + " ".join(
        f"{label} {_delta(new[key]-old[key]) if percent else _number(new[key]-old[key])}"
        for key, label, percent in fields if key in old and key in new)


def _families(before, after):
    if not before or not after:
        return ""
    parts = []
    for name, current in after.get("by_family", {}).items():
        original = before.get("by_family", {}).get(name)
        if original and "correct" in original and "correct" in current:
            parts.append(f"{name} {original['correct']}->{current['correct']}/{current['questions']}")
    return ", ".join(parts)


def candidate_line(record, attempts=None, *, elapsed=None):
    """Render actual candidate record fields, never assume sentinel was used."""
    grade = record["grade"]
    maximum = attempts if attempts is not None else "?"
    title = (f"[candidate] pass {record['pass']} {grade} attempt "
             f"{record['attempt']}/{maximum} strategy {record.get('policy_id','?')}")
    if record.get("instruction_method"):
        title += f" method={record['instruction_method']}"
    segments = [title]
    if elapsed is not None:
        segments.append(f"elapsed={elapsed / 60:.1f}m")
    before, after = record.get("old_before") or {}, record.get("old_after") or {}
    if grade.startswith("G") and grade in before and grade in after:
        segments.append(f"probe {_percent(before[grade])}->{_percent(after[grade])} "
                        f"({_delta(after[grade]-before[grade])})")
    elif record.get("numeric_before") and record.get("numeric_after"):
        segments.append(_correct_change(record["numeric_before"],
                                        record["numeric_after"], "number"))
        segments.append(f"output diversity {record['numeric_before'].get('distinct_predictions','?')}"
                        f"->{record['numeric_after'].get('distinct_predictions','?')}")
    if before and after:
        delta = _mean(after) - _mean(before)
        worst = min(after[key]-before[key] for key in before)
        segments.append(f"old22 avg {_delta(delta)} worst {_delta(worst)}")
    if record.get("bridge_before") and record.get("bridge_after"):
        segments.append(_correct_change(record["bridge_before"],
                                        record["bridge_after"],
                                        f"bridge {record.get('bridge_grade','?')}"))
        parts = _families(record["bridge_before"], record["bridge_after"])
        if parts:
            segments.append(f"families [{parts}]")
    segments.append(f"reward {_number(record.get('reward'))} "
                    f"teacher-credit {_number(record.get('teacher_credit'))}")
    segments.append(_sentinel(record))
    segments.append(_soup(record))
    verdict = record.get("decision", "?")
    reason = record.get("reason", "unspecified")
    selection = record.get("selection")
    if verdict == "ELIGIBLE" and selection is None:
        verdict = "ELIGIBLE (winner pending)"
    elif selection in ("SELECTED", "ELIGIBLE_SUPERSEDED"):
        verdict += f" {selection}"
    segments.append(f"{verdict} {reason}")
    return " | ".join(segment for segment in segments if segment)


def grade_line(visit, attempts, state, *, elapsed=None, pending=False):
    grade, number = visit["grade"], visit["pass"]
    selected = next((r for r in attempts if r.get("selection") == "SELECTED"), None)
    prior = attempts[0] if attempts else None
    active = selected or prior
    parent_step=attempts[0].get("parent_step","?") if attempts else "?"
    step=(visit['selected']['step'] if visit.get('selected') else parent_step)
    parts = [f"[grade] pass {number} {grade} step {step}"]
    if elapsed is not None:
        parts.append(f"elapsed {elapsed/60:.1f}m")
    if active:
        before = active.get("old_before") or {}
        after = (active.get("old_after") if selected else before) or {}
        if grade in before:
            parts.append(f"probe {_percent(before[grade])}->{_percent(after[grade])} "
                         f"({_delta(after[grade]-before[grade])})")
        if before:
            parts.append(f"old22 {_delta(_mean(after)-_mean(before))}")
        if grade.startswith("M") and active.get("numeric_before"):
            end = active.get("numeric_after") if selected else active["numeric_before"]
            parts.append(_correct_change(active["numeric_before"],end,"number"))
        if active.get("bridge_before"):
            end = active.get("bridge_after") if selected else active["bridge_before"]
            parts.append(_correct_change(active["bridge_before"],end,"bridge"))
    winner_label=(f"SELECTED attempt {selected['attempt']} (checkpoint pending)"
                  if pending and selected else
                  f"PROMOTED attempt {selected['attempt']}" if selected else
                  "NO_CANDIDATE_PROMOTED")
    parts.append(f"gate {winner_label} "
                 f"{visit.get('eligible',0)}/{visit.get('candidate_attempts',len(attempts))} eligible")
    teacher = state.get("teacher", {})
    if teacher:
        parts.append(f"teacher {len(teacher.get('strategies',[]))} strategies/"
                     f"{teacher.get('mutations','?')} mutations/"
                     f"{visit.get('teacher_events',teacher.get('events','?'))} events")
    if attempts:
        parts.append(_soup(attempts[-1]))
    parts.append(f"stalled {state.get('stalled_passes',0)} complete passes")
    return " | ".join(parts)


def pass_lines(report, state):
    old = report.get("old_22_scores") or {}
    if not old:
        return [f"=== PASS {report.get('pass','?')} {report.get('decision','?')} ==="]
    scores = sorted(old.items(), key=lambda x: x[1])
    values = [value for _, value in scores]
    middle = len(values) // 2
    median = (values[middle-1]+values[middle])/2
    previous = state.get("source_scores_mean")
    header = (f"=== PASS {report['pass']} REPORT | mean {_percent(_mean(old))} | "
              f"median {_percent(median)} | vs P43 {_delta(_mean(old)-previous) if previous is not None else 'n/a'} "
              f"| >=90% {sum(x >= .9 for x in values)}/{len(values)} "
              f"| 100% {sum(x == 1 for x in values)}/{len(values)} "
              f"| low {scores[0][0]} {_percent(scores[0][1])} "
              f"| high {scores[-1][0]} {_percent(scores[-1][1])} "
              f"| {report['decision']} {report['reason']} "
              f"| vs champion {_number(report.get('old_22_delta_pp'),3)}pp "
              f"| worst {_number(report.get('old_22_worst_delta_pp'),3)}pp ===")
    details = (f"[pass-transfer] numeric {report.get('numeric_correct','?')}/144 "
               f"(vs P43 {report.get('numeric_net_gain',0):+d}) "
               f"| bridge {report.get('bridge_correct','?')}/192 "
               f"(vs P43 {report.get('bridge_net_gain',0):+d}) "
               f"| optimizer step {report.get('attempted_optimizer_step','?')} "
               f"| teacher events {report.get('teacher_events_preserved','?')} "
               f"| mutations {report.get('teacher_mutations_preserved','?')}")
    families = {}
    for item in (report.get("bridge_development") or {}).values():
        for name, performance in item.get("by_family", {}).items():
            current = families.setdefault(name,[0,0])
            current[0] += performance["correct"]
            current[1] += performance["questions"]
    by_family = ("[pass-bridge] " + " | ".join(
        f"{name} {correct}/{count} ({100*correct/count:.1f}%)"
        for name, (correct,count) in families.items())) if families else ""
    return [line for line in (header, details, by_family) if line]


def report_new_visits(state, start):
    """Pure ledger renderer: one candidate appears exactly once per saved visit."""
    grades = state.get("grade_ledger") or []
    candidates = state.get("candidate_ledger") or []
    index = sum(int(visit.get("candidate_attempts",0)) for visit in grades[:start])
    lines = []
    for visit in grades[start:]:
        end = index + visit.get("candidate_attempts",0)
        subset = candidates[index:end]
        if len(subset) != visit.get("candidate_attempts",0):
            raise ValueError("DIAGNOSTICS_PARTIAL_CANDIDATE_LEDGER")
        for candidate in subset:
            lines.append(candidate_line(candidate, visit["candidate_attempts"]))
        lines.append(grade_line(visit,subset,state))
        if visit["grade"] == "G22":
            report = next((p for p in state.get("pass_reports",[])
                           if p.get("pass")==visit["pass"]),None)
            if report is not None:
                lines.extend(pass_lines(report,state))
        index=end
    return len(grades), lines


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def watch(run_dir, *, tail=3, interval=1.5, heartbeat=30.0, follow=False):
    """Observer attaches to current training without opening a writer lock."""
    path = Path(run_dir).expanduser() / "state.json"
    cursor = None
    last_signature = None
    last_notice = time.monotonic()
    print(f"[diagnostics] READ ONLY: {path}",flush=True)
    try:
        while True:
            try:
                st = path.stat()
                signature = (st.st_mtime_ns,st.st_size)
                if signature != last_signature:
                    state = _read(path)
                    last_signature = signature
                    if cursor is None:
                        cursor = max(0,len(state.get("grade_ledger",[]))-tail)
                    cursor, lines = report_new_visits(state,cursor)
                    for line in lines:
                        print(line,flush=True)
                    if lines:
                        last_notice = time.monotonic()
                    if not follow:
                        break
                    if state.get("last_run_status") in TERMINAL:
                        print(f"[diagnostics] Trainer stopped: {state['last_run_status']}",flush=True)
                        break
                if not follow:
                    break
                if time.monotonic()-last_notice>=heartbeat:
                    print(f"[diagnostics] waiting for next saved grade boundary; "
                          f"next={CYCLE[state['cycle_index']] if 'state' in locals() else '?'} "
                          "(individual attempts are not persisted mid-grade)",flush=True)
                    last_notice=time.monotonic()
            except (FileNotFoundError,json.JSONDecodeError):
                if not follow:
                    raise
            time.sleep(interval)
    except KeyboardInterrupt:
        print("[diagnostics] Monitor detached; trainer unaffected.",flush=True)


def train_with_live_diagnostics(args):
    """Non-recipe instrumentation; invoke exactly the same runner.main()."""
    from . import engine, spiral_numeric_runner as runner

    original_observe = engine.observe
    original_visit = runner._visit
    original_finish = runner._finish_spiral_pass
    started = time.monotonic()
    visit_started = started

    def observed_teacher(*items, **kwargs):
        caller = inspect.currentframe().f_back
        result = original_observe(*items, **kwargs)
        if caller.f_code is original_visit.__code__:
            try:
                data = caller.f_locals
                report = {"grade":data["grade"],
                          "pass":data["state"]["completed_passes"]+1,
                          "attempt":data["attempt"],"policy_id":data["key"],
                          "instruction_method":data.get("method"),
                          "old_before":data["old_before"],"old_after":data["old_after"],
                          "numeric_before":data.get("math_before"),
                          "numeric_after":data.get("math_after"),
                          "bridge_grade":data["target_bridge_grade"],
                          "bridge_before":data["bridge_before"],
                          "bridge_after":data["bridge_after"],
                          "reward":data["reward"],"teacher_credit":data["teacher_credit"],
                          "sentinel_before":data.get("sentinel_before"),
                          "sentinel_after":data.get("sentinel_after"),
                          "loss_last":data["traces"][-1],
                          "allocation":data["exposures"][0],
                          "decision":data["decision"],"reason":data["reason"]}
                print(candidate_line(report,data["state"]["config"]["attempts"],
                                     elapsed=time.monotonic()-started),flush=True)
            except Exception as exc:  # Reporting must never affect teaching.
                print(f"[diagnostics] candidate reporter unavailable: {exc}",
                      file=sys.stderr,flush=True)
        return result

    def observed_visit(*items, **kwargs):
        nonlocal visit_started
        visit_started = time.monotonic()
        outcome = original_visit(*items, **kwargs)
        try:
            grade, records, _, _, _, winner = outcome
            context = items[2]
            visit = {"grade":grade,"pass":context["completed_passes"]+1,
                     "candidate_attempts":len(records),
                     "eligible":sum(row["decision"]=="ELIGIBLE" for row in records),
                     "selected":({"step":winner["candidate_step"]} if winner else None),
                     "teacher_events":context["teacher"]["events"]}
            print(grade_line(visit,records,context,
                             elapsed=time.monotonic()-started,pending=True),flush=True)
        except Exception as exc:
            print(f"[diagnostics] grade reporter unavailable: {exc}",
                  file=sys.stderr,flush=True)
        return outcome

    def observed_pass(*items, **kwargs):
        result=original_finish(*items,**kwargs)
        try:
            for line in pass_lines(result,items[2]):
                print(line,flush=True)
        except Exception as exc:
            print(f"[diagnostics] pass reporter unavailable: {exc}",
                  file=sys.stderr,flush=True)
        return result

    engine.observe = observed_teacher
    runner._visit = observed_visit
    runner._finish_spiral_pass = observed_pass
    prior = sys.argv
    sys.argv = ["spiral_numeric_runner",*args]
    print("[diagnostics] LIVE candidate reporting enabled; training recipe unchanged.",flush=True)
    try:
        runner.main()
    finally:
        sys.argv = prior
        engine.observe = original_observe
        runner._visit = original_visit
        runner._finish_spiral_pass = original_finish


def main():
    if len(sys.argv)>1 and sys.argv[1]=="train":
        return train_with_live_diagnostics(sys.argv[2:])
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir",type=Path,default=DEFAULT_RUN)
    parser.add_argument("--watch",action="store_true",
                        help="attach read-only and show saved candidates at each grade boundary")
    parser.add_argument("--last",type=int,default=3,
                        help="number of most recent completed grades to replay on attach")
    parser.add_argument("--poll",type=float,default=1.5)
    parser.add_argument("--heartbeat",type=float,default=30.0)
    args=parser.parse_args()
    if not 0 <= args.last <= 10000 or args.poll < .2 or args.heartbeat<1:
        parser.error("--last must be nonnegative, --poll >=0.2, --heartbeat >=1")
    watch(args.run_dir,tail=args.last,interval=args.poll,
          heartbeat=args.heartbeat,follow=args.watch)


if __name__ == "__main__":
    main()
