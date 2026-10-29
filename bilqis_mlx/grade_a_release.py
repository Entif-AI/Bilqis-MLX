"""Human-accepted source-bound Grade A, without claiming full NI certification."""
from __future__ import annotations

from dataclasses import replace

from .curriculum import Course
from .grade_a_probe import candidate_course
from .semantics.foundation.abi import HISTORICAL_PREFIX_SIZE

RELEASE = "bilqis.mlx.grade-a-user-accepted/20261015"
AUTHORITY = "user-explicit-grade-a-acceptance/20261015"


def accepted_grade_a(manifest: dict) -> Course:
    """Release the existing six predicates, not any different or expanded exam."""
    candidate = candidate_course()
    if (manifest.get("state") != "CANDIDATE_SEALED_NOT_TRAINING_ADMITTED"
            or manifest.get("course_proposal_digest") != candidate.digest()
            or manifest.get("exam_count") != 72
            or manifest.get("train_count") != 144):
        raise ValueError("GRADE_A_ACCEPTANCE_SOURCE_INVENTORY_MISMATCH")
    seal = manifest["exam_rubric_sha256"]
    graph = manifest["parent_student"]
    if (graph.get("student_vocab_size") != HISTORICAL_PREFIX_SIZE or
            not graph.get("prefix_identity_preserved")
            or len(seal) != 64
            or not manifest.get("manifest_sha256")):
        raise ValueError("GRADE_A_ACCEPTANCE_STUDENT_OR_RUBRIC_MISMATCH")
    grade = replace(candidate.grades[0], assessment_sha256=seal)
    released = replace(candidate, grades=(grade,), version=RELEASE,
                       source_attestation_sha256=manifest["manifest_sha256"],
                       assessment_manifest_sha256=seal,
                       program_complete=False)
    if not released.executable:
        raise ValueError("GRADE_A_ACCEPTED_COURSE_NOT_EXECUTABLE")
    return released
