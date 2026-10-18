"""Read-only, deterministic learning-history report for the human-operated MLX student.

Consumes committed events only. No model, optimizer, oracle, or MLX import is needed.
Distinct cohorts are *never* joined into a paired learning trajectory. Missing
diagnostic evidence stays missing; temporal association is not causal credit.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
from statistics import median
import tempfile
from types import MappingProxyType

from bilqis_mlx.curriculum import GRADE_IDS


SCHEMA = "bilqis.mlx.learning-history-report/v1"
ALERT_DROP_FRACTION = .05
PEER_LAG_FRACTION = .15
STALL_MIN_ATTEMPTS = 8
EXAM_TYPES = frozenset((
    "GRADE_A_EXAM_COMMITTED", "GRADE_A_LIVE_EXAM_COMMITTED",
    "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED", "SCHOOL_LIVE_EXAM_COMMITTED",
))
VISIT_TYPES = frozenset((
    "GRADE_A_TEACHER_VISIT_COMMITTED", "SCHOOL_GRADE_B_TEACHER_VISIT_COMMITTED",
    "SCHOOL_TEACHER_VISIT_COMMITTED", "SCHOOL_PERFECT_TARGET_VISIT_SKIPPED",
))
S_NAMES = MappingProxyType({
    "REPETITIVE_ANSWERS": "S1 · Repeated answers",
    "CHANCE_LEVEL_OR_LAGGING": "S2 · Chance-level or lagging",
    "LACK_OF_DURABLE_GAIN": "S3 · No lasting gain",
    "DISCONNECTED_PREREQUISITES": "S4 · Disconnected semantics",
    "EXCESSIVE_INTRODUCTORY_COMPLEXITY": "S5 · Introductory complexity",
})


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False).encode("utf-8")).hexdigest()


def _score_rows(raw):
    if not isinstance(raw, dict) or not raw:
        return None
    result = {}
    for capability, row in raw.items():
        if not isinstance(capability, str) or not isinstance(row, dict):
            return None
        correct, total = row.get("correct"), row.get("total")
        if (type(correct) is not int or type(total) is not int or
                total < 1 or not 0 <= correct <= total):
            return None
        result[capability] = (correct, total)
    return result


def _totals(scores):
    result = dict(scores)
    grades = defaultdict(lambda: [0, 0])
    for name, (correct, total) in scores.items():
        grade = name.partition(".")[0]
        grades[grade][0] += correct
        grades[grade][1] += total
    for grade, pair in grades.items():
        result[grade] = tuple(pair)
    result["ALL"] = (sum(v[0] for v in scores.values()),
                     sum(v[1] for v in scores.values()))
    return result


@dataclass(frozen=True)
class Exam:
    line: int
    generation: int
    step: int
    student: str
    cohort: str
    scope: str
    declared_scope: str
    scores: dict
    diagnostics: tuple
    event: str

    @property
    def totals(self):
        return _totals(self.scores)


@dataclass(frozen=True)
class Visit:
    line: int
    step: int
    capability: str
    decision: str
    reason: str
    retained: int
    policy: str
    old: int | None
    delivered_old: int | None
    methodology: tuple


def _exam(line, raw):
    scores = _score_rows(raw.get("scores"))
    step = raw.get("optimizer_step")
    student = raw.get("student_sha256")
    if scores is None or type(step) is not int or not isinstance(student, str) or not student:
        return None
    rubric = raw.get("rubric", "")
    if isinstance(rubric, dict):
        rubric = _digest(rubric)
    inventory = sorted((name, total) for name, (_, total) in scores.items())
    declared = str(raw.get("assessment_scope_sha256") or "")
    scope = _digest({"declared_scope": declared, "rubric": str(rubric),
                     "generator": str(raw.get("generator_version") or ""),
                     "inventory": inventory, "event_family": "live" if declared else raw["event"]})
    cohort = str(raw.get("cohort_sha256") or f"UNVERIFIED-LINE-{line}")
    diagnostics = (raw.get("learning_diagnostics") or {}).get("findings") or ()
    findings = tuple({"target": v.get("capability"), "signal": v.get("signal"),
                      "status": v.get("status"), "note": v.get("note", ""),
                      "type": v.get("target"), "scope": v.get("scope")}
                     for v in diagnostics if isinstance(v, dict))
    return Exam(line, int(raw.get("generation") or 0), step, student, cohort, scope,
                declared, scores, findings, raw["event"])


def _visit(line, raw):
    strategy = raw.get("strategy") or {}
    retention = raw.get("candidate_retention") or {}
    control = raw.get("typed_policy_controls") or {}
    old = strategy.get("old")
    old = old if type(old) is int else None
    delivered = control.get("old_grade_examples_delivered")
    delivered = delivered if type(delivered) is int else None
    lesson = raw.get("lesson_methodology") or {}
    return Visit(line, int(raw.get("optimizer_step") or 0),
                 str(raw.get("capability") or ""),
                 str(retention.get("decision") or ("SKIPPED" if "SKIPPED" in raw["event"] else "UNMEASURED")),
                 str(retention.get("reason") or ""),
                 int(raw.get("retained_optimizer_updates") or 0),
                 str(raw.get("teacher_policy") or ""), old, delivered,
                 tuple({"signal": f.get("signal"), "status": f.get("status"),
                        "target": f.get("capability"), "note": f.get("note", "")}
                       for f in lesson.get("findings", ()) if isinstance(f, dict)))


def read_history(event_file: Path):
    """Take one bounded append-safe byte snapshot. Never read mutable state.json."""
    exams, visits, warnings = [], [], []
    events_sha = hashlib.sha256()
    limit = event_file.stat().st_size
    complete_bytes = 0
    event_count = 0
    legacy_exams_without_identity = 0
    first_legacy_line = None
    with event_file.open("rb") as source:
        line_number = 0
        while complete_bytes < limit:
            raw_line = source.readline(limit - complete_bytes)
            if not raw_line:
                warnings.append("EVENT_STREAM_TRUNCATED_DURING_SNAPSHOT")
                break
            if not raw_line.endswith(b"\n"):
                warnings.append("TRAILING_PARTIAL_EVENT_EXCLUDED")
                break
            line_number += 1
            complete_bytes += len(raw_line)
            events_sha.update(raw_line)
            try:
                raw = json.loads(raw_line)
            except (ValueError, UnicodeError):
                warnings.append(f"UNREADABLE_EVENT_LINE:{line_number}")
                continue
            if not isinstance(raw, dict):
                warnings.append(f"NONOBJECT_EVENT_LINE:{line_number}")
                continue
            event_count += 1
            kind = raw.get("event")
            if kind in EXAM_TYPES:
                exam = _exam(line_number, raw)
                if exam is None:
                    if kind == "GRADE_A_EXAM_COMMITTED" and (
                            type(raw.get("optimizer_step")) is not int):
                        legacy_exams_without_identity += 1
                        if first_legacy_line is None:
                            first_legacy_line = line_number
                    else:
                        warnings.append(f"INCOMPLETE_EXAM_LINE:{line_number}")
                else:
                    exams.append(exam)
            elif kind in VISIT_TYPES:
                visits.append(_visit(line_number, raw))
    # Distinct exam snapshots, not repeated examinations of unchanged weights.
    distinct, known = [], {}
    duplicate_count = 0
    for exam in exams:
        key = (exam.scope, exam.cohort, exam.step, exam.student)
        previous = known.get(key)
        if previous is not None:
            if previous.scores != exam.scores:
                warnings.append(f"CONTRADICTORY_EXAM_SAME_CHECKPOINT:lines-{previous.line}-{exam.line}")
            else:
                duplicate_count += 1
            continue
        known[key] = exam
        distinct.append(exam)
    # Hash+step consistency is an independent custody concern, even when the
    # exam's cohort or score denominator changes.
    by_step = {}
    for exam in distinct:
        if exam.step in by_step and by_step[exam.step] != exam.student:
            warnings.append(f"CHECKPOINT_IDENTITY_CONFLICT_STEP:{exam.step}")
        by_step.setdefault(exam.step, exam.student)
    return {"exams": distinct, "visits": visits, "warnings": sorted(set(warnings)),
            "raw_exam_count": len(exams), "duplicate_exams": duplicate_count,
            "legacy_exams_without_checkpoint_identity": legacy_exams_without_identity,
            "first_legacy_exam_line": first_legacy_line,
            "event_count": event_count, "bytes_read": complete_bytes,
            "event_sha256": events_sha.hexdigest()}


def _threshold(total):
    # Descriptive alert threshold, not a statistical significance assertion.
    return max(2, math.ceil(total * ALERT_DROP_FRACTION))


def _finding(kind, target, before, after, *, cause, paired=False, detail=""):
    old_correct, total = before.totals[target]
    new_correct, new_total = after.totals[target]
    drop = old_correct - new_correct
    return {"id": _digest([kind, target, before.line, after.line])[:16],
            "kind": kind, "target": target, "before": old_correct,
            "after": new_correct, "total": total, "after_total": new_total,
            "loss": drop, "percentage_points": round(100 * drop / total, 2),
            "start_step": before.step, "end_step": after.step,
            "start_line": before.line, "end_line": after.line,
            "cohort_before": before.cohort, "cohort_after": after.cohort,
            "scope": after.scope, "same_student": (before.step == after.step and
                                                 before.student == after.student),
            "paired": paired, "classification": cause, "note": detail,
            "student_before": before.student, "student_after": after.student}


def _all_targets(exams):
    return sorted({cap for e in exams for cap in e.totals},
                  key=lambda name: (name not in ("A", "B", "C", "ALL"), name))


def inspect_trends(exams):
    """Only same scope+cohort changes are direct paired score evidence."""
    findings = []
    by_scope_cohort = defaultdict(list)
    by_scope = defaultdict(list)
    for exam in exams:
        by_scope_cohort[(exam.scope, exam.cohort)].append(exam)
        by_scope[exam.scope].append(exam)
    # Find worst peak -> trough per target, within one fixed source cohort.
    for (scope, cohort), cohort_exams in by_scope_cohort.items():
        if cohort.startswith("UNVERIFIED-"):
            continue
        for target in _all_targets(cohort_exams):
            members = [e for e in cohort_exams if target in e.totals]
            if len(members) < 2:
                continue
            peak = members[0]
            worst = None
            for current in members[1:]:
                if current.step != peak.step and current.student != peak.student:
                    if current.totals[target][1] == peak.totals[target][1]:
                        delta = peak.totals[target][0] - current.totals[target][0]
                        if delta >= _threshold(peak.totals[target][1]) and (
                                worst is None or delta > worst[0]):
                            worst = (delta, peak, current)
                if (current.totals[target][1] == peak.totals[target][1] and
                        current.totals[target][0] > peak.totals[target][0]):
                    peak = current
            if worst:
                _, before, after = worst
                findings.append(_finding("FIXED_COHORT_REGRESSION", target, before, after,
                    cause="MEASURED_SAME_QUESTIONS", paired=True,
                    detail="Same source cohort, different student checkpoints. A measured score decline, not isolated causal attribution."))
    # Adjacent cohort switches within a compatible rubric/answer inventory.
    for scope, scope_exams in by_scope.items():
        for before, after in zip(scope_exams, scope_exams[1:]):
            if before.cohort == after.cohort or (
                    before.cohort.startswith("UNVERIFIED-") or
                    after.cohort.startswith("UNVERIFIED-")):
                continue
            common = set(before.totals) & set(after.totals)
            for target in common:
                old_correct, denominator = before.totals[target]
                new_correct, new_denominator = after.totals[target]
                if (denominator != new_denominator or
                        old_correct - new_correct < _threshold(denominator)):
                    continue
                same = before.step == after.step and before.student == after.student
                findings.append(_finding("CROSS_COHORT_SCORE_GAP", target,
                    before, after, cause="SAME_MODEL_DIFFERENT_QUESTIONS" if same else
                    "UNPAIRED_COHORT_CHANGE", detail=(
                    "Unchanged checkpoint scored differently on two cohorts; this cannot be neural forgetting."
                    if same else "Different cohorts: do not infer forgetting or candidate causality from this difference.")))
    return sorted(findings, key=lambda f: (
        f["kind"] != "CROSS_COHORT_SCORE_GAP", -f["percentage_points"],
        -f["end_line"], f["target"]))


def _between(visits, start_line, end_line):
    return [v for v in visits if start_line < v.line <= end_line]


def _teacher_summary(visits):
    by_target = defaultdict(list)
    for visit in visits:
        if visit.capability:
            by_target[visit.capability].append(visit)
    first_grade = GRADE_IDS[0]
    summaries = []
    for target, all_visits in sorted(by_target.items()):
        recent = all_visits[-16:]
        attempted = [v for v in recent if v.decision not in ("SKIPPED", "UNMEASURED")]
        accepted = [v for v in attempted if v.decision == "PROVISIONAL" and v.retained > 0]
        rejected = [v for v in attempted if v.decision == "REJECT"]
        missing_old = [v for v in recent if v.capability.partition(".")[0] != first_grade
                       and v.old is not None and v.old > 0 and
                       v.delivered_old is None]
        reasons = Counter(v.reason for v in rejected)
        if not recent:
            continue
        summaries.append({"target": target, "recent_visits": len(recent),
                          "attempts": len(attempted), "accepted": len(accepted),
                          "rejected": len(rejected), "skipped": sum(v.decision == "SKIPPED" for v in recent),
                          "retained_optimizer_updates": sum(v.retained for v in recent),
                          "no_old_delivery_receipt": len(missing_old),
                          "top_rejection": reasons.most_common(1)[0][0] if reasons else None,
                          "start_line": recent[0].line, "end_line": recent[-1].line,
                          "zero_acceptance_stall": len(attempted) >= STALL_MIN_ATTEMPTS and
                                                   not accepted})
    return sorted(summaries, key=lambda r: (not r["zero_acceptance_stall"],
                                            -r["no_old_delivery_receipt"], r["target"]))


def _signal_summary(exams, visits):
    """Reuse existing source-scored S1-S5 findings; do not pretend to re-score gold."""
    latest = {}
    observed = []
    counts = Counter()
    for exam in exams:
        for f in exam.diagnostics:
            name = f["signal"]
            if name not in S_NAMES or not f["target"]:
                continue
            key = (name, f["target"])
            record = {**f, "line": exam.line, "step": exam.step,
                      "cohort": exam.cohort, "source": "EXAM"}
            latest[key] = record
            if str(f["status"]).startswith("OBSERVED"):
                observed.append(record)
    for visit in visits:
        for f in visit.methodology:
            name = f["signal"]
            if name not in S_NAMES or not f["target"]:
                continue
            key = (name, f["target"])
            record = {**f, "line": visit.line, "step": visit.step,
                      "cohort": None, "source": "DELIVERED_LESSON"}
            latest[key] = record
            if str(f["status"]).startswith("OBSERVED"):
                observed.append(record)
    # Absent diagnostics are a missing measurement, never an implicit pass.
    if exams:
        last = exams[-1]
        for target in last.scores:
            for name in S_NAMES:
                key = (name, target)
                if key not in latest:
                    latest[key] = {"signal": name, "target": target,
                                   "status": "NOT_MEASURED", "scope": "UNKNOWN",
                                   "line": last.line, "step": last.step,
                                   "source": "MISSING_DIAGNOSTIC_RECEIPT",
                                   "note": "No corresponding saved observation; no health claim possible."}
    for v in latest.values():
        counts[(v["signal"], v["status"])] += 1
    return {"latest": sorted(latest.values(), key=lambda x: (x["target"], x["signal"])),
            "observed": observed, "counts": [
                {"signal": signal, "status": status, "targets": n}
                for (signal, status), n in sorted(counts.items())]}


def _metrics(exams, scope, target):
    return [e for e in exams if e.scope == scope and target in e.totals]


def _additional_clues(current, teacher):
    latest = current[-1]
    clues = []
    scores = latest.totals
    groups = defaultdict(list)
    for name in latest.scores:
        groups[name.partition(".")[0]].append(name)
    for grade, capabilities in sorted(groups.items()):
        if len(capabilities) < 3:
            continue
        benchmark = median(scores[name][0] / scores[name][1] for name in capabilities)
        for name in capabilities:
            percent = scores[name][0]/scores[name][1]
            if benchmark - percent >= PEER_LAG_FRACTION:
                clues.append({"kind": "RELATIVE_PEER_LAG", "target": name,
                              "step": latest.step, "line": latest.line,
                              "evidence": f'{scores[name][0]}/{scores[name][1]} correct; '
                              f'grade {grade} capability median {benchmark:.1%}',
                              "interpretation": "Within-cohort relative gap, not a calibrated chance baseline."})
    for record in teacher:
        if record["zero_acceptance_stall"]:
            clues.append({"kind": "REPEATED_CANDIDATE_REJECTION", "target": record["target"],
                          "step": None, "line": record["end_line"],
                          "evidence": f'{record["attempts"]} recent attempts, '
                          f'{record["accepted"]} retained; most common: {record["top_rejection"]}',
                          "interpretation": "Teacher proposal or admission bottleneck; not proof of inability to learn."})
        if record["no_old_delivery_receipt"] >= 3:
            clues.append({"kind": "OLDER_GRADE_REHEARSAL_UNVERIFIED", "target": record["target"],
                          "step": None, "line": record["end_line"],
                          "evidence": f'{record["no_old_delivery_receipt"]} of last '
                          f'{record["recent_visits"]} visits requested earlier-grade examples '
                          'without a delivered-old accounting receipt',
                          "interpretation": "Instrumentation/control-path audit required; absence of receipt is not proof of absence of rehearsal."})
    return sorted(clues, key=lambda x: (x["kind"], x["target"]))


def _scope_contrasts(current, scope):
    """Best versus latest on a sealed scope, without pairing different cohorts."""
    contrasts = []
    for target in (t for t in _all_targets(current) if t != "ALL"):
        members = _metrics(current, scope, target)
        if not members:
            continue
        before = max(members, key=lambda e: (e.totals[target][0]/e.totals[target][1],
                                              -e.line))
        after = members[-1]
        best_score, current_score = before.totals[target], after.totals[target]
        same_cohort = before.cohort == after.cohort
        contrasts.append({"target": target, "best_correct": best_score[0],
                          "best_total": best_score[1], "last_correct": current_score[0],
                          "last_total": current_score[1], "best_step": before.step,
                          "last_step": after.step, "best_line": before.line,
                          "last_line": after.line, "best_cohort": before.cohort,
                          "last_cohort": after.cohort,
                          "paired": same_cohort and before.step != after.step and
                                    before.student != after.student,
                          "difference": round(100*(best_score[0]/best_score[1] -
                                                   current_score[0]/current_score[1]), 2),
                          "evidence_class": "SAME_SOURCE_COHORT" if same_cohort else
                                            "CROSS_COHORT_UNPAIRED"})
    return sorted(contrasts, key=lambda x: (-x["difference"], x["target"]))


def analyze(ledger, *, min_report_loss=1):
    """Return a deterministic, machine-readable report from one event snapshot."""
    exams = ledger["exams"]
    visits = ledger["visits"]
    if not exams:
        raise ValueError("LEARNING_REPORT_REQUIRES_COMPLETE_SCORED_EXAM_EVENTS")
    newest = exams[-1]
    scope = newest.scope
    current = [e for e in exams if e.scope == scope]
    findings = inspect_trends(exams)
    # The feature first reports the current curriculum scope and its history;
    # incompatible older numeric domains are retained in the dataset counts.
    current_findings = [f for f in findings if f["scope"] == scope]
    for f in current_findings:
        window = _between(visits, f["start_line"], f["end_line"])
        accepted = [v for v in window if v.decision == "PROVISIONAL" and v.retained > 0]
        rejected = [v for v in window if v.decision == "REJECT"]
        f["intervening_visits"] = len(window)
        f["accepted_visits"] = len(accepted)
        f["rejected_visits"] = len(rejected)
        f["accepted_capabilities"] = dict(Counter(v.capability for v in accepted))
        f["candidate_causality"] = (
            "NOT_APPLICABLE_IDENTICAL_STUDENT" if f["same_student"] else
            "NOT_ATTRIBUTABLE_FROM_TEMPORAL_ASSOCIATION")
    contrasts = _scope_contrasts(current, scope)
    signal = _signal_summary(current, visits)
    teacher = _teacher_summary(visits)
    # No unknown run clock inferred. Steps and line numbers are observable order.
    return {"schema": SCHEMA,
            "source": {"sha256": ledger["event_sha256"],
                       "bytes": ledger["bytes_read"], "events": ledger["event_count"],
                       "scored_exams": ledger["raw_exam_count"],
                       "distinct_exam_snapshots": len(exams),
                       "repeated_identical_exams": ledger["duplicate_exams"],
                       "legacy_exams_without_checkpoint_identity": ledger[
                           "legacy_exams_without_checkpoint_identity"],
                       "first_legacy_exam_line": ledger["first_legacy_exam_line"],
                       "visit_events": len(visits),
                       "warnings": ledger["warnings"]},
            "latest_scope_sha256": scope,
            "latest_declared_scope": newest.declared_scope,
            "latest_cohort_sha256": newest.cohort,
            "latest_step": newest.step,
            "detector_thresholds": {
                "minimum_score_drop_points": 2,
                "minimum_score_drop_fraction": ALERT_DROP_FRACTION,
                "relative_peer_lag_fraction": PEER_LAG_FRACTION,
                "stall_attempts_without_admission": STALL_MIN_ATTEMPTS,
                "visual_high_fraction": .90,
                "visual_low_fraction": .65,
            },
            "latest_line": newest.line,
            "latest_scores": {k: {"correct": v[0], "total": v[1]}
                              for k, v in newest.totals.items()},
            "scopes": len({e.scope for e in exams}),
            "cohorts_in_latest_scope": len({e.cohort for e in current}),
            "distinct_exams_in_scope": len(current),
            "alerts": [f for f in current_findings if f["loss"] >= min_report_loss],
            "scope_contrasts": contrasts, "signals": signal,
            "teacher": teacher,
            "additional_clues": _additional_clues(current, teacher),
            "milestones": [{"line": e.line, "step": e.step,
                            "cohort": e.cohort,
                            "scores": {k: {"correct": v[0], "total": v[1]}
                                       for k, v in e.totals.items()}}
                           for e in current],
            "_exam_history": current}



def render_html(report, *, max_points=240):
    """Public renderer, loaded lazily to keep event analysis presentation-free."""
    from .learning_report_render import render_html as render
    return render(report, max_points=max_points)

def _atomic_write(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Generated outputs are the only writable artifacts. Never stage a report
    # beside the trainer's state.json, model bundle or events.jsonl.
    fd, tmp = tempfile.mkstemp(prefix=".learning-report-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(contents)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline, read-only Bilqis learning report (HTML + JSON)")
    parser.add_argument("--run-dir", type=Path, default=Path(__file__).resolve().parents[2]
                        / "runs" / "school-mlx-v1", help="Existing saved-run directory")
    parser.add_argument("--output", type=Path, default=None,
                        help="HTML output outside the active run directory")
    parser.add_argument("--max-points", type=int, default=240,
                        help="Max recent distinct examinations per SVG (default 240)")
    args = parser.parse_args(argv)
    run = args.run_dir.expanduser().resolve()
    events = run / "events.jsonl"
    if not events.is_file():
        parser.error(f"saved event stream not found: {events}")
    if not 8 <= args.max_points <= 3000:
        parser.error("--max-points must be between 8 and 3000")
    out = (args.output.expanduser() if args.output else
           run.parent / "reports" / f"{run.name}-learning-report.html").resolve()
    if out.suffix.lower() != ".html":
        parser.error("--output must end in .html")
    if out.is_relative_to(run):
        parser.error("refusing output inside the active neural run directory")
    raw = read_history(events)
    report = analyze(raw)
    report["source"]["events_file"] = str(events)
    rendered = render_html(report, max_points=args.max_points)
    json_report = {key: value for key, value in report.items() if not key.startswith("_")}
    json_file = out.with_suffix(".json")
    _atomic_write(out, rendered)
    _atomic_write(json_file, json.dumps(json_report, indent=2, sort_keys=True,
                                        ensure_ascii=False) + "\n")
    print(f"HTML: {out}\nJSON: {json_file}\n"
          f"Distinct exams: {raw['raw_exam_count'] - raw['duplicate_exams']} "
          f"(suppressed {raw['duplicate_exams']} repeats); "
          f"current-scope alerts: {len(report['alerts'])}")
    for f in sorted(report["alerts"], key=lambda x: -x["end_line"])[:6]:
        print(f"  {f['classification']}: {f['target']} "
              f"{f['before']}/{f['total']} -> {f['after']}/{f['after_total']} "
              f"(steps {f['start_step']}->{f['end_step']}; "
              f"events {f['start_line']}->{f['end_line']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
