"""Historical CLI projections for receipts created before factory v2.

No function here controls current runtime progression. These helpers only make
old saved receipts legible while current CLI status/preflight uses v2 artifacts.
"""
from __future__ import annotations

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


def legacy_profile_label(saved: dict, *, full_grade_b: bool) -> dict:
    """Describe old release-shaped B state without selecting current behavior."""
    mode = saved.get("curriculum_mode")
    if mode == MINIMAL_BOOLEAN_RELEASE:
        return {
            "profile": "MINIMAL_DEFAULT",
            "migration_required": False,
            "legacy_release": mode,
        }
    if full_grade_b and mode in FULL_BOOLEAN_RELEASES:
        return {
            "profile": "FULL_OPT_IN",
            "migration_required": False,
            "legacy_release": mode,
        }
    if mode in FULL_BOOLEAN_RELEASES and not full_grade_b:
        return {
            "profile": "MINIMAL_DEFAULT",
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
