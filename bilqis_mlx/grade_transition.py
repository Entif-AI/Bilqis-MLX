"""Atomic, operator-owned transition to an expanded numerical school release."""
from __future__ import annotations

from dataclasses import replace

from .live_grade_c import RELEASE, answer_heads, constructor_digest, expanded_graph
from .live_curriculum import numeric_maximum
from .school import append_next_grade
from .vocabulary_growth import extend_mlx_student


def activate_numeric_grade(mx, run_dir, receipt, previous, successor,
                           parameters, optimizer, graph, *, reserve_gib):
    # Import the existing custody writer at use time; it owns all state/outbox I/O.
    from .grade_a_trainer import (_advance, _bundle_pointer, _fingerprint, _persist,
        _reconcile_delivery_outbox, _state_from_json, _with_delivery_outbox)
    school = _state_from_json(receipt["school"], previous)
    exam = receipt.get("last_exam") or {}
    counts = {cap: count for grade in previous.grades for cap, count in grade.exam_item_counts}
    if (successor.version != RELEASE or school.grade != "B" or
            school.revalidation_target_grade is not None or
            exam.get("student_sha256") != school.current_student.sha256 or
            exam.get("optimizer_step") != school.current_student.optimizer_step or
            exam.get("scores") != {cap: {"correct": count, "total": count} for cap,count in counts.items()}):
        raise ValueError("GRADE_C_REQUIRES_ONE_COMPLETE_CUMULATIVE_A_B_PASS")
    # After the real student qualification check, before any model growth.
    # Selection evidence never substitutes for independent source admission.
    from .next_grade_review import require_admission_review
    require_admission_review("C", previous.version)
    next_state = append_next_grade(previous, successor, school)
    grown_graph = expanded_graph(graph)
    grown, own_optimizer, growth = extend_mlx_student(parameters, optimizer, graph, grown_graph)
    import uuid
    pointer = _bundle_pointer(run_dir, "numeric-admission-"+uuid.uuid4().hex[:12],
        grown, own_optimizer, grown_graph, reserve_gib=reserve_gib)
    next_state = replace(next_state, current_student=pointer)
    maximum = numeric_maximum(successor)
    updated = {**receipt, "curriculum_mode": RELEASE,
        "numeric_maximum": maximum, "grade_c_code_sha256": constructor_digest(),
        "semantic_graph_sha256": _fingerprint(grown_graph),
        "parameter_shapes": {name: list(value.shape) for name,value in grown.items()},
        "config": {**receipt["config"], "answer_heads": answer_heads(grown_graph, maximum)},
        "live_rubric_sha256": successor.grades[-1].assessment_sha256}
    record = _advance(run_dir, updated, next_state, model_bundle=pointer.filename,
                       result="ACTIVE_GRADE_C", persist=False)
    event = {"event": "SCHOOL_COURSE_ADMITTED", "grade": "C",
        "generation": record["generation"], "student_sha256": pointer.sha256,
        "optimizer_step": pointer.optimizer_step, "growth": growth,
        "previous_student_sha256": school.current_student.sha256,
        "teacher_events": receipt["teacher"]["events"],
        "rubric": successor.grades[-1].assessment_sha256,
        "actual_neural_updates": 0}
    record = _persist(run_dir, _with_delivery_outbox(record, (event,)))
    _reconcile_delivery_outbox(run_dir, record)
    return grown, own_optimizer, grown_graph, record
