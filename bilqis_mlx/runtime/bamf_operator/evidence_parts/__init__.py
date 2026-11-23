"""Public facade for persistent BAMF candidate evidence."""
import os

from bilqis_mlx.learning.teacher_lineage import restore_teacher_lineage

from .capture import CandidateEvidenceCapture
from .support import (
    EVIDENCE_SCHEMA, PERSISTENCE_SCHEMA, REFERENCE_SCHEMA, _PREPARED_ROOTS,
    candidate_attempt_id, prepare_candidate_evidence_root,
)


__all__ = (
    "CandidateEvidenceCapture",
    "EVIDENCE_SCHEMA",
    "PERSISTENCE_SCHEMA",
    "REFERENCE_SCHEMA",
    "candidate_attempt_id",
    "prepare_candidate_evidence_root",
)
