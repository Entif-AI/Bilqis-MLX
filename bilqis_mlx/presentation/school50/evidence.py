from __future__ import annotations

import string
from .formatting import _delta, _display, _percent, _source_provenance

class EvidenceProjection:
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
