from __future__ import annotations

from bilqis_mlx.presentation.numeric_scope import PROFILE_ADOPTION_EVENTS, apply_profile_adoption
from bilqis_mlx.compatibility.telemetry_events import (
    historical_capability_grade,
    historical_course_admission,
    historical_event_grade,
    historical_event_kind,
    historical_live_exam,
    historical_withheld_inventory_change_explains,
)

class CurriculumProjection:
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
        if event["event"] in PROFILE_ADOPTION_EVENTS: return apply_profile_adoption(self, grade, event)
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
        self.board.state["graduations"] = self.graduations.begin_execution()
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
