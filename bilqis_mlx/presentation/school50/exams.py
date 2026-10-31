from __future__ import annotations

from collections import defaultdict
from bilqis_mlx.compatibility.telemetry_events import (
    historical_capability_grade,
    historical_course_admission,
    historical_event_grade,
    historical_event_kind,
    historical_live_exam,
    historical_withheld_inventory_change_explains,
)
from .diagnostics import _diagnostic_system_rows
from .formatting import ExamScore, _inventory_scope

class ExamsProjection:
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
        if event.get("exam_plane") == "GENERALIZATION":
            self.board.push("system", {"kind": "HISTORICAL GENERALIZATION", "grade": grade,
                "detail": "PRESERVED IN LEDGER; EXCLUDED FROM ACTIVE MASTERY"}, redraw=False)
            return
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
