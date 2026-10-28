"""Historical CLI projections for receipts created before factory v2.

No function here controls current runtime progression. These helpers only make
old saved receipts legible while current CLI status/preflight uses v2 artifacts.
"""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus, SCHOOL

import json

from .live_releases import (
    BOOLEAN_COMPOSITE_RELEASE,
    BOOLEAN_IDENTIFICATION_RELEASE,
    BOOLEAN_RELEASE,
    FULL_BOOLEAN_RELEASES,
    INITIAL_RELEASE,
    MINIMAL_BOOLEAN_RELEASE,
    NUMERIC_RELEASE,
    NUMERIC_STAIRCASE_RELEASE,
)
from ..grade_a_release import RELEASE as GRADE_A_RELEASE


BOOLEAN_RELEASES = (
    BOOLEAN_RELEASE,
    BOOLEAN_COMPOSITE_RELEASE,
    BOOLEAN_IDENTIFICATION_RELEASE,
    MINIMAL_BOOLEAN_RELEASE,
)


def legacy_qualification_scope() -> dict:
    """Report Grade-A-era qualification evidence without replaying it."""
    return {
        "disposable_full_student_optimizer_continuation": {
            "status": "PREVIOUSLY_VERIFIED_CPU_AND_APPLE_GPU",
            "scope": "ONE_DETACHED_STEP_AND_COMPLETE_39_TENSOR_ADAMW_RESTART",
            "evidence": "docs/evidence/grades/GRADE_A_REPAIR_AND_BACKEND_20261015.md",
            "recheck": "npm run mlx:qualify",
            "freshly_rerun_by_this_command": False,
        },
        "human_live_grade_a_trainer_end_to_end_qualified": False,
        "human_experimental_trainer_implemented": True,
        "operator_release": "HUMAN_EXPLICIT_--human-run_ONLY",
    }


def historical_session_stop(event_name: object) -> bool:
    """Recognize the Grade-A stop event superseded by the school event."""
    return event_name == "GRADE_A_SESSION_STOPPED"


def legacy_status_fields(saved: dict) -> dict:
    mode = saved.get("curriculum_mode")
    return {
        "grade_a_release": INITIAL_RELEASE if mode in BOOLEAN_RELEASES else
            mode or GRADE_A_RELEASE,
        "historical_source_release": GRADE_A_RELEASE,
        "grade_a_curriculum_mode": (
            INITIAL_RELEASE if mode in BOOLEAN_RELEASES else
            mode or "HISTORICAL_FIXED_72"),
        "grade_b_curriculum_mode": mode if mode in BOOLEAN_RELEASES else None,
        "grade_b_source_admitted": mode in (
            *BOOLEAN_RELEASES, NUMERIC_RELEASE, NUMERIC_STAIRCASE_RELEASE),
        "grade_c_curriculum_mode": (
            mode if mode in (NUMERIC_RELEASE, NUMERIC_STAIRCASE_RELEASE)
            else None),
    }


def legacy_new_run_status_fields() -> dict:
    return {
        "grade_a_release": INITIAL_RELEASE,
        "historical_source_release": GRADE_A_RELEASE,
        "grade_a_curriculum_mode": INITIAL_RELEASE,
    }


def legacy_new_run_inspection(*, historical_seed: dict) -> dict:
    """Render the Grade-A-only status contract before a saved school exists."""
    return {
        "status": "GRADE_A_EXPERIMENTAL_HUMAN_LAUNCH_AVAILABLE",
        "grade": "A",
        "phase": "READY_FOR_HUMAN_GRADE_A_START",
        "historical_seed": historical_seed,
        **legacy_new_run_status_fields(),
        "grade_a_curriculum": "SIX_SOURCE_TYPED_PREDICATES_FRESH_GENERATED_COHORTS",
        "source_grounded_grade_a_admitted": True,
    }


def legacy_profile_label(saved: dict, *, full_grade_b: bool) -> dict:
    """Describe old release-shaped B state without selecting current behavior."""
    mode = saved.get("curriculum_mode")
    if mode == MINIMAL_BOOLEAN_RELEASE:
        return {
            "profile": "FULL_DEFAULT" if full_grade_b else "REDUCED_EXPLICIT",
            "migration_required": full_grade_b,
            "legacy_release": mode,
        }
    if full_grade_b and mode in FULL_BOOLEAN_RELEASES:
        return {
            "profile": "FULL_DEFAULT",
            "migration_required": False,
            "legacy_release": mode,
        }
    if mode in FULL_BOOLEAN_RELEASES and not full_grade_b:
        return {
            "profile": "REDUCED_EXPLICIT",
            "migration_required": True,
            "legacy_release": mode,
        }
    return {}


def legacy_numeric_scope(saved: dict) -> dict:
    if saved.get("curriculum_mode") != NUMERIC_STAIRCASE_RELEASE:
        return {}
    from ..numeric_staircase import INITIAL_MAXIMUM, FINAL_MAXIMUM
    return {
        "initial_maximum": INITIAL_MAXIMUM,
        "final_maximum": FINAL_MAXIMUM,
        "resume_maximum": saved.get("numeric_maximum", INITIAL_MAXIMUM),
        "neural_updates": 0,
        "legacy_release": NUMERIC_STAIRCASE_RELEASE,
    }


def legacy_numeric_staircase_preflight(
        saved: dict, *, maximum, checkpoint_sha256: str | None,
        factory: dict | None) -> dict:
    """Project the historical numeric-staircase request into CLI wire fields."""
    from ..numeric_staircase import INITIAL_MAXIMUM, FINAL_MAXIMUM

    scope = legacy_numeric_scope(saved)
    return {
        "authority": "EXECUTABLE_FACTORY_NUMERIC_PROFILE",
        "initial_maximum": INITIAL_MAXIMUM,
        "final_maximum": FINAL_MAXIMUM,
        "resume_maximum": (
            maximum if isinstance(maximum, int)
            else scope.get("resume_maximum", 3)),
        "source_student_sha256": checkpoint_sha256,
        "neural_updates": 0,
        "profile_id": factory.get("profile_id") if factory is not None else None,
    }


def legacy_boolean_revision_preflight(
        *, resume: bool, boolean_composite: bool,
        boolean_idboolops: bool, checkpoint_sha256: str | None) -> dict:
    """Describe legacy Boolean flags now represented by teaching stages."""
    if not boolean_composite and not boolean_idboolops:
        return {}
    if not resume:
        if boolean_composite:
            ErrorBus.raise_legacy(SCHOOL.RESUME.BOOLEAN_COMPOSITE_REQUIRES_RESUME)
        ErrorBus.raise_legacy(SCHOOL.RESUME.BOOLEAN_IDBOOLOPS_REQUIRES_RESUME)
    if not isinstance(checkpoint_sha256, str) or not checkpoint_sha256:
        ErrorBus.raise_legacy(SCHOOL.RESUME.BOOLEAN_REVISION_SOURCE_STUDENT_MISSING)
    return {
        "legacy_boolean_revision_flags": {
            "composite_requested": boolean_composite,
            "idboolops_requested": boolean_idboolops,
            "authority": "CANONICAL_PROFILE_TEACHING_STAGES",
            "separate_release_enrollment": False,
            "source_student_sha256": checkpoint_sha256,
            "neural_updates": 0,
        }
    }


def legacy_boolean_profile_request(*, full_grade_b: bool) -> str:
    return ("school/boolean/full" if full_grade_b
            else "school/boolean-kernel/and-iff")


def legacy_ignored_boolean_revision_flags(
        *, full_grade_b: bool, boolean_composite: bool,
        boolean_idboolops: bool) -> dict:
    if full_grade_b or not (boolean_composite or boolean_idboolops):
        return {}
    return {
        "legacy_boolean_revision_flags": {
            "ignored": True,
            "reason": "MINIMAL_GRADE_B_ALREADY_INCLUDES_SIMPLIFIED_COMPOSITE_AND_IDBOOLOPS",
        }
    }


def legacy_boolean_association_bridge_fields() -> dict:
    """Describe the historical Boolean association bridge without admission."""
    from ..boolean_association import VERSION, constructor_digest

    return {
        "enabled_for_next_human_command": True,
        "version": VERSION,
        "generator_code_sha256": constructor_digest(),
        "authority": "FACTORY_RELEASE_TEACHING_OPTION",
        "exam_rubric_changed": False,
        "grade_a_pass_fail_changed": False,
        "grade_c_pass_fail_changed": False,
        "neural_updates": 0,
    }
