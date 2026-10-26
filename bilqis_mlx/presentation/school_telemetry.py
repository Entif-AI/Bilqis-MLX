"""Grade-independent, read-only School50 telemetry projection.

Legacy Grade A events adapt to this contract. New grades can emit SCHOOL_*
events without teaching the dashboard their particular lesson vocabulary.
No scoring here is passed back to a teacher, model, or curriculum admission.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any
import string

from bilqis_mlx.presentation.spiral_dashboard import Column
from bilqis_mlx.presentation.growth_projection import GrowthProjection
from bilqis_mlx.presentation.teacher_vnext import teacher_fields as _teacher_vnext_fields
from ..compatibility.telemetry_events import (
    historical_capability_grade,
    historical_course_admission,
    historical_event_grade,
    historical_event_kind,
    historical_live_exam,
    historical_withheld_inventory_change_explains,
)

TELEMETRY_VERSION = "bilqis.school50.telemetry/v1"
_SIGNAL_LABELS = {
    "REPETITIVE_ANSWERS": "S1",
    "CHANCE_LEVEL_OR_LAGGING": "S2",
    "LACK_OF_DURABLE_GAIN": "S3",
    "DISCONNECTED_PREREQUISITES": "S4",
    "EXCESSIVE_INTRODUCTORY_COMPLEXITY": "S5",
}

def _signal_label(signal) -> str:
    return _SIGNAL_LABELS.get(str(signal), str(signal))


def _teacher_decision_text(decision: object) -> str:
    if not isinstance(decision, dict):
        return "LESSON COMMITTED; exam pending"
    warnings = [_signal_label(signal) for signal in decision.get("warning_signals", ())]
    selected = decision.get("selected") or {}
    selection = decision.get("policy_selection") or {}
    warning_prefix = ("warn " if selection.get("diagnostic_context_consumed") else
                      "warn-context ")
    parts = [warning_prefix + ",".join(warnings)] if warnings else []
    replayed = selected.get("exam_mistake_replay")
    champion = selected.get("champion_priority")
    if type(replayed) is int and replayed:
        parts.append(f"miss {replayed}")
    if type(champion) is int and champion:
        parts.append(f"champ {champion}")
    return " | ".join(parts) + "; exam pending" if parts else "LESSON COMMITTED; exam pending"

_REASON_LABELS = {
    "NO_MEASURABLE_TARGET_GAIN": "NO TARGET GAIN",
    "FRAGILE_COMPOSITION_REPLAY_REGRESSION": "OR/XOR LOSS",
    "PROTECTED_CAPABILITY_REGRESSION": "PROTECTED LOSS",
    "ACTIVE_SCHOOL_GRADE_REGRESSION": "FRONTIER LOSS",
    "PAIRED_SCREEN_WITHIN_BUDGET": "WITHIN BUDGET",
}


def _warning_text(event: dict) -> str:
    decision = event.get("teacher_decision")
    if not isinstance(decision, dict):
        return "-"
    warnings = [_signal_label(signal) for signal in decision.get("warning_signals", ())]
    return ",".join(warnings) if warnings else "-"


def _candidate_result_reason(event: dict) -> tuple[str, str]:
    candidate = event.get("candidate_retention")
    steps = event.get("retained_optimizer_updates")
    if candidate is None and steps is None:
        return "PEND", "EXAM PENDING"
    if not isinstance(candidate, dict):
        return "UNK", "ADMISSION UNKNOWN"
    reason = str(candidate.get("reason") or "UNKNOWN")
    reason = _REASON_LABELS.get(reason, reason)
    if candidate.get("decision") == "PROVISIONAL" and type(steps) is int and steps > 0:
        return "RETAIN", reason
    if candidate.get("decision") == "REJECT" and steps == 0:
        return "REJECT", reason
    return "CONFLT", "ADMISSION CONFLICT"


def _candidate_admission_text(event: dict) -> str:
    """Distinguish an attempted lesson from student/AdamW promotion."""
    candidate = event.get("candidate_retention")
    steps = event.get("retained_optimizer_updates")
    if candidate is None and steps is None:
        return _teacher_decision_text(event.get("teacher_decision"))
    if not isinstance(candidate, dict):
        label = "ADMISSION UNKNOWN"
    elif candidate.get("decision") == "PROVISIONAL" and type(steps) is int and steps > 0:
        label = f"RETAIN {steps}"
    elif candidate.get("decision") == "REJECT" and steps == 0:
        reason = candidate.get("reason")
        if reason == "NO_MEASURABLE_TARGET_GAIN":
            label = "REJECT NO TARGET GAIN"
        elif reason == "FRAGILE_COMPOSITION_REPLAY_REGRESSION":
            label = "REJECT OR/XOR LOSS"
        elif reason == "PROTECTED_CAPABILITY_REGRESSION":
            label = "REJECT PROTECTED LOSS"
        else:
            label = "REJECT " + str(reason or "UNKNOWN")
    else:
        label = "ADMISSION CONFLICT"
    instructional = _teacher_decision_text(event.get("teacher_decision"))
    hint = instructional.removesuffix("; exam pending")
    if hint != "LESSON COMMITTED":
        label += " | " + hint
    association = _association_text(event)
    if association is not None:
        label += " | " + association
    return label


def _association_text(event: dict) -> str | None:
    bridge = event.get("boolean_association_bridge")
    if isinstance(bridge, dict) and bridge.get("active_for_visit") is True:
        grades = bridge.get("borrowed_source_grades")
        delivered = bridge.get("delivered_examples")
        active = event.get("active_grade") or event.get("grade")
        if (isinstance(grades, list) and grades and
                all(isinstance(grade, str) and grade for grade in grades) and
                type(delivered) is int and delivered > 0 and
                isinstance(active, str) and active):
            return "COMPOSE " + "+".join(grades) + "->" + active + f" x{delivered}"
    return None


def _instruction_method_text(event: dict) -> str:
    """Project the lesson mechanism actually evidenced by the visit receipt."""
    parts = []
    if _association_text(event) is not None:
        parts.append("COMPOSE")
    decision = event.get("teacher_decision") or {}
    selected = decision.get("selected") if isinstance(decision, dict) else {}
    selected = selected if isinstance(selected, dict) else {}
    if type(selected.get("exam_mistake_replay")) is int and selected["exam_mistake_replay"] > 0:
        parts.append("MISS")
    prerequisites = selected.get("prerequisite_connections")
    if isinstance(prerequisites, (list, tuple)) and prerequisites:
        parts.append("PREREQ")
    if type(selected.get("champion_priority")) is int and selected["champion_priority"] > 0:
        parts.append("CHAMP")
    if parts:
        return "+".join(parts)
    methodology = event.get("lesson_methodology") or {}
    if isinstance(methodology, dict) and type(methodology.get("delivered_examples")) is int:
        if methodology["delivered_examples"] > 0:
            return "SOURCE"
    if type(selected.get("delivered_examples")) is int and selected["delivered_examples"] > 0:
        return "DIRECT"
    return "-"


def _candidate_retention_row(event: dict, grade: str, attempt: int) -> dict | None:
    retention = event.get("candidate_retention")
    if not isinstance(retention, dict):
        return None
    capability = retention.get("active_capability") or event.get("capability") or "-"
    before = retention.get("active_probe_before")
    after = retention.get("active_probe_after")
    total = retention.get("active_probe_total")
    target = (f"{before}>{after}/{total}"
              if all(type(value) is int for value in (before, after, total)) and total > 0
              else "-")
    local = retention.get("local_correct_delta")
    protected = retention.get("protected_net_correct_delta")
    worst = retention.get("worst_protected_loss")
    reason = str(retention.get("reason") or "UNKNOWN")
    unsampled = retention.get("unsampled_admitted_capabilities")
    evidence = reason
    if type(unsampled) is int:
        evidence += f" | unsampled {unsampled}"
    frontier_grade = retention.get("protected_frontier_grade")
    frontier_delta = retention.get("protected_frontier_grade_net_correct_delta")
    if isinstance(frontier_grade, str) and type(frontier_delta) is int:
        evidence += f" | frontier {frontier_grade} {frontier_delta:+d}"
    return {
        "grade": grade,
        "capability": capability,
        "attempt": attempt,
        "target": target,
        "target_delta": f"{local:+d}" if type(local) is int else "-",
        "protected": f"{protected:+d}" if type(protected) is int else "-",
        "worst": ("0" if worst == 0 else f"-{worst}"
                  if type(worst) is int and worst > 0 else "-"),
        "decision": str(retention.get("decision") or "UNKNOWN"),
        "result": str(retention.get("decision") or "UNKNOWN"),
        "evidence": evidence,
    }


def _diagnostic_system_rows(event: dict, grade: str) -> tuple[dict, ...]:
    rows = []
    diagnostics = event.get("learning_diagnostics")
    if isinstance(diagnostics, dict):
        warning_labels = [
            f"{_signal_label(warning.get('signal'))}:{warning.get('capability', '?')}"
            for warning in diagnostics.get("active_warnings", ())
            if isinstance(warning, dict)
        ]
        not_measured = sum(
            1 for finding in diagnostics.get("findings", ())
            if isinstance(finding, dict) and finding.get("status") == "NOT_MEASURED")
        unavailable = (
            diagnostics.get("s3_usable") is False
            if "s3_usable" in diagnostics else
            diagnostics.get("history_usable") is False)
        detail = ("active " + ", ".join(warning_labels)
                  if warning_labels else "S3 unavailable" if unavailable else "no active warnings")
        if unavailable and warning_labels:
            detail += " | S3 unavailable"
        rows.append({"kind":"DIAGNOSTIC", "grade":grade,
                     "detail":detail + f" | {not_measured} NOT MEASURED"})
        if unavailable and diagnostics.get("history_issue"):
            rows.append({"kind": "HISTORY ISSUE", "grade": grade,
                         "detail": str(diagnostics["history_issue"])})
        elif diagnostics.get("history_usable") is False and diagnostics.get("history_issue"):
            rows.append({"kind": "HISTORY ISSUE", "grade": grade,
                         "detail": str(diagnostics["history_issue"]) +
                                   " | paired S3 recovered"})
    outcomes = event.get("teacher_outcomes")
    if isinstance(outcomes, list) and outcomes:
        rows.append({"kind":"TEACH OUTCOME", "grade":grade,
                     "detail":_teacher_outcome_text(outcomes)})
    return tuple(rows)


def _teacher_outcome_text(outcomes: list[dict]) -> str:
    measured = _measured_teacher_outcomes(outcomes)
    if measured:
        return "fixed-exam action outcome " + (_measured_outcome_changes(measured) or "measured")
    return _unmeasured_outcome_counts(outcomes)


def _measured_teacher_outcomes(outcomes: list[dict]) -> list[dict]:
    return [item for item in outcomes if isinstance(item, dict) and
            item.get("attribution") == "MEASURED_FIXED_EXAM_UNIQUE_ACTION"]


def _measured_outcome_changes(measured: list[dict]) -> str:
    return ", ".join(
        f"{item.get('capability', '?')} {item.get('delta_correct', 0):+d}"
        for item in measured if type(item.get("delta_correct")) is int)


def _unmeasured_outcome_counts(outcomes: list[dict]) -> str:
    counts = defaultdict(int)
    for item in outcomes:
        if isinstance(item, dict):
            counts[str(item.get("attribution", "UNKNOWN"))] += 1
    return " | ".join(f"{key} x{count}" for key, count in sorted(counts.items()))

# Same six historical panel identities, new-school labels that describe what
# the data actually measures. The old School50 TABLES constant is untouched.
LETTER_TABLES = (
    ("CANDIDATES", (
        Column("CAPABILITY", 10, "capability"),
        Column("VISIT", 5, "attempt", right=True),
        Column("POLICY", 10, "strategy", optional=True),
        Column("LR", 2, "lr", optional=True, right=True),
        Column("WAS/CHP/NOW/ALL", 15, "score_line", right=True),
        Column("REWARD", 6, "reward", right=True),
        Column("LOSS", 5, "loss"),
        Column("GRAD", 5, "gradient", right=True),
        Column("METHOD", 6, "method"),
        Column("OLD pp", 6, "old", optional=True, right=True),
        Column("RESULT", 6, "result"),
        Column("REASON", 27, "reason"),
        Column("WARNINGS", 12, "warnings"))),
    ("SENTINEL & RETENTION", (
        Column("CAPABILITY", 10, "capability"),
        Column("VISIT", 5, "attempt", right=True),
        Column("TARGET", 8, "target", right=True),
        Column("DTG", 3, "target_delta", right=True),
        Column("PRT", 3, "protected", right=True),
        Column("WRS", 3, "worst", right=True),
        Column("RSULT", 5, "result"),
        Column("EVIDENCE", 20, "evidence", optional=True))),
    ("SOUP & TEACHER", (
        Column("CAPABILITY", 10, "capability"),
        Column("VISIT", 5, "attempt", right=True),
        Column("POLICY", 10, "policy", optional=True),
        Column("LR", 2, "lr", right=True),
        Column("D", 1, "depth", right=True),
        Column("C", 1, "contrast", right=True),
        Column("OLD", 3, "old", optional=True, right=True),
        Column("DSTIL", 5, "distill", optional=True, right=True),
        Column("CREDIT", 7, "credit", right=True), Column("HEALTH", 9, "health", optional=True))),
    ("GRADES & MASTERY", (
        Column("CAPABILITY", 10, "subject"),
        Column("WAS/TOP/NOW/ALL", 15, "score_line", right=True),
        Column("GOOD [GREW]", 11, "right_grew", right=True),
        Column("OUTCOME", 26, "outcome"))),
    ("SYSTEM & QUALIFICATION", (
        Column("TYPE", 7, "kind"),
        Column("DETAILS", 32, "detail"))),
)


EVENT_KINDS = {
    "SCHOOL_NEW_RUN_INITIALIZED": "init",
    "SCHOOL_NEXT_GRADE_COURSE_ADMITTED": "init",
    "SCHOOL_EXECUTION_PROFILE_ADOPTED": "curriculum",
    "SCHOOL_SEMANTIC_CATALOG_PROFILE_ADOPTED": "curriculum",
    "SCHOOL_TEACHER_VISIT_COMMITTED": "visit",
    "SCHOOL_LIVE_EXAM_COMMITTED": "exam",
    "SCHOOL_FLASH_ROUTINE_EXAM_COMMITTED": "exam",
    "SCHOOL_COURSE_ADMITTED": "init",
    "SCHOOL_RUN_INITIALIZED": "init",
    "SCHOOL_VISIT_COMMITTED": "visit",
    "SCHOOL_EXAM_COMMITTED": "exam",
    "SCHOOL_SESSION_STOPPED": "stop",
    "SCHOOL_SESSION_STARTED": "start",
    "SCHOOL_SENTINEL_COMMITTED": "sentinel",
    "SCHOOL_SOUP_COMMITTED": "soup",
    "SCHOOL_FAMILY_PROBE_COMMITTED": "family",
    "SCHOOL_RESOURCE_OBSERVED": "resource",
    "SCHOOL_CAPABILITY_BEST_COMMITTED": "capability_best",
    "SCHOOL_LIVE_CANDIDATE_COMPARED": "candidate",
    "SCHOOL_QUALIFICATION_COMMITTED": "qualification",
    "SCHOOL_FLASH_ASSESSMENT_DEFERRED": "progress",
    "SCHOOL_GRADE_RELEASE_REPLACED": "curriculum",
    "SCHOOL_AUTONOMY_SOURCE_COVERAGE_BLOCKED": "autonomy",
    "SCHOOL_AUTONOMY_EVIDENCE_RECORDED": "autonomy",
    "SCHOOL_AUTONOMY_EVIDENCE_VISIT_COMPLETED": "autonomy",
    "SCHOOL_AUTONOMY_QUALIFIED_VISIT_COMPLETED": "autonomy",
    "SCHOOL_AUTONOMY_TEACHING_RECORDED": "autonomy",
}


def _display(value: Any, *, decimals: int = 3) -> str:
    if type(value) in (float, int):
        if value and abs(value) < 0.5 * 10 ** (-decimals):
            return f"{value:.2e}"
        return f"{value:.{decimals}f}"
    return "-"


def _inventory_scope(scope: str, caps: dict) -> str:
    """Internal comparison identity for the capability inventory actually scored."""
    return scope + "|inventory:" + ",".join(sorted(caps))


def _scaled_lr(value: Any) -> str:
    if type(value) not in (float, int):
        return "-"
    return str(int(value * 100000 + 0.5))


def _whole(value: Any) -> str:
    if type(value) not in (float, int):
        return "-"
    return str(int(value + 0.5))


def _score_quad(before: Any, top: Any, after: Any, total: Any) -> str:
    if not all(type(value) is int for value in (before, after, total)) or total <= 0:
        return "-"
    top_text = f"{top:>3}" if type(top) is int else "  -"
    return f"{before:>3}/{top_text}/{after:>3}/{total:>3}"


def _delta(value: Any, *, pp: bool = False) -> str:
    if type(value) not in (float, int):
        return "-"
    if pp:
        return f"{value:+.1f}pp"
    return f"{value:+.3f}"


def _percent(value: Any) -> str:
    return f"{value:.1%}" if type(value) in (float, int) else "-"


def _count(value: Any) -> str:
    return f"{value:,}" if type(value) is int else "-"


def _source_provenance(event: dict):
    """Independent metrics must identify their validation set and whole student."""
    for key in ("dataset_sha256", "student_sha256"):
        value = event.get(key)
        if (not isinstance(value, str) or len(value) != 64 or
                any(ch not in string.hexdigits for ch in value)):
            raise ValueError("SCHOOL_TELEMETRY_SOURCE_PROVENANCE_REQUIRED:" + key)
    if type(event.get("optimizer_step")) is not int:
        raise ValueError("SCHOOL_TELEMETRY_SOURCE_PROVENANCE_REQUIRED:optimizer_step")


@dataclass(frozen=True)
class ExamScore:
    grade: str
    rubric: str
    correct: int
    total: int
    step: int | None
    checkpoint_sha256: str
    generation: int
    capabilities: dict[str, tuple[int, int]]
    assessment_scope: str = ""


class SchoolTelemetry:
    """Incremental projection; START/latest/best scores are receipt-backed."""

    def __init__(self, board, *, active_grades=(), champions=None):
        self.board = board
        self.grades = list(active_grades)
        self.champions = champions or {}
        self.start = {}   # (grade, complete-rubric, scope) -> execution-start ExamScore
        self.latest = {}
        self.best = {}
        self.last_cap = {}  # (capability, complete-rubric) -> (correct,total)
        self.start_cap = {}
        self.growth = GrowthProjection(active_grades)
        self.last_source_training = {}  # capability -> (accuracy, optimizer_step)
        self.exam_cohorts = {}  # (grade, semantic rubric) -> last sampled cohort
        self.reported_scope_inventory = {}
        self.scope_variants = {}
        # Whole-student exam scores are distinct from separate per-grade bests.
        self.cumulative_best = {}  # (grades, rubric, scope) -> (correct, total, step)
        self.cumulative_latest = None  # (key, correct, total, step, status)
        self.score_era = 0
        self.era_cohorts = defaultdict(set)
        self.visits = 0
        self.last_exam_grade = None
        self.execution_start_step = None
        self.live_projected_generations = set()
        self.teacher_policy_health = {}
        self.board.grade_program = tuple(self.grades)

    def _grade(self, name):
        if name not in self.grades:
            self.grades.append(name)
            self.board.grade_program = tuple(self.grades)

    def _reset_score_era(self, *, reason: str, grade: str | None) -> None:
        """Start a new longitudinal-score era without deleting event history."""
        self.score_era += 1
        self.best.clear()
        self.cumulative_best.clear()
        self.cumulative_latest = None
        self.exam_cohorts.clear()
        self.era_cohorts.clear()
        self.last_cap.clear()
        self.start_cap.clear()
        self.board.push("system", {
            "kind": "SCORE ERA", "grade": grade or "-",
            "detail": f"ERA {self.score_era} | RESET {reason}",
        }, redraw=False)

    def ingest(self, event: dict):
        if (event.get("event", "").startswith("SCHOOL_") and
                event.get("telemetry_schema", TELEMETRY_VERSION) != TELEMETRY_VERSION):
            raise ValueError("SCHOOL_TELEMETRY_UNSUPPORTED_SCHEMA")
        kind = (EVENT_KINDS.get(event.get("event")) or
                historical_event_kind(event.get("event")))
        if kind is None:
            return
        grade = event.get("grade") or historical_event_grade(event["event"])
        if kind not in {"init", "resource"} and not grade:
            raise ValueError("SCHOOL_TELEMETRY_GRADE_REQUIRED")
        if grade:
            self._grade(grade)
        {
            "init": self._init,
            "curriculum": self._curriculum,
            "start": self._start,
            "visit": self._visit,
            "exam": self._exam,
            "stop": self._stop,
            "sentinel": self._sentinel,
            "soup": self._soup,
            "family": self._family,
            "resource": self._resource,
            "capability_best": self._capability_best,
            "candidate": self._candidate,
            "qualification": self._qualification,
            "progress": self._progress,
            "autonomy": self._autonomy,
        }[kind](grade, event)

    def _init(self, grade, event):
        if event.get("event") in {
                "SCHOOL_NEXT_GRADE_COURSE_ADMITTED",
                "SCHOOL_COURSE_ADMITTED"} or historical_course_admission(
                    event.get("event")):
            self._reset_score_era(
                reason=("NEXT_GRADE_ADMITTED"
                        if event.get("event") == "SCHOOL_NEXT_GRADE_COURSE_ADMITTED"
                        else "COURSE_ADMITTED"),
                grade=grade)
        self.board.state["step"] = event.get("optimizer_step", self.board.state.get("step"))
        self.board.state["_rate_sample_eligible"] = True

    def _curriculum(self, grade, event):
        """Make a release replacement a hard boundary in the active dashboard view."""
        self._reset_score_era(reason=event["event"], grade=grade)
        old_caps = tuple(event.get("old_capabilities") or ())
        new_caps = tuple(event.get("new_capabilities") or ())
        if (not grade or not old_caps or not new_caps or
                any(not isinstance(cap, str) for cap in (*old_caps, *new_caps))):
            raise ValueError("SCHOOL_TELEMETRY_CURRICULUM_REPLACEMENT_INVALID")
        self.board.state["grew"] = self.growth.replace_grade(
            grade, old_caps, new_caps, event.get("withheld_capabilities", ()))
        old_set = set(old_caps)

        # Rows before this event describe the superseded curriculum. Keep them
        # in the immutable event log, not in the operator's active curriculum.
        for table in ("CANDIDATES", "SOUP & TEACHER", "BRIDGE FAMILIES",
                      "SENTINEL & RETENTION"):
            rows = self.board.rows[table]
            self.board.rows[table] = [
                row for row in rows
                if (row.get("capability") or row.get("family")) not in old_set
            ]
        self.board.rows["GRADES & MASTERY"] = [
            row for row in self.board.rows["GRADES & MASTERY"]
            if row.get("grade") != grade
        ]
        self.board.rows["SYSTEM & QUALIFICATION"] = [
            row for row in self.board.rows["SYSTEM & QUALIFICATION"]
            if not (row.get("grade") == grade and
                    row.get("kind") in {"CHAMPION", "GRADE SOUP", "CAP BEST"})
        ]

        for mapping in (self.start, self.latest, self.best, self.exam_cohorts,
                        self.reported_scope_inventory):
            for key in list(mapping):
                if isinstance(key, tuple) and key and key[0] == grade:
                    mapping.pop(key, None)
        for mapping in (self.start_cap, self.last_cap):
            for key in list(mapping):
                if isinstance(key, tuple) and key and key[0] in old_set:
                    mapping.pop(key, None)
        for cap in old_set:
            self.last_source_training.pop(cap, None)
        for key in list(self.scope_variants):
            if isinstance(key, tuple) and key and key[0] == grade:
                self.scope_variants.pop(key, None)
        self.cumulative_best.clear()
        self.cumulative_latest = None
        self.champions.pop(grade, None)
        self.last_exam_grade = None

        self.board.push("system", {
            "kind": "CURRICULUM",
            "grade": grade,
            "detail": "Active " + grade + ": " + ", ".join(new_caps),
        }, redraw=False)

    def begin_execution(self, *, grade=None, step=None):
        """Re-anchor START to the scores that exist when this command begins."""
        if (type(step) is int and self.execution_start_step == step and
                self.start == self.latest):
            self.board.state.update(
                step=step, prefix=grade or self.board.state.get("prefix"),
                _rate_sample_eligible=True)
            return
        self.visits = 0
        self.start = dict(self.latest)
        self.start_cap = dict(self.last_cap)
        self.board.state["grew"] = self.growth.begin_execution()
        self.execution_start_step = step if type(step) is int else None
        # Emit current snapshots immediately so START is truthful before the
        # first new exam in this execution command.
        latest_by_grade = {}
        for key, report in self.latest.items():
            existing = latest_by_grade.get(report.grade)
            if existing is None or report.generation >= existing.generation:
                latest_by_grade[report.grade] = report
        for g, report in sorted(latest_by_grade.items()):
            key = (g, report.rubric, report.assessment_scope)
            best = self.best.get(key, report)
            champion = self.champions.get(g)
            self.board.rows["GRADES & MASTERY"].append({
                "visit": self.visits, "grade": g, "step": report.step or "-",
                "attempt": report.generation,
                "start": f"{report.correct}/{report.total}",
                "latest": f"{report.correct}/{report.total}",
                "best": f"{best.correct}/{best.total}",
                "to100": str(report.total-report.correct),
                "right_pct": f"{100*report.correct/report.total:.1f}%",
                "outcome": "EXECUTION START", "mastered": bool(champion),
            })
        if latest_by_grade:
            ordered = [g for g in self.grades if g in latest_by_grade]
            summary = " | ".join(
                f"{g} {latest_by_grade[g].correct}/{latest_by_grade[g].total}"
                for g in ordered)
            steps = {latest_by_grade[g].step for g in ordered}
            suffix = f" @step {next(iter(steps))}" if len(steps) == 1 else ""
            self.board.operator_lines = [
                "START " + summary + suffix + " | execution baseline",
                "LATEST begins equal to START; BEST remains historical receipt-backed evidence.",
            ]
        self.board.state.update(
            step=step if type(step) is int else self.board.state.get("step"),
            prefix=grade or self.board.state.get("prefix"), visits=0,
            attempted_steps=0, retained_steps=0, retained_visits=0,
            _rate_sample_eligible=True)
        self.board.started = self.board.clock()
        self.board._rate_step = None
        self.board._rate_time = None

    def _start(self, grade, event):
        self.begin_execution(grade=grade, step=event.get("optimizer_step"))

    def _progress(self, grade, event):
        """Ephemeral operator-only progress; never interpreted as qualification."""
        self.board.state.update(
            step=event.get("optimizer_step", self.board.state.get("step")),
            prefix=grade,
            phase=event.get("phase", self.board.state.get("phase")),
            _rate_sample_eligible=True)

    def _candidate(self, grade, event):
        digest = event.get("cohort_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("SCHOOL_TELEMETRY_CANDIDATE_COHORT_REQUIRED")
        self.board.push("system", {"kind": "COMPARATOR", "grade": grade,
            "detail": ("Same-cohort incumbent replay " + digest[:12] +
                       f" | {len(event.get('incumbent_comparisons', []))} complete incumbents")},
            redraw=False)

    def _capability_best(self, grade, event):
        """One student's best capability slots do not mean grade mastery."""
        step, caps = event.get("optimizer_step"), event.get("capabilities")
        rubric, scores = event.get("rubric"), event.get("scores") or {}
        sha = event.get("student_sha256")
        if (type(step) is not int or not caps or
                not isinstance(sha, str) or len(sha) != 64 or
                not isinstance(rubric, str) or len(rubric) != 64 or
                not isinstance(scores, dict) or
                set(caps) != set(scores) or
                any(not isinstance(scores[cap], dict) or
                    type(scores[cap].get("correct")) is not int or
                    type(scores[cap].get("total")) is not int or
                    scores[cap]["total"] <= 0 or
                    not 0 <= scores[cap]["correct"] <= scores[cap]["total"]
                    for cap in caps)):
            raise ValueError("SCHOOL_CAPABILITY_BEST_PROVENANCE_REQUIRED")
        scored = ", ".join(
            f"{cap} {scores[cap]['correct']}/{scores[cap]['total']}"
            for cap in sorted(caps))
        self.board.push("system", {"kind": "CAP BEST", "grade": grade,
                        "detail": (f"CAPABILITY BEST SAVED: {scored} at step {step} | "
                                   f"checkpoint {sha[:10]} | TITLE SEPARATE | "
                                   f"NOT grade mastery")},
                        redraw=True)

    def _title_correct(self, capability: str, total: int) -> int | None:
        for row in getattr(self.board, "_champion_rows", ()):
            if row.get("capability") != capability:
                continue
            best = row.get("best")
            if not isinstance(best, str) or "/" not in best:
                return None
            left, right = best.split("/", 1)
            try:
                correct, recorded_total = int(left), int(right)
            except ValueError:
                return None
            if recorded_total == total and 0 <= correct <= recorded_total:
                return correct
        return None

    def _visit(self, grade, event):
        generation = event.get("generation")
        live_ephemeral = event.get("_live_ephemeral") is True
        if (not live_ephemeral and type(generation) is int and
                generation in self.live_projected_generations):
            self.live_projected_generations.remove(generation)
            event["_dashboard_redraw"] = False
            return
        if live_ephemeral:
            if type(generation) is not int:
                raise ValueError("SCHOOL_TELEMETRY_LIVE_VISIT_GENERATION_REQUIRED")
            if generation in self.live_projected_generations:
                return
            self.live_projected_generations.add(generation)
        self.visits += 1
        cap = event.get("capability")
        if not cap:
            raise ValueError("SCHOOL_TELEMETRY_CAPABILITY_REQUIRED")
        before = event.get("source_training_accuracy_before")
        after = event.get("source_training_accuracy_after")
        if type(after) in (int, float) and 0 <= after <= 1:
            self.last_source_training[cap] = (after, event.get("optimizer_step"))
        strategy = event.get("strategy") or {}
        unavailable = set(event.get("unavailable_teacher_dimensions") or ())
        policy = event.get("teacher_policy", "-")
        gain = _delta(event.get("teacher_reward"))
        retention = event.get("candidate_retention")
        if isinstance(retention, dict):
            probe_before = retention.get("active_probe_before")
            probe_after = retention.get("active_probe_after")
            probe_total = retention.get("active_probe_total")
        else:
            probe_before = probe_after = probe_total = None
        top = (self._title_correct(cap, probe_total)
               if type(probe_total) is int and probe_total > 0 else None)
        result, reason = _candidate_result_reason(event)
        row = {
            "capability": cap, "attempt": self.visits,
            "strategy": policy[:10], "lr": _scaled_lr(strategy.get("lr")),
            "method": _instruction_method_text(event),
            "train": (_percent(before) + ">" + _percent(after)),
            "score_line": _score_quad(probe_before, top, probe_after, probe_total),
            "reward": gain,
            "loss": _display(event.get("loss")),
            "gradient": (f"{event['gradient_norm']:.2f}"
                         if type(event.get("gradient_norm")) in (float, int) else "-"),
            "old": _delta(event.get("earlier_grade_delta_pp"), pp=True),
            "decision": _candidate_admission_text(event),
            "result": result,
            "reason": reason,
            "warnings": _warning_text(event),
        }
        self.board.rows["CANDIDATES"].append(row)
        retention_row = _candidate_retention_row(event, grade, self.visits)
        if retention_row is not None:
            self.board.rows["SENTINEL & RETENTION"].append(retention_row)
        association = _association_text(event)
        if association is not None:
            self.board.push("system", {
                "kind": "COMPOSE", "grade": grade,
                "detail": association + " | " + cap,
            }, redraw=False)
        teacher = {"grade": grade, "capability": cap,
                   "attempt": self.visits, "policy": policy[:10],
                   "lr": _scaled_lr(strategy.get("lr")),
                   "depth": _whole(strategy.get("depth")),
                   "contrast": _whole(strategy.get("contrast")),
                   "credit": gain, "soup": "-", "cover": "-", "parent": "-"}
        for field in ("old", "preview", "distill"):
            if field == "old":
                teacher[field] = "OFF" if field in unavailable else _whole(strategy.get(field))
            else:
                teacher[field] = "OFF" if field in unavailable else _display(strategy.get(field))
        teacher.update(_teacher_vnext_fields(event, self.teacher_policy_health))
        self.board.rows["SOUP & TEACHER"].append(teacher)
        attempted = event.get("attempted_optimizer_updates", 0)
        if type(attempted) is not int or attempted < 0:
            raise ValueError("SCHOOL_TELEMETRY_ATTEMPTED_OPTIMIZER_UPDATES_INVALID")
        retained = event.get("retained_optimizer_updates", 0)
        if type(retained) is not int or retained < 0:
            raise ValueError("SCHOOL_TELEMETRY_RETAINED_OPTIMIZER_UPDATES_INVALID")
        attempted_total = self.board.state.get("attempted_steps", 0)
        if type(attempted_total) is not int or attempted_total < 0:
            attempted_total = 0
        retained_total = self.board.state.get("retained_steps", 0)
        if type(retained_total) is not int or retained_total < 0:
            retained_total = 0
        retained_visits = self.board.state.get("retained_visits", 0)
        if type(retained_visits) is not int or retained_visits < 0:
            retained_visits = 0
        self.board.state.update(step=event.get("optimizer_step", self.board.state.get("step")),
                                attempted_steps=attempted_total + attempted,
                                retained_steps=retained_total + retained,
                                retained_visits=retained_visits + (1 if retained > 0 else 0),
                                visits=self.visits, prefix=grade,
                                phase=event.get("next_phase", self.board.state.get("phase")),
                                _rate_sample_eligible=(
                                    event.get("checkpoint_status") != "RECORDED_AT_BOUNDARY"))

    def _exam(self, grade, event):
        rubric = event.get("rubric") or event.get("exam_rubric_sha256")
        if not rubric:
            raise ValueError("SCHOOL_TELEMETRY_EXAM_RUBRIC_REQUIRED")
        scores = event.get("scores") or {}
        if not scores:
            raise ValueError("SCHOOL_TELEMETRY_EXAM_SCORES_REQUIRED")
        step = event.get("optimizer_step", self.board.state.get("step"))
        checkpoint = event.get("student_sha256")
        if not checkpoint:
            raise ValueError("SCHOOL_TELEMETRY_EXAM_CHECKPOINT_REQUIRED")
        live = (
            event.get("event") in (
                "SCHOOL_LIVE_EXAM_COMMITTED",
                "SCHOOL_FLASH_ROUTINE_EXAM_COMMITTED")
            or historical_live_exam(event.get("event")))
        scope = event.get("assessment_scope_sha256", "")
        cohort_sha = event.get("cohort_sha256") if live else None
        if live and (not isinstance(cohort_sha, str) or len(cohort_sha) != 64 or
                     not event.get("cohort_file") or not event.get("generator_version")):
            raise ValueError("SCHOOL_TELEMETRY_LIVE_COHORT_PROVENANCE_REQUIRED")
        cohort = defaultdict(dict)
        for cap, raw in scores.items():
            score_grade = (raw.get("grade") or
                           historical_capability_grade(cap, grade))
            if (raw.get("checkpoint_sha256", checkpoint) != checkpoint or
                    raw.get("optimizer_step", step) != step):
                raise ValueError("SCHOOL_TELEMETRY_EXAM_CHECKPOINT_MISMATCH")
            correct, total = raw.get("correct"), raw.get("total")
            if (type(correct) is not int or type(total) is not int or
                    total <= 0 or not 0 <= correct <= total):
                raise ValueError("SCHOOL_TELEMETRY_SCORE_INVALID")
            cohort[score_grade][cap] = (correct, total)
        target_evaluated = grade in cohort

        # Validate the full exam before emitting any dashboard rows. Historical
        # retained runs briefly reused one scope receipt while stagnation
        # withholding changed the actually scored inventory. Keep the receipt
        # visible, but never compare unlike inventories as if they were one exam.
        effective_scopes = {}
        for g, caps in cohort.items():
            shape = tuple(sorted((cap, total) for cap, (_, total) in caps.items()))
            reported_key = (g, rubric, scope)
            shape_key = (g, rubric, scope, shape)
            previous_shape = self.reported_scope_inventory.get(reported_key)
            effective_scope = self.scope_variants.get(shape_key)
            if effective_scope is None:
                if previous_shape is None or previous_shape == shape:
                    effective_scope = scope
                elif historical_withheld_inventory_change_explains(
                        event, g, previous_shape, shape):
                    effective_scope = _inventory_scope(scope, caps)
                else:
                    raise ValueError("SCHOOL_TELEMETRY_EXAM_RUBRIC_ITEMS_DRIFT")
                self.scope_variants[shape_key] = effective_scope
            effective_scopes[g] = effective_scope
            self.reported_scope_inventory[reported_key] = shape

        for g, caps in sorted(cohort.items()):
            self._grade(g)
            effective_scope = effective_scopes[g]
            total = sum(x[1] for x in caps.values())
            correct = sum(x[0] for x in caps.values())
            report = ExamScore(g, rubric, correct, total, step, checkpoint,
                               event.get("generation", 0), caps, effective_scope)
            key = (g, rubric, effective_scope)
            prev = self.latest.get(key)
            start = self.start.setdefault(key, report)
            best = self.best.get(key)
            if best is None or correct * best.total > best.correct * total:
                self.best[key] = report
            best = self.best[key]
            self.latest[key] = report
            same_cohort = not live or self.exam_cohorts.get(key) == cohort_sha
            if live:
                self.era_cohorts[key].add(cohort_sha)
            for cap, (score, count) in sorted(caps.items()):
                self.board.state["grew"] = self.growth.observe(
                    g, cap, score, count)
                cap_key = (cap, rubric, effective_scope)
                baseline = self.start_cap.setdefault(cap_key, (score, count))
                earlier = self.last_cap.get(cap_key)
                gain = score - earlier[0] if earlier and same_cohort else None
                self.board.rows["BRIDGE FAMILIES"].append({
                    "grade": g, "family": cap, "attempt": report.generation,
                    "step": step or "-",
                    "start": f"{baseline[0]}/{baseline[1]}",
                    "before": f"{earlier[0]}/{earlier[1]}" if earlier and same_cohort else "-",
                    "after": f"{score}/{count}",
                    "gain": f"{gain:+d}" if gain is not None else "-",
                })
                self.last_cap[cap_key] = (score, count)
            champion = self.champions.get(g)
            epoch = event.get("championship_epoch") or {}
            earned = tuple(
                cap for cap in epoch.get("earned_roles", ())
                if (isinstance(cap, str) and
                    historical_capability_grade(cap, grade) == g))
            title_decisions = tuple(
                decision for decision in epoch.get("cross_origin_decisions", ())
                if isinstance(decision, dict) and decision.get("grade") == g)
            withheld = tuple(
                cap for cap in event.get("withheld_capabilities", ())
                if isinstance(cap, str))
            if event.get("flash_scheduler_only") is True:
                label = f"FLASH SAMPLE {correct}/{total} | NO TITLES"
            elif earned:
                label = f"TITLE MOVED {len(earned)} | SAMPLE {correct}/{total}"
                detail = ", ".join(
                    f"{cap} {caps[cap][0]}/{caps[cap][1]}"
                    for cap in earned if cap in caps)
                self.board.push("system", {
                    "kind": "CHAMPION", "grade": g,
                    "detail": f"Titles moved: {detail} | step {step}",
                }, redraw=False)
            elif live and isinstance(event.get("championship_epoch"), dict):
                settled = tuple(
                    decision for decision in title_decisions
                    if decision.get("decision") == "TITLE_MATCH_ALREADY_SETTLED")
                label = (f"PAIR ALREADY SETTLED | SAMPLE {correct}/{total}"
                         if settled and len(settled) == len(title_decisions)
                         else f"NO TITLE CHANGE | SAMPLE {correct}/{total}")
                if title_decisions:
                    reasons = ", ".join(sorted({
                        str(decision.get("decision", "UNKNOWN"))
                        for decision in title_decisions
                    }))
                    self.board.push("system", {
                        "kind": "CHAMPION", "grade": g,
                        "detail": f"No title change: {reasons} | step {step}",
                    }, redraw=False)
                elif withheld:
                    self.board.push("system", {
                        "kind": "CHAMPION", "grade": g,
                        "detail": ("No title decision; withheld NOT_MEASURED: " +
                                   ", ".join(sorted(withheld)) + f" | step {step}"),
                    }, redraw=False)
            elif champion and correct < total:
                label = f"CURRENT REGRESSION | SAMPLE {correct}/{total}"
            elif champion:
                label = f"GRADE CHAMPION EXISTS | PASS {correct}/{total}"
            elif correct == total:
                label = "100% EXAM; GATE PENDING"
            else:
                label = f"{'GENERATED' if live else 'SEALED'} EXAM {correct}/{total} | {event.get('phase', '?')}"
            self.board.rows["GRADES & MASTERY"].append({
                "visit": self.visits, "grade": g, "step": step or "-",
                "attempt": report.generation,
                "start": f"{start.correct}/{start.total}",
                "latest": f"{correct}/{total}", "best": f"{best.correct}/{best.total}",
                "to100": str(total-correct), "right_pct": f"{100*correct/total:.1f}%",
                "outcome": label, "mastered": bool(champion),
            })
            if live:
                self.exam_cohorts[key] = cohort_sha
        cumulative_caps = {
            cap: score for grade_caps in cohort.values()
            for cap, score in grade_caps.items()
        }
        cumulative_scope = (
            _inventory_scope(scope, cumulative_caps)
            if any(value != scope for value in effective_scopes.values())
            else scope
        )
        self._cumulative_exam(
            cohort, rubric, cumulative_scope,
            step, event.get("phase"))
        # The A+B cohort reports both rows, but the operator summary must
        # identify the grade whose scheduled exam just completed, especially
        # during the Billy Madison backward A replay.
        self.last_exam_grade = grade if target_evaluated else None
        self.board.state.update(phase=event.get("phase", self.board.state.get("phase")),
                                prefix=grade, step=step,
                                _rate_sample_eligible=True)
        if not target_evaluated:
            observed = "+".join(sorted(cohort))
            detail = (
                f"{grade} NOT EVALUATED IN THIS SAMPLE | observed {observed} | "
                f"{event.get('phase', '?')}")
            self.board.push("system", {
                "kind": "EXAM SCOPE", "grade": grade, "detail": detail,
            }, redraw=False)
            self.board.operator_lines = [
                f"{grade} NOT EVALUATED IN THIS SAMPLE | observed {observed} "
                f"@step {step or '-'}",
                "Dashboard remains available; no score is inferred for the omitted grade.",
            ]
        for system_row in _diagnostic_system_rows(event, grade):
            self.board.push("system", system_row, redraw=False)
        if target_evaluated:
            self._summary()

    def _cumulative_exam(self, cohort, rubric, scope, step, phase):
        """Show one checkpoint's complete grade-prefix exam, never summed bests."""
        if len(cohort) < 2 or set(cohort) != set(self.grades):
            return
        key = (tuple(sorted(cohort)), rubric, scope)
        correct = sum(score for caps in cohort.values() for score, _ in caps.values())
        total = sum(count for caps in cohort.values() for _, count in caps.values())
        self.board.state["_all_grade_correct"] = correct
        self.board.state["_all_grade_total"] = total
        best = self.cumulative_best.get(key)
        if best is None or correct * best[1] > best[0] * total:
            best = (correct, total, step)
            self.cumulative_best[key] = best
        status = ("PROGRESSION GATE MET / MASTERY DEBT"
                  if phase == "AWAITING_NEXT_GRADE_WITH_DEBT" else
                  "GATE MET" if correct == total and phase in
                  ("AWAITING_NEXT_GRADE", "WHOLE_SCHOOL_MASTERED") else
                  "REVALIDATION PENDING" if correct == total else
                  f"{total}/{total} REQUIRED")
        self.cumulative_latest = (key, correct, total, step, status)
        label = "+".join(key[0])
        detail = (f"{status} | latest {correct}/{total} | "
                  f"best same student {best[0]}/{best[1]}")
        rows = self.board.rows["SYSTEM & QUALIFICATION"]
        new_row = {"kind": "CUMULATIVE", "grade": label, "detail": detail}
        for index, existing in enumerate(rows):
            if existing["kind"] == "CUMULATIVE":
                rows[index] = new_row
                break
        else:
            rows.append(new_row)

    def _summary(self):
        grade = self.last_exam_grade
        if grade is None:
            return
        reports = [v for (g, _, _), v in self.latest.items() if g == grade]
        report = max(
            reports,
            key=lambda item: (
                item.generation if type(item.generation) is int else -1,
                item.step if type(item.step) is int else -1,
            ),
            default=None,
        )
        if report is None:
            return
        key = (grade, report.rubric, report.assessment_scope)
        start = self.start[key]
        best = self.best[key]
        latest = report
        live = key in self.exam_cohorts
        category = "GENERATED SAMPLE" if live else "SEALED"
        self.board.operator_lines = [
            f"START {category} {grade} {start.correct}/{start.total} @step {start.step or '-'} | "
            f"LATEST {grade} {latest.correct}/{latest.total} @step {latest.step or '-'} | "
            f"{'BEST OBSERVED SAMPLE (not paired)' if live else 'BEST'} {grade} "
            f"{best.correct}/{best.total} @step {best.step or '-'}",
            f"TO100 {latest.total-latest.correct}/{latest.total} wrong ({'fresh sampled cohort' if live else 'sealed rubric'}) | "
            f"Source-train rewards are in-sample; independent sentinel NOT MEASURED",
        ]
        if live:
            count = len(self.era_cohorts.get(key, ()))
            self.board.operator_lines.append(
                f"HISTORY ERA {self.score_era} | {count} cohort{'s' if count != 1 else ''} | "
                f"TOP {best.correct}/{best.total} @step {best.step or '-'} | "
                "cross-cohort context, not a paired delta")
        if self.cumulative_latest is not None:
            key, correct, total, step, status = self.cumulative_latest
            best = self.cumulative_best[key]
            self.board.operator_lines.append(
                f"CUMULATIVE {'+'.join(key[0])}: {status}; latest {correct}/{total} @step {step}; "
                f"best SAME STUDENT {best[0]}/{best[1]} @step {best[2]}. "
                "Individual grade champions are not additive.")
        # A diagnostic observation, not an optimizer signal. Individual
        # source-training measurements may come from different checkpoints.
        families = tuple(latest.capabilities)
        if (not live and latest.correct < latest.total and families and
                all(cap in self.last_source_training and
                    self.last_source_training[cap][0] >= .99 for cap in families)):
            self.board.operator_lines.append(
                f"GENERALIZATION GAP OBSERVED: recent source-train accuracy >=99% "
                f"for {len(families)}/{len(families)} capabilities (different steps); "
                f"{'generated' if live else 'sealed'} {latest.correct}/{latest.total} at one checkpoint")

    def _sentinel(self, grade, event):
        if event.get("partition") != "independent_validation":
            raise ValueError("SCHOOL_TELEMETRY_SENTINEL_PARTITION_NOT_INDEPENDENT")
        _source_provenance(event)
        ce = _delta(event.get("cross_entropy_delta"))
        prob = _delta(event.get("correct_probability_delta"))
        margin = _delta(event.get("margin_delta"))
        sent = _delta(event.get("sentinel_delta_pp"), pp=True)
        row = {
            "grade": grade, "attempt": event.get("generation", "-"),
            "capability": event.get("capability") or event.get("family") or "GRADE",
            "target": "INDEP",
            "target_delta": _delta(event.get("probe_delta_pp"), pp=True),
            "protected": sent,
            "worst": _delta(event.get("worst_delta_pp"), pp=True),
            "decision": "SENTINEL",
            "result": "SENTINEL",
            "evidence": (f"{event.get('family_count', '?')} families | "
                         f"CE {ce} P(C) {prob} M {margin}"),
            # Retain raw semantic aliases for programmatic consumers of v1.
            "probe": _delta(event.get("probe_delta_pp"), pp=True),
            "sent": sent, "ce": ce, "prob": prob, "margin": margin,
        }
        self.board.rows["SENTINEL & RETENTION"].append(row)

    def _soup(self, grade, event):
        if event.get("teacher_only") is not True:
            raise ValueError("SCHOOL_TELEMETRY_SOUP_TEACHER_ONLY_REQUIRED")
        digest = event.get("teacher_digest")
        if (not isinstance(digest, str) or len(digest) != 64 or
                any(ch not in string.hexdigits for ch in digest)):
            raise ValueError("SCHOOL_TELEMETRY_SOUP_SOURCE_PROVENANCE_REQUIRED")
        self.board.rows["SOUP & TEACHER"].append({
            "grade": grade,
            "capability": event.get("capability") or event.get("family") or grade,
            "attempt": event.get("generation", "-"),
            "policy": "TEACHER SOUP", "lr": "-", "depth": "-", "contrast": "-",
            "old": "-", "preview": "-", "distill": "-",
            "credit": _delta(event.get("teacher_credit")),
            "soup": _display(event.get("soup_kl")),
            "cover": _percent(event.get("coverage")),
            "sup": _display(event.get("supervised_loss")),
            "parent": _display(event.get("parent_kl")),
            "bridge_ce": _display(event.get("bridge_ce")),
        })
        self.board.push("system", {"kind": "SOUP", "grade": grade,
            "detail": f"Measured sup={_display(event.get('supervised_loss'))} "
                      f"bridge CE={_display(event.get('bridge_ce'))}; teacher only"}, redraw=False)

    def _family(self, grade, event):
        """Future source/NI constructor family probes, never grade mastery."""
        _source_provenance(event)
        if event.get("partition") not in ("independent_validation", "source_train"):
            raise ValueError("SCHOOL_TELEMETRY_FAMILY_UNKNOWN_PARTITION")
        family = event.get("family")
        before, after = event.get("before"), event.get("after")
        if not family or not isinstance(before, dict) or not isinstance(after, dict):
            raise ValueError("SCHOOL_TELEMETRY_FAMILY_SCORE_REQUIRED")
        for score in (before, after):
            if (type(score.get("correct")) is not int or type(score.get("total")) is not int or
                    score["total"] <= 0 or not 0 <= score["correct"] <= score["total"]):
                raise ValueError("SCHOOL_TELEMETRY_FAMILY_SCORE_INVALID")
        if before["total"] != after["total"]:
            raise ValueError("SCHOOL_TELEMETRY_FAMILY_RUBRIC_COUNT_DRIFT")
        self.board.rows["BRIDGE FAMILIES"].append({
            "grade": grade, "family": family,
            "start": "-", "before": f"{before['correct']}/{before['total']}",
            "after": f"{after['correct']}/{after['total']}",
            "gain": f"{after['correct']-before['correct']:+d}",
            "attempt": event.get("generation", "-"),
        })

    def _qualification(self, grade, event):
        self.board.push("system", {"kind": "QUALIFICATION", "grade": grade,
            "detail": f"{event.get('status', 'UNKNOWN')}: {event.get('details', '-')}"},
            redraw=False)

    def _autonomy(self, grade, event):
        """Render receipt-backed autonomous curriculum progress without scoring it."""
        name = event["event"]
        capability = event.get("capability")
        obligation = event.get("obligation")

        if name == "SCHOOL_AUTONOMY_SOURCE_COVERAGE_BLOCKED":
            debt = event.get("debt")
            if (not isinstance(debt, (list, tuple)) or not debt or
                    any(not isinstance(item, str) or not item for item in debt) or
                    event.get("model_and_optimizer_unchanged") is not True):
                raise ValueError("SCHOOL_AUTONOMY_SOURCE_COVERAGE_RECEIPT_INVALID")
            detail = "SOURCE COVERAGE BLOCKED | " + ", ".join(debt)
        elif name == "SCHOOL_AUTONOMY_EVIDENCE_RECORDED":
            if (not isinstance(capability, str) or not capability or
                    not isinstance(obligation, str) or not obligation or
                    type(event.get("passed")) is not bool or
                    type(event.get("optimizer_step")) is not int or
                    any(not isinstance(event.get(field), str) or len(event[field]) != 64
                        for field in ("cohort_sha256", "student_sha256"))):
                raise ValueError("SCHOOL_AUTONOMY_EVIDENCE_RECEIPT_INVALID")
            outcome = "PASS" if event["passed"] else "FAIL"
            detail = (f"{outcome} {capability} | {obligation} | "
                      f"cohort {event['cohort_sha256'][:12]} | "
                      f"step {event['optimizer_step']}")
        elif name == "SCHOOL_AUTONOMY_TEACHING_RECORDED":
            if (not isinstance(capability, str) or not capability or
                    not isinstance(obligation, str) or not obligation or
                    type(event.get("optimizer_step")) is not int or
                    any(not isinstance(event.get(field), str) or len(event[field]) != 64
                        for field in ("parent_student_sha256", "student_sha256"))):
                raise ValueError("SCHOOL_AUTONOMY_TEACHING_RECEIPT_INVALID")
            detail = (f"TEACH {capability} | {obligation} | "
                      f"{event['parent_student_sha256'][:10]} > "
                      f"{event['student_sha256'][:10]} | step {event['optimizer_step']}")
        else:
            if (not isinstance(capability, str) or not capability or
                    type(event.get("optimizer_step")) is not int or
                    not isinstance(event.get("student_sha256"), str) or
                    len(event["student_sha256"]) != 64 or
                    event.get("retained_optimizer_updates") != 0):
                raise ValueError("SCHOOL_AUTONOMY_VISIT_RECEIPT_INVALID")
            action = ("EVIDENCE COMPLETE" if
                      name == "SCHOOL_AUTONOMY_EVIDENCE_VISIT_COMPLETED"
                      else "QUALIFIED")
            detail = (f"{action} {capability} | zero-update scheduler advance | "
                      f"step {event['optimizer_step']}")

        self.board.push("system", {
            "kind": "AUTONOMY", "grade": grade, "detail": detail,
        }, redraw=False)

    def _resource(self, grade, event):
        for field in ("free_bytes", "reserve_bytes", "estimated_write_bytes"):
            if type(event.get(field)) is not int or event[field] < 0:
                raise ValueError("SCHOOL_TELEMETRY_DISK_BUDGET_INVALID:" + field)
        free, reserve, estimate = (event[field] for field in
                                   ("free_bytes", "reserve_bytes", "estimated_write_bytes"))
        ready = free >= reserve + estimate
        detail = (f"{'READY' if ready else 'BLOCKED'} | free {free/1024**3:.2f} GiB | "
                  f"reserve {reserve/1024**3:.1f} GiB + "
                  f"next write {estimate/1024**3:.2f} GiB")
        records = self.board.rows["SYSTEM & QUALIFICATION"]
        new_row = {"kind": "DISK", "grade": grade, "detail": detail}
        for i, existing in enumerate(records):
            if existing["kind"] == "DISK":
                records[i] = new_row
                break
        else:
            records.append(new_row)
        self.board.state["disk_ready"] = ready

    def _stop(self, grade, event):
        reason = event["stop_reason"]
        if all(field in event for field in
               ("free_bytes", "reserve_bytes", "estimated_write_bytes")):
            self._resource(grade, event)
        self.board.mode = "STOPPED | " + reason
        self.board.push("system", {"kind": "STOP", "grade": grade,
            "detail": f"{reason} | {event['visits_this_command']} visits | "
                      f"{event['elapsed_seconds']:.1f}s | step {event['optimizer_step']}"},
            redraw=False)
        quarantined = event.get("stagnation_quarantined") or []
        if quarantined:
            self.board.push("system", {"kind": "STAGNATION", "grade": grade,
                "detail": "WITHHELD THIS RUN | " + ", ".join(quarantined) +
                          " | still required for graduation"}, redraw=False)
        self.board.state.update(
            stop=reason,
            step=event.get("optimizer_step", self.board.state.get("step")),
            _rate_sample_eligible=True)
