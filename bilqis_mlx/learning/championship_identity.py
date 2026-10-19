"""Holistic comparison identity for active championship and soup authority."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json


SCHEMA = "bilqis.mlx.championship-school-identity/v1"


def _sha(value) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        symbol in "0123456789abcdef" for symbol in value)


def build_school_identity(*, course_sha256: str, semantic_graph_sha256: str,
                          parameter_shapes: dict,
                          factory_release_sha256: str) -> dict:
    """Bind all comparison geometry that makes championship evidence comparable."""
    if not all(_sha(value) for value in (
            course_sha256, semantic_graph_sha256, factory_release_sha256)):
        raise ValueError("CHAMPIONSHIP_SCHOOL_IDENTITY_SHA_INVALID")
    if (not isinstance(parameter_shapes, dict) or not parameter_shapes or
            any(not isinstance(name, str) or not name or
                not isinstance(shape, (list, tuple)) or not shape or
                any(type(size) is not int or size < 1 for size in shape)
                for name, shape in parameter_shapes.items())):
        raise ValueError("CHAMPIONSHIP_SCHOOL_IDENTITY_PARAMETER_SHAPES_INVALID")
    core = {
        "schema": SCHEMA,
        "course_sha256": course_sha256,
        "semantic_graph_sha256": semantic_graph_sha256,
        "parameter_shapes": {name: list(parameter_shapes[name])
                             for name in sorted(parameter_shapes)},
        "factory_release_sha256": factory_release_sha256,
    }
    digest = hashlib.sha256(json.dumps(
        core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**core, "sha256": digest}


def enforce_school_identity(epoch: dict, identity: dict, *, generation: int,
                            student: dict) -> tuple[dict, bool]:
    """Archive and clear all live championship authority on identity drift."""
    if (not isinstance(epoch, dict) or identity.get("schema") != SCHEMA or
            not _sha(identity.get("sha256")) or type(generation) is not int or
            generation < 1 or not isinstance(student, dict) or
            not _sha(student.get("sha256")) or
            type(student.get("optimizer_step")) is not int or
            student["optimizer_step"] < 0):
        raise ValueError("CHAMPIONSHIP_SCHOOL_IDENTITY_RESET_INVALID")
    updated = deepcopy(epoch)
    if updated.get("championship_school_identity") == identity:
        return updated, False
    archive = {
        "source_generation": generation,
        "prior_school_identity": deepcopy(updated.get("championship_school_identity")),
        "active_roles": deepcopy(updated.get("active_roles", {})),
        "active_grade_soups": deepcopy(updated.get("active_grade_soups", {})),
        "starting_student": dict(student),
    }
    updated["school_identity_history"] = [
        *updated.get("school_identity_history", ()), archive]
    updated["superseded_active_championships"] = [
        *updated.get("superseded_active_championships", ()), deepcopy(archive)]
    updated["active_roles"] = {}
    updated["active_grade_soups"] = {}
    updated["championship_school_identity"] = deepcopy(identity)
    updated["championship_eligibility_after_step"] = student["optimizer_step"]
    updated["administrative_empty_reset"] = {
        "reason": "HOLISTIC_SCHOOL_IDENTITY_CHANGED",
        "source_generation": generation,
        "student_sha256": student["sha256"],
        "optimizer_step": student["optimizer_step"],
        "old_active_role_count": len(archive["active_roles"]),
        "old_active_soup_grades": sorted(archive["active_grade_soups"]),
        "settled_matchups_preserved": len(updated.get("settled_matchups", {})),
        "training_or_optimizer_updates": 0,
    }
    return updated, True
