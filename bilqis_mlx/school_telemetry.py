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

from .spiral_dashboard import Column


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
        unavailable = diagnostics.get("history_usable") is False
        detail = ("active " + ", ".join(warning_labels)
                  if warning_labels else "S3 unavailable" if unavailable else "no active warnings")
        if unavailable and warning_labels:
            detail += " | S3 unavailable"
        rows.append({"kind":"DIAGNOSTIC", "grade":grade,
                     "detail":detail + f" | {not_measured} NOT MEASURED"})
        if unavailable and diagnostics.get("history_issue"):
            rows.append({"kind": "HISTORY ISSUE", "grade": grade,
                         "detail": str(diagnostics["history_issue"])})
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
        Column("CAPABILITY", 13, "capability"),
        Column("VISIT", 5, "attempt", right=True),
        Column("POLICY", 10, "strategy", optional=True),
        Column("LR", 8, "lr", optional=True),
        Column("LESSON% BFR>AFTER", 18, "train"),
        Column("REWARD", 8, "reward", right=True),
        Column("LOSS", 8, "loss", optional=True),
        Column("GRAD", 10, "gradient", optional=True),
        Column("METHOD", 12, "method", optional=True),
        Column("OLDpp", 8, "old", optional=True, right=True),
        Column("DECISION / REASON", 30, "decision"))),
    ("SENTINEL & RETENTION", (
        Column("GRADE", 6, "grade"),
        Column("EXAM", 6, "attempt", right=True),
        Column("EXAMpp", 9, "probe", right=True),
        Column("WORSTpp", 9, "worst", right=True),
        Column("SENTpp", 9, "sent", right=True),
        Column("CEd", 9, "ce", optional=True, right=True),
        Column("P(C)d", 9, "prob", optional=True, right=True),
        Column("MARGd", 9, "margin", optional=True, right=True),
        Column("EVIDENCE", 25, "evidence", optional=True))),
    ("SOUP & TEACHER", (
        Column("GRADE", 5, "grade"),
        Column("VISIT", 5, "attempt", right=True),
        Column("POLICY", 10, "policy", optional=True),
        Column("LR", 8, "lr"),
        Column("DEPTH", 5, "depth", right=True),
        Column("CONTRAST", 8, "contrast", right=True),
        Column("SOUP_KL", 8, "soup", optional=True, right=True),
        Column("COVER", 7, "cover", optional=True, right=True),
        Column("OLD", 7, "old", optional=True),
        Column("PREVIEW", 8, "preview", optional=True),
        Column("DISTILL", 8, "distill", optional=True),
        Column("CREDIT", 7, "credit", right=True),
        Column("SUP_CE", 9, "sup", optional=True, right=True),
        Column("PAR_KL", 9, "parent", optional=True, right=True),
        Column("BRG_CE", 9, "bridge_ce", optional=True, right=True))),
    ("BRIDGE FAMILIES", (
        Column("GRADE", 5, "grade"),
        Column("FAMILY", 22, "family"),
        Column("FIRST", 7, "first", right=True),
        Column("PREVIOUS", 8, "before", right=True),
        Column("LATEST", 8, "after", right=True),
        Column("GAIN", 6, "gain", right=True),
        Column("EXAM", 5, "attempt", optional=True, right=True))),
    ("GRADES & MASTERY", (
        Column("GRADE", 5, "grade"),
        Column("STEP", 9, "step", right=True),
        Column("FIRST", 7, "first", right=True),
        Column("LATEST", 7, "latest", right=True),
        Column("BEST", 7, "best", right=True),
        Column("TO100", 6, "to100", right=True),
        Column("RIGHT%", 7, "right_pct", right=True),
        Column("OUTCOME", 20, "outcome"))),
    ("SYSTEM & QUALIFICATION", (
        Column("TYPE", 15, "kind"),
        Column("GRADE", 6, "grade", optional=True),
        Column("DETAILS", 65, "detail"))),
)


EVENT_KINDS = {
    "GRADE_A_NEW_RUN_INITIALIZED": "init",
    "GRADE_A_TEACHER_VISIT_COMMITTED": "visit",
    "GRADE_A_EXAM_COMMITTED": "exam",
    "GRADE_A_LIVE_EXAM_COMMITTED": "exam",
    "SCHOOL_GRADE_B_TEACHER_VISIT_COMMITTED": "visit",
    "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED": "exam",
    "SCHOOL_GRADE_B_COURSE_ADMITTED": "init",
    "SCHOOL_TEACHER_VISIT_COMMITTED": "visit",
    "SCHOOL_LIVE_EXAM_COMMITTED": "exam",
    "SCHOOL_COURSE_ADMITTED": "init",
    "GRADE_A_SESSION_STOPPED": "stop",
    "SCHOOL_RUN_INITIALIZED": "init",
    "SCHOOL_VISIT_COMMITTED": "visit",
    "SCHOOL_EXAM_COMMITTED": "exam",
    "SCHOOL_SESSION_STOPPED": "stop",
    "SCHOOL_SENTINEL_COMMITTED": "sentinel",
    "SCHOOL_SOUP_COMMITTED": "soup",
    "SCHOOL_FAMILY_PROBE_COMMITTED": "family",
    "SCHOOL_RESOURCE_OBSERVED": "resource",
    "SCHOOL_CAPABILITY_BEST_COMMITTED": "capability_best",
    "SCHOOL_LIVE_CANDIDATE_COMPARED": "candidate",
    "SCHOOL_QUALIFICATION_COMMITTED": "qualification",
}


def _display(value: Any, *, decimals: int = 3) -> str:
    if type(value) in (float, int):
        if value and abs(value) < 0.5 * 10 ** (-decimals):
            return f"{value:.2e}"
        return f"{value:.{decimals}f}"
    return "-"


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


def _grade_from_capability(name: str, event_grade: str) -> str:
    prefix = name.split(".", 1)[0]
    return prefix if len(prefix) == 1 and prefix.isalpha() else event_grade


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
    """Incremental projection; all first/latest/best scores are from receipts."""

    def __init__(self, board, *, active_grades=("A",), champions=None):
        self.board = board
        self.grades = list(active_grades)
        self.champions = champions or {}
        self.first = {}   # (grade, complete-rubric) -> ExamScore
        self.latest = {}
        self.best = {}
        self.last_cap = {}  # (capability, complete-rubric) -> (correct,total)
        self.first_cap = {}
        self.last_source_training = {}  # capability -> (accuracy, optimizer_step)
        self.exam_cohorts = {}  # (grade, semantic rubric) -> last sampled cohort
        # Whole-student exam scores are distinct from separate per-grade bests.
        self.cumulative_best = {}  # (grades, rubric, scope) -> (correct, total, step)
        self.cumulative_latest = None  # (key, correct, total, step, status)
        self.visits = 0
        self.last_exam_grade = None
        self.board.grade_program = tuple(self.grades)

    def _grade(self, name):
        if name not in self.grades:
            self.grades.append(name)
            self.board.grade_program = tuple(self.grades)

    def ingest(self, event: dict):
        if (event.get("event", "").startswith("SCHOOL_") and
                event.get("telemetry_schema", TELEMETRY_VERSION) != TELEMETRY_VERSION):
            raise ValueError("SCHOOL_TELEMETRY_UNSUPPORTED_SCHEMA")
        kind = EVENT_KINDS.get(event.get("event"))
        if kind is None:
            return
        grade = event.get("grade") or ("A" if event["event"].startswith("GRADE_A_") else None)
        if kind != "init" and not grade:
            raise ValueError("SCHOOL_TELEMETRY_GRADE_REQUIRED")
        if grade:
            self._grade(grade)
        {
            "init": self._init,
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
        }[kind](grade, event)

    def _init(self, grade, event):
        self.board.state["step"] = event.get("optimizer_step", self.board.state.get("step"))

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
        self.board.push("system", {"kind": "CAP BEST", "grade": grade,
                        "detail": (f"Best slots: {', '.join(sorted(caps))} "
                                   f"at step {step} | NOT grade mastery")},
                        redraw=False)

    def _visit(self, grade, event):
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
        train = (_percent(before) + ">" + _percent(after))
        gain = _delta(event.get("teacher_reward"))
        row = {
            "capability": cap, "attempt": self.visits,
            "strategy": policy[:10], "lr": _display(strategy.get("lr"), decimals=5),
            "method": event.get("instruction_method", "-"),
            "train": train, "reward": gain,
            "loss": _display(event.get("loss")),
            "gradient": (f"{event['gradient_norm']:.3g}" if type(event.get("gradient_norm")) in (float,int) else "-"),
            "old": _delta(event.get("earlier_grade_delta_pp"), pp=True),
            "decision": _teacher_decision_text(event.get("teacher_decision")),
        }
        self.board.rows["CANDIDATES"].append(row)
        teacher = {"grade": grade, "attempt": self.visits, "policy": policy[:10],
                   "lr": _display(strategy.get("lr"), decimals=5),
                   "depth": strategy.get("depth", "-"),
                   "contrast": _display(strategy.get("contrast")),
                   "credit": gain, "soup": "-", "cover": "-", "parent": "-"}
        for field in ("old", "preview", "distill"):
            teacher[field] = "OFF" if field in unavailable else _display(strategy.get(field))
        self.board.rows["SOUP & TEACHER"].append(teacher)
        self.board.state.update(step=event.get("optimizer_step", self.board.state.get("step")),
                                visits=self.visits, prefix=grade,
                                phase=event.get("next_phase", self.board.state.get("phase")))

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
        live = event.get("event") in ("GRADE_A_LIVE_EXAM_COMMITTED",
                                       "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED", "SCHOOL_LIVE_EXAM_COMMITTED")
        scope = event.get("assessment_scope_sha256", "") if event.get("event") == "SCHOOL_LIVE_EXAM_COMMITTED" else ""
        cohort_sha = event.get("cohort_sha256") if live else None
        if live and (not isinstance(cohort_sha, str) or len(cohort_sha) != 64 or
                     not event.get("cohort_file") or not event.get("generator_version")):
            raise ValueError("SCHOOL_TELEMETRY_LIVE_COHORT_PROVENANCE_REQUIRED")
        cohort = defaultdict(dict)
        for cap, raw in scores.items():
            score_grade = raw.get("grade") or _grade_from_capability(cap, grade)
            if (raw.get("checkpoint_sha256", checkpoint) != checkpoint or
                    raw.get("optimizer_step", step) != step):
                raise ValueError("SCHOOL_TELEMETRY_EXAM_CHECKPOINT_MISMATCH")
            correct, total = raw.get("correct"), raw.get("total")
            if (type(correct) is not int or type(total) is not int or
                    total <= 0 or not 0 <= correct <= total):
                raise ValueError("SCHOOL_TELEMETRY_SCORE_INVALID")
            cohort[score_grade][cap] = (correct, total)
        if grade not in cohort:
            raise ValueError("SCHOOL_TELEMETRY_EXAM_TARGET_GRADE_NOT_EVALUATED")

        # Validate the full exam before emitting any dashboard rows.
        for g, caps in cohort.items():
            previous = self.latest.get((g, rubric, scope))
            if previous is not None and (set(previous.capabilities) != set(caps) or
                any(previous.capabilities[k][1] != caps[k][1] for k in caps)):
                raise ValueError("SCHOOL_TELEMETRY_EXAM_RUBRIC_ITEMS_DRIFT")

        for g, caps in sorted(cohort.items()):
            self._grade(g)
            total = sum(x[1] for x in caps.values())
            correct = sum(x[0] for x in caps.values())
            report = ExamScore(g, rubric, correct, total, step, checkpoint,
                               event.get("generation", 0), caps, scope)
            key = (g, rubric, scope)
            prev = self.latest.get(key)
            first = self.first.setdefault(key, report)
            best = self.best.get(key)
            if best is None or correct * best.total > best.correct * total:
                self.best[key] = report
            best = self.best[key]
            self.latest[key] = report
            same_cohort = not live or self.exam_cohorts.get(key) == cohort_sha
            for cap, (score, count) in sorted(caps.items()):
                baseline = self.first_cap.setdefault((cap, rubric, scope), (score, count))
                earlier = self.last_cap.get((cap, rubric, scope))
                gain = score - earlier[0] if earlier and same_cohort else None
                self.board.rows["BRIDGE FAMILIES"].append({
                    "grade": g, "family": cap, "attempt": report.generation,
                    "first": f"{baseline[0]}/{baseline[1]}",
                    "before": f"{earlier[0]}/{earlier[1]}" if earlier and same_cohort else "-",
                    "after": f"{score}/{count}",
                    "gain": f"{gain:+d}" if gain is not None else "-",
                })
                self.last_cap[(cap, rubric, scope)] = (score, count)
            # This is a sealed-exam-to-sealed-exam change. It is NOT the
            # independent sentinel/held-out teacher reward channel.
            if prev and same_cohort:
                pp = 100 * (correct / total - prev.correct / prev.total)
                worst = min(100 * (caps[c][0] / caps[c][1] -
                         prev.capabilities[c][0] / prev.capabilities[c][1]) for c in caps)
            else:
                pp, worst = None, None
            self.board.rows["SENTINEL & RETENTION"].append({
                "grade": g, "attempt": report.generation,
                "probe": _delta(pp, pp=True), "worst": _delta(worst, pp=True),
                "sent": "-", "ce": "-", "prob": "-", "margin": "-",
                "evidence": ("GENERATED COHORT; NO SENTINEL" if live else
                             "SEALED EXAM; NO SENTINEL"),
            })
            champion = self.champions.get(g)
            label = ("CHAMPION SAVED; FRESH SAMPLE" if live and champion else
                     "CHAMPION SAVED; CURRENT REGRESSION" if champion and correct < total else
                     "CHAMPION RECORDED; CURRENT PASS" if champion else
                     "100% EXAM; GATE PENDING" if correct == total else
                     f"{'GENERATED' if live else 'SEALED'} EXAM {correct}/{total} | {event.get('phase', '?')}")
            self.board.rows["GRADES & MASTERY"].append({
                "visit": self.visits, "grade": g, "step": step or "-",
                "first": f"{first.correct}/{first.total}",
                "latest": f"{correct}/{total}", "best": f"{best.correct}/{best.total}",
                "to100": str(total-correct), "right_pct": f"{100*correct/total:.1f}%",
                "outcome": label, "mastered": bool(champion),
            })
            if live:
                self.exam_cohorts[key] = cohort_sha
        self._cumulative_exam(cohort, rubric, scope, step, event.get("phase"))
        # The A+B cohort reports both rows, but the operator summary must
        # identify the grade whose scheduled exam just completed, especially
        # during the Billy Madison backward A replay.
        self.last_exam_grade = grade
        self.board.state.update(phase=event.get("phase", self.board.state.get("phase")),
                                prefix=grade, step=step)
        for system_row in _diagnostic_system_rows(event, grade):
            self.board.push("system", system_row, redraw=False)
        self._summary()

    def _cumulative_exam(self, cohort, rubric, scope, step, phase):
        """Show one checkpoint's complete grade-prefix exam, never summed bests."""
        if len(cohort) < 2 or set(cohort) != set(self.grades):
            return
        key = (tuple(sorted(cohort)), rubric, scope)
        correct = sum(score for caps in cohort.values() for score, _ in caps.values())
        total = sum(count for caps in cohort.values() for _, count in caps.values())
        best = self.cumulative_best.get(key)
        if best is None or correct * best[1] > best[0] * total:
            best = (correct, total, step)
            self.cumulative_best[key] = best
        status = ("GATE MET" if correct == total and phase in
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
        report = next((v for (g, _, _), v in reversed(tuple(self.latest.items())) if g == grade), None)
        if report is None:
            return
        key = (grade, report.rubric, report.assessment_scope)
        first = self.first[key]
        best = self.best[key]
        latest = report
        live = key in self.exam_cohorts
        category = "GENERATED SAMPLE" if live else "SEALED"
        self.board.operator_lines = [
            f"FIRST {category} {grade} {first.correct}/{first.total} @step {first.step or '-'} | "
            f"LATEST {grade} {latest.correct}/{latest.total} @step {latest.step or '-'} | "
            f"{'BEST OBSERVED SAMPLE (not paired)' if live else 'BEST'} {grade} "
            f"{best.correct}/{best.total} @step {best.step or '-'}",
            f"TO100 {latest.total-latest.correct}/{latest.total} wrong ({'fresh sampled cohort' if live else 'sealed rubric'}) | "
            f"Source-train rewards are in-sample; independent sentinel NOT MEASURED",
        ]
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
        self.board.rows["SENTINEL & RETENTION"].append({
            "grade": grade, "attempt": event.get("generation", "-"),
            "probe": _delta(event.get("probe_delta_pp"), pp=True),
            "worst": _delta(event.get("worst_delta_pp"), pp=True),
            "sent": _delta(event.get("sentinel_delta_pp"), pp=True),
            "ce": _delta(event.get("cross_entropy_delta")),
            "prob": _delta(event.get("correct_probability_delta")),
            "margin": _delta(event.get("margin_delta")),
            "evidence": f"INDEPENDENT {event.get('family_count', '?')} families",
        })

    def _soup(self, grade, event):
        if event.get("teacher_only") is not True:
            raise ValueError("SCHOOL_TELEMETRY_SOUP_TEACHER_ONLY_REQUIRED")
        digest = event.get("teacher_digest")
        if (not isinstance(digest, str) or len(digest) != 64 or
                any(ch not in string.hexdigits for ch in digest)):
            raise ValueError("SCHOOL_TELEMETRY_SOUP_SOURCE_PROVENANCE_REQUIRED")
        self.board.rows["SOUP & TEACHER"].append({
            "grade": grade, "attempt": event.get("generation", "-"),
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
            "first": "-", "before": f"{before['correct']}/{before['total']}",
            "after": f"{after['correct']}/{after['total']}",
            "gain": f"{after['correct']-before['correct']:+d}",
            "attempt": event.get("generation", "-"),
        })

    def _qualification(self, grade, event):
        self.board.push("system", {"kind": "QUALIFICATION", "grade": grade,
            "detail": f"{event.get('status', 'UNKNOWN')}: {event.get('details', '-')}"},
            redraw=False)

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
        self.board.state["stop"] = reason
