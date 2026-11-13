"""Small fixtures for the B09.3 C05 promotion-authority tests."""
from types import SimpleNamespace


FOUNDATION = ("A.ONE", "A.TWO")
RUNTIME_RELEASE = "1" * 64
INITIAL_RELEASE = "2" * 64
PARENT_MANIFEST = "3" * 64


def school(candidate_sha, step, *, stage, queue, scores=(), epoch=0,
           grade_index=0, debt=(), scope=FOUNDATION):
    return SimpleNamespace(
        stage=stage,
        queue=tuple(queue),
        promotion_sweep_scope=(tuple(scope)
                               if stage in {"PROMOTION_SWEEP",
                                            "ASSESS_PROMOTION_SWEEP"} else ()),
        promotion_sweep_scores=tuple(scores),
        promotion_sweep_attempt_student_sha256=candidate_sha,
        promotion_sweep_attempt_scope=FOUNDATION,
        grade_index=grade_index,
        grade_exam_epoch=epoch,
        carried_mastery_debt=tuple(debt),
        current_student=SimpleNamespace(
            sha256=candidate_sha, optimizer_step=step),
    )


def ordinary_schools(candidate_sha, step, *, entry_score=10,
                     continuation_score=9):
    entry = (("A.ONE", entry_score, 10), ("A.TWO", entry_score, 10))
    running = (("A.ONE", continuation_score, 10), ("A.TWO", entry_score, 10))
    return {
        0: school(candidate_sha, step, stage="PROMOTION_SWEEP",
                  queue=FOUNDATION, scores=entry),
        1: school(candidate_sha, step, stage="ASSESS_PROMOTION_SWEEP",
                  queue=("A.TWO",), scores=entry),
        2: school(candidate_sha, step, stage="PROMOTION_SWEEP",
                  queue=("A.TWO",), scores=running),
        3: school(candidate_sha, step, stage="ASSESS_PROMOTION_SWEEP",
                  queue=(), scores=running),
        4: school(candidate_sha, step, stage="MAIN", queue=("B.ONE",),
                  epoch=1, grade_index=1),
    }
