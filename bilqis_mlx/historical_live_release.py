"""Read-only compatibility for the A/B release sealed before ABI refactoring.

The 2026-10-16 ABI refactor replaced a literal graph SHA with a reference
to the identical code-owned value. That source-only change altered Grade A's
byte-derived generator fingerprint, which cascaded into the sealed A/B rubric
and course digest. Existing human runs retain their original release contract.
"""
from __future__ import annotations

from dataclasses import replace

from .live_grade_a import (ASSESSMENT_ITEMS_PER_CAPABILITY, GENERATOR,
                           RELEASE, _sha, generator_source_digest, live_course)


HISTORICAL_A_GENERATOR_SHA256 = (
    "9e107ab8282fe07a7720b7df6d82dedd3b50adb0f44f7142fb491407ce4848ad"
)
ABI_REFACTORED_A_GENERATOR_SHA256 = (
    "4b1a491d09fccfced98d368d52794b003de26e628c867ae3fd4a7c979060f59d"
)
HISTORICAL_A_RUBRIC_SHA256 = (
    "c65522b6de61bc40d386ec60a66b3c01d274a60f7c9feaf84a9679150935e32d"
)
HISTORICAL_B_RUBRIC_SHA256 = (
    "4aee94a3c06cfb4567595b315b0ac88aee4d5ed9cb32a3a86f89ac6ee610a94f"
)
HISTORICAL_B_COURSE_SHA256 = (
    "8b50a9c964c82785fe65cbfd65344b706f492cc9e8348f95a3c24d803845e8c6"
)


def historical_grade_a_course(accepted):
    """Rebuild the archived seal; never rewrite archived states or specimens."""
    if generator_source_digest() != ABI_REFACTORED_A_GENERATOR_SHA256:
        raise ValueError("HISTORICAL_GRADE_A_SOURCE_COMPATIBILITY_NOT_PROVEN")
    current = live_course(accepted)
    rubric = _sha({
        "generator": GENERATOR,
        "generator_code_sha256": HISTORICAL_A_GENERATOR_SHA256,
        "source": accepted.source_attestation_sha256,
        "families": [cap.id for cap in accepted.grades[0].capabilities],
        "assessments_per_capability": ASSESSMENT_ITEMS_PER_CAPABILITY,
    })
    if rubric != HISTORICAL_A_RUBRIC_SHA256 or current.version != RELEASE:
        raise ValueError("HISTORICAL_GRADE_A_RUBRIC_NOT_REPRODUCIBLE")
    grade = replace(current.grades[0], assessment_sha256=rubric)
    return replace(current, grades=(grade,), assessment_manifest_sha256=rubric)


def historical_grade_b_course(accepted, source_root):
    from .live_grade_b import live_course as build_grade_b

    old_a = historical_grade_a_course(accepted)
    old_b = build_grade_b(old_a, source_root)
    if (old_b.digest() != HISTORICAL_B_COURSE_SHA256 or
            old_b.grades[-1].assessment_sha256 != HISTORICAL_B_RUBRIC_SHA256):
        raise ValueError("HISTORICAL_GRADE_B_RUBRIC_NOT_REPRODUCIBLE")
    return old_a, old_b
