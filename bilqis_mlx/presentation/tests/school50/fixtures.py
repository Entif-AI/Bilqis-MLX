"""Literal source-shaped exam receipts shared by projection tests."""

def exam(grade, generation, rubric, scores, *, step, sha="signed-model"):
    return {"event": "SCHOOL_EXAM_COMMITTED", "grade": grade,
            "generation": generation, "rubric": rubric,
            "optimizer_step": step, "student_sha256": sha, "phase": "MAIN",
            "scores": {cap: {"correct": correct, "total": total}
                       for cap, (correct, total) in scores.items()}}
