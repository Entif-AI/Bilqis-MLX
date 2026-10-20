"""Verification of cohorts minted before executable FactoryRelease v2."""
from __future__ import annotations

import json

from ..generated_assessment import make_cohort
from ..live_curriculum import cohort_contract, lesson_contract


def verify_legacy_saved_cohort(run_dir, receipt, course):
    """Cold-verify one historical Course-bound cohort."""
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
    contracts = [lesson_contract(course, grade.id) for grade in course.grades]
    matches = [
        contract for contract in contracts
        if contract[1] == stored.get("schema")]
    if len(matches) == 1:
        rubric, release, generator, code_sha = matches[0]
    elif stored.get("schema") == course.version:
        rubric, release, generator, code_sha = cohort_contract(course)
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
    cohort = make_cohort(
        stored["rows"], generator_version=generator,
        seed=stored["seed"], rubric_version=release)
    if cohort.digest != sha:
        raise ValueError("HUMAN_TRAINER_SAVED_COHORT_CONTENT_DRIFT")
    return cohort
