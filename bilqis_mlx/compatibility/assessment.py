"""Verification of cohorts minted before executable FactoryRelease v2."""
from __future__ import annotations

import json

from ..generated_assessment import verify_stored_cohort
from ..live_curriculum import cohort_contract, lesson_contract


def sealed_v1_cohort_contract(release, grade):
    """Derive historical cohort provenance from its original signed adapter.

    V1 cohort identities cannot be reconstructed by compiling the old course
    against today's registry: source adapters and constructor fingerprints have
    evolved. The verified persisted release already owns these exact values.
    """
    candidates = tuple(item for item in release.capabilities
                       if item.grade_id == grade.id)
    adapters = {item.source_adapter_id for item in candidates}
    if len(adapters) != 1:
        raise ValueError("FACTORY_SEALED_COHORT_ADAPTER_AMBIGUOUS")
    adapter = release.source_adapter_map[next(iter(adapters))]
    known = {name for name, _ in adapter.cohort_releases}
    schema = (release.course.version if
              grade.id == release.course.grades[-1].id and
              release.course.version in known else
              adapter.cohort_releases[0][0]
              if adapter.cohort_releases else release.course.version)
    code_sha = adapter.cohort_code_sha256(schema)
    from .historical_live_release import (
        HISTORICAL_A_GENERATOR_SHA256, HISTORICAL_A_RUBRIC_SHA256,
    )
    if grade.assessment_sha256 == HISTORICAL_A_RUBRIC_SHA256:
        code_sha = HISTORICAL_A_GENERATOR_SHA256
    return (grade.assessment_sha256, schema, adapter.cohort_generator, code_sha)


def verify_legacy_saved_cohort(run_dir, receipt, course, *, sealed_v1_release=None):
    """Cold-verify one historical Course-bound cohort."""
    if sealed_v1_release is not None:
        # A post-migration v2 profile is not the authority that minted this
        # historical exam. Its original signed v1 course and adapter are.
        course = sealed_v1_release.course
    exam = receipt.get("last_exam") or {}
    sha = exam.get("cohort_sha256")
    if sha is None:
        return None
    if (not isinstance(sha, str) or len(sha) != 64 or
            exam.get("cohort_file") != "cohorts/" + sha + ".json"):
        raise ValueError("HUMAN_TRAINER_SAVED_COHORT_REFERENCE_DRIFT")
    path = run_dir / exam["cohort_file"]
    if path.is_symlink() or not path.is_file():
        raise ValueError("HUMAN_TRAINER_SAVED_COHORT_MISSING")
    stored = json.loads(path.read_text())
    contracts = [
        (sealed_v1_cohort_contract(sealed_v1_release, grade)
         if sealed_v1_release is not None else lesson_contract(course, grade.id))
        for grade in course.grades]
    matches = [
        contract for contract in contracts
        if contract[1] == stored.get("schema")]
    if len(matches) == 1:
        rubric, release, generator, code_sha = matches[0]
    elif stored.get("schema") == course.version:
        rubric, release, generator, code_sha = (
            sealed_v1_cohort_contract(sealed_v1_release, course.grades[-1])
            if sealed_v1_release is not None else cohort_contract(course))
    else:
        raise ValueError("HUMAN_TRAINER_SAVED_COHORT_RELEASE_NOT_ADMITTED")
    if (stored.get("rubric_sha256") != rubric or
            stored.get("source_manifest_sha256") !=
            receipt["source_manifest_sha256"] or
            stored.get("generator_version") != generator or
            stored.get("generator_code_sha256") != code_sha or
            stored.get("cohort_sha256") != sha or
            stored.get("seed") != exam.get("cohort_seed") or
            stored.get("schema") != release):
        raise ValueError("HUMAN_TRAINER_SAVED_COHORT_METADATA_DRIFT")
    try:
        return verify_stored_cohort(
            stored, sha, expected_rubric_sha256=rubric)
    except ValueError as exc:
        if str(exc) == "STORED_COHORT_CONTENT_DRIFT":
            raise ValueError("HUMAN_TRAINER_SAVED_COHORT_CONTENT_DRIFT") from exc
        raise ValueError("HUMAN_TRAINER_SAVED_COHORT_METADATA_DRIFT") from exc
