"""Minimal ordinary-mode facts that change future teacher learning policy."""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.bamf_operator.evidence_parts.support import candidate_attempt_id

def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_FIRST_STUDENT.INVALID, reason=reason)


_CONTROL_FIELDS = (
    "depth_control",
    "contrast_control",
    "effective_old_grade_examples",
    "fragile_preservation_delivered",
    "exact_miss_delivery_ids",
    "exact_miss_replay_delivered",
    "retention_support_delivered",
    "fresh_support_delivered",
    "weakness_targets_delivered",
    "priority_weakness_targets_delivered",
    "weakness_class_matches",
    "weakness_unavailable",
    "current_semantic_patterns_delivered",
    "current_semantic_patterns_required",
    "selected_answer_kinds",
)


class CandidateLearningTrace:
    """Retain only realized-action facts used to choose future teaching policy."""

    def __init__(self, selection, *, generation, accepted_manifest_sha256,
                 candidate_attempt_ordinal, parent_optimizer_step):
        identity = selection.visit.identity
        self.attempt_id = candidate_attempt_id(
            generation, accepted_manifest_sha256, identity.visit_id,
            candidate_attempt_ordinal)
        self.selected_option = selection.option_id
        self.parent_optimizer_step = parent_optimizer_step
        self._steps = 0
        self._batch_size = None
        self._policy_controls = []
        self._guidance_applied_steps = 0
        self._enrichment_examples = 0

    def delivery(self, _release, _capability, step, rows, **facts):
        expected = self.parent_optimizer_step + self._steps + 1
        if type(step) is not int or step != expected or not rows:
            _invalid("BAMF_LEARNING_TRACE_STEP_INVALID")
        size = len(rows)
        if self._batch_size is None:
            self._batch_size = size
        controls = facts.get("controls") or {}
        matches = controls.get("weakness_class_matches", {})
        if matches:
            delivered_ids = {row["id"] for row in rows}
            if not {row_id for ids in matches.values() for row_id in ids} <= delivered_ids:
                _invalid("BAMF_LEARNING_TRACE_WEAKNESS_DELIVERY_DRIFT")
        if ("exact_miss_delivery_ids" in controls
                or "exact_miss_replay_delivered" in controls):
            from bilqis_mlx.learning.teacher_realized_action import exact_miss_delivery_ids
            try:
                exact_ids = exact_miss_delivery_ids(controls)
            except ValueError:
                _invalid("BAMF_LEARNING_TRACE_EXACT_MISS_DELIVERY_DRIFT")
            preservation = tuple(facts.get("preservation") or ())
            if (not set(exact_ids) <= {row["id"] for row in rows}
                    or not set(exact_ids) <= {row["id"] for row in preservation}
                    or controls.get("fragile_preservation_delivered", 0) + len(exact_ids)
                    != len(preservation)):
                _invalid("BAMF_LEARNING_TRACE_EXACT_MISS_DELIVERY_DRIFT")
        self._policy_controls.append({
            key: controls[key] for key in _CONTROL_FIELDS if key in controls
        })
        self._guidance_applied_steps += int(facts.get("guidance") is not None)
        self._enrichment_examples += len(tuple(facts.get("enrichment") or ()))
        self._steps += 1

    def summary(self) -> dict:
        if self._steps < 1 or not self._batch_size:
            _invalid("BAMF_LEARNING_TRACE_EMPTY")
        return {
            "attempt_id": self.attempt_id,
            "candidate_steps": self._steps,
            "batch_size": self._batch_size,
            "policy_controls": tuple(self._policy_controls),
            "guidance_applied_steps": self._guidance_applied_steps,
            "enrichment_examples": self._enrichment_examples,
        }


__all__ = ("CandidateLearningTrace",)
