from __future__ import annotations

from bilqis_mlx.presentation.teacher_vnext import teacher_fields as _teacher_vnext_fields
from .diagnostics import _candidate_retention_row
from .formatting import _delta, _display, _percent, _scaled_lr, _score_quad, _whole
from .labels import _association_text, _candidate_admission_text, _candidate_result_reason, _instruction_method_text, _warning_text

class CandidatesProjection:
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
