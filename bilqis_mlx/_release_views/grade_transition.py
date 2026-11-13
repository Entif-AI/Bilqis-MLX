"""Pure identity helpers shared by historical admission evidence."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
import hashlib
import json

from .curriculum.scheduler import Assessment
from .curriculum_compiler import TypedCandidatePackage


def candidate_package_digest(package: TypedCandidatePackage) -> str:
    """Digest the complete immutable source-only output approved by a receipt."""
    if not isinstance(package, TypedCandidatePackage):
        raise ValueError("GRADE_ADMISSION_INVALID_CANDIDATE_PACKAGE")

    def default(value):
        if isinstance(value, Enum):
            return value.value
        if is_dataclass(value):
            return asdict(value)
        raise TypeError(type(value).__name__)

    payload = json.dumps(asdict(package), sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, default=default)
    return hashlib.sha256(payload.encode()).hexdigest()


def cumulative_exam_digest(assessment: Assessment) -> str:
    """Bind independent exam attestation to scores and one complete checkpoint."""
    return hashlib.sha256(json.dumps(asdict(assessment), sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()
