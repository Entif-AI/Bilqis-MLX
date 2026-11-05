"""Compatibility-only provider metadata and immutable receipt validation."""
from __future__ import annotations

from .providers import (
    BOOLEAN_RELEASE, BOOLEAN_COMPOSITE_RELEASE, BOOLEAN_IDENTIFICATION_RELEASE,
    INITIAL_RELEASE, MINIMAL_BOOLEAN_RELEASE, NUMERIC_RELEASE,
    NUMERIC_STAIRCASE_RELEASE, release_code_digest, release_generator,
)

def legacy_receipt_fields(version: str) -> dict[str, str]:
    """Return compatibility-only receipt metadata for historical readers.

    These fields MUST NOT be used by generic runtime to choose pedagogy or
    admission behavior. They exist solely so older state readers can verify
    the exact provider bytes they historically recorded.
    """
    if version == BOOLEAN_RELEASE:
        return {
            "grade_b_code_sha256": release_code_digest(version),
            "grade_b_generator": release_generator(version),
        }
    if version == BOOLEAN_COMPOSITE_RELEASE:
        return {
            "boolean_composite_code_sha256": release_code_digest(version),
            "grade_b_generator": release_generator(version),
        }
    if version == BOOLEAN_IDENTIFICATION_RELEASE:
        return {
            "boolean_identification_code_sha256": release_code_digest(version),
            "grade_b_generator": release_generator(version),
        }
    if version == MINIMAL_BOOLEAN_RELEASE:
        return {
            "grade_b_minimal_code_sha256": release_code_digest(version),
            "grade_b_generator": release_generator(version),
        }
    if version == NUMERIC_RELEASE:
        return {"grade_c_code_sha256": release_code_digest(version)}
    if version == NUMERIC_STAIRCASE_RELEASE:
        return {"staircase_code_sha256": release_code_digest(version)}
    if version == INITIAL_RELEASE:
        return {}
    raise ValueError("FACTORY_UNKNOWN_RELEASE:" + str(version))


def verify_release_receipt(receipt: dict, course) -> None:
    """Verify historical provider fingerprints without grade-letter dispatch."""
    version = course.version
    if version == INITIAL_RELEASE:
        return
    field_by_release = {
        BOOLEAN_RELEASE: "grade_b_code_sha256",
        BOOLEAN_COMPOSITE_RELEASE: "boolean_composite_code_sha256",
        BOOLEAN_IDENTIFICATION_RELEASE: "boolean_identification_code_sha256",
        MINIMAL_BOOLEAN_RELEASE: "grade_b_minimal_code_sha256",
        NUMERIC_RELEASE: "grade_c_code_sha256",
        NUMERIC_STAIRCASE_RELEASE: "staircase_code_sha256",
    }
    field = field_by_release.get(version)
    if field is None:
        raise ValueError("FACTORY_UNKNOWN_RELEASE:" + str(version))
    if receipt.get(field) != release_code_digest(version):
        raise ValueError("FACTORY_RELEASE_PROVIDER_DIGEST_DRIFT:" + version)
