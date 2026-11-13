"""Optimizer-step loop for one teaching visit."""
from __future__ import annotations

from . import selection, step_sources


def run(d, s):
    step_sources.initialize(d, s)
    for step in range(s.candidate_steps):
        d._runtime_timing_trace.trace_mark(
            "OPTIMIZER_STEP_START", capability=s.cap, visit_step=step + 1,
            optimizer_step=int(s.optimizer.state["step"].item()))
        prepared, fresh, option_rows, preservation, support = step_sources.for_step(d, s, step)
        training_rows, training_guidance = selection.select(
            d, s, step, prepared, fresh, option_rows, preservation, support)
        with d._runtime_timing_trace.trace_span(
                "STEP_TRAIN", capability=s.cap, visit_step=step + 1,
                batch_size=len(training_rows)):
            s.last_loss, s.last_norm = d._learning_student_ops._train_step(
                s.mx, s.params, s.optimizer, training_rows, s.receipt["config"],
                s.receipt["answer_ids"], champion_guidance=training_guidance)
        rung = step + 1
        if s.shadow_rungs and rung in s.shadow_rungs and rung < s.candidate_steps:
            with d._runtime_timing_trace.trace_span(
                    "TEACHER_SHADOW_RUNG", capability=s.cap, visit_step=rung):
                rung_score = d._learning_student_ops._train_score(
                    s.mx, s.params, s.rows, s.receipt["config"], s.receipt["answer_ids"])
            s.shadow_probes.append((
                rung, d._learning_teacher_multifidelity.target_correct_delta(
                    s.before, rung_score, len(s.rows))))
        d._runtime_timing_trace.trace_mark(
            "OPTIMIZER_STEP_END", capability=s.cap, visit_step=step + 1,
            optimizer_step=int(s.optimizer.state["step"].item()))
