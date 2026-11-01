"""Recognize one narrowly verified historical event-outbox migration defect.

Only a v1 -> v2 *neural-inert* migration may inherit old generation IDs. The
immutable predecessor owns those IDs. Their exact publication in the append-only
event journal is mandatory; this module cannot invent or rewrite past events.
"""
from __future__ import annotations

from pathlib import Path

from .admission import _verified_legacy_upgrade_release
from ..state_dag import read_generation


_V2_SCHEMA = "bilqis.mlx.factory-release/v2"
_MIGRATED_FIELDS = frozenset((
    "generation", "school", "factory_release_file", "factory_release_sha256",
    "factory_release_schema", "factory_admission_v2",
    "numeric_scope_final_maximum",
))


def verified_inherited_v1_generation(run_dir: Path, record: dict) -> int | None:
    """Return the signed predecessor generation only for exact v1->v2 carryover.

    This *does not* approve delivery. The caller must also prove each original
    event ID/payload appears exactly once in the original append-only journal.
    """
    current = record.get("generation")
    if (type(current) is not int or current < 2 or
            not isinstance(record.get("factory_admission_v2"), dict) or
            record.get("factory_release_schema") != _V2_SCHEMA):
        return None
    path = Path(run_dir) / "states" / f"{current - 1:07d}.json"
    if path.is_symlink() or not path.is_file():
        return None
    previous = read_generation(run_dir, current - 1)
    if (not isinstance(previous, dict) or
            previous.get("generation") != current - 1 or
            previous.get("factory_admission_v2") is not None or
            not isinstance(previous.get("factory_admission"), dict) or
            record.get("factory_admission") != previous["factory_admission"] or
            not isinstance(previous.get("delivery_outbox"), list) or
            record.get("delivery_outbox") != previous["delivery_outbox"]):
        return None

    # The historical migration may alter only its release authority, school
    # digest and generation, never the underlying student, learning history or
    # unsent event intent.
    for key in set(record) | set(previous):
        if key not in _MIGRATED_FIELDS and record.get(key) != previous.get(key):
            return None
    old_school = previous.get("school")
    new_school = record.get("school")
    if not isinstance(old_school, dict) or not isinstance(new_school, dict):
        return None
    if (old_school.get("course_digest") == new_school.get("course_digest") or
            {k: v for k, v in old_school.items() if k != "course_digest"} !=
            {k: v for k, v in new_school.items() if k != "course_digest"}):
        return None
    latest = new_school.get("current_student")
    admission = record["factory_admission_v2"]
    if (not isinstance(latest, dict) or
            record.get("factory_release_file") !=
            "factory-releases/" + str(record.get("factory_release_sha256")) + ".json" or
            admission.get("factory_release_sha256") != record.get("factory_release_sha256") or
            admission.get("student_sha256") != latest.get("sha256") or
            admission.get("optimizer_step") != latest.get("optimizer_step") or
            admission.get("semantic_graph_sha256") !=
            record.get("semantic_graph_sha256")):
        return None
    # Recheck the predecessor against its signed v1 factory authority. If
    # someone changed the old release or admission, hard-fail, never heal it.
    historical = _verified_legacy_upgrade_release(Path(run_dir), previous)
    if historical is None or historical.course.digest() != old_school["course_digest"]:
        return None
    return current - 1
