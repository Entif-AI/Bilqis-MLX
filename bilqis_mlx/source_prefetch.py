"""Pure host-side lesson preparation for the three-lane human trainer.

Workers receive source/curriculum inputs only.  They never receive model
parameters, optimizers, run-state paths, checkpoint authority, or MLX handles.
"""
from __future__ import annotations

from pathlib import Path

from .fragile_replay import (
    select_preservation_rows,
    select_structural_preservation_rows,
)
from .live_curriculum import draw_course_rows, numeric_maximum


SCHEMA = "bilqis.mlx.source-prefetch/v1"
FORBIDDEN_AUTHORITY_KEYS = frozenset({
    "parameters", "params", "optimizer", "run_dir", "checkpoint",
    "student", "receipt", "teacher", "school_state",
})


def _fragile_rows(request: dict) -> tuple[dict, ...]:
    fixed = tuple(request["fragile_fixed_rows"])
    requested = tuple(request["fragile_requested"])
    if not fixed or not requested:
        return ()
    excluded = {row["id"] for row in fixed}
    selected = []
    source_root = Path(request["source_root"])
    graph = request["graph"]
    course = request["course"]
    batch_size = request["batch_size"]
    seed_map = request["fragile_seeds"]
    rotation = request["fragile_rotation"]
    for name in requested:
        fixed_capability = tuple(row for row in fixed if row["capability"] == name)
        fresh = []
        matched = ()
        seeds = tuple(seed_map.get(name, ()))
        if len(seeds) != 3:
            raise ValueError("SOURCE_PREFETCH_FRAGILE_SEEDS_INVALID")
        for seed in seeds:
            fresh.extend(draw_course_rows(
                source_root, graph, course, seed=seed, capability=name,
                each=max(96, batch_size * 3)))
            matched = select_structural_preservation_rows(
                fresh, fixed_capability, excluded_ids=excluded,
                rotation=rotation, limit=4)
            if len(matched) >= 4:
                break
        delivered = list(matched)
        if len(delivered) < 4:
            try:
                fallback = select_preservation_rows(
                    fresh, capabilities=(name,), excluded_ids=excluded)
            except ValueError as exc:
                if str(exc) != "FRAGILE_PRESERVATION_INCOMPLETE_TRUTH_TABLE":
                    raise
                fallback = ()
            used = {row["id"] for row in delivered}
            for row in fallback:
                if row["id"] not in used:
                    delivered.append(row)
                    used.add(row["id"])
                if len(delivered) >= 4:
                    break
        selected.extend(delivered[:4])
    if any(row["id"] in excluded for row in selected):
        raise ValueError("FRAGILE_PRESERVATION_EXAM_ROW_LEAK")
    return tuple(selected)


def _association_rows(request: dict):
    if not request["boolean_association_bridge"] or request["lesson_grade"] != "B":
        return ()
    if {grade.id for grade in request["course"].grades} != {"A", "B", "C"}:
        raise ValueError("BOOLEAN_ASSOCIATION_BRIDGE_REQUIRES_ADMITTED_A_B_C")
    from .boolean_association import draw_b_grade_bridges
    return tuple(draw_b_grade_bridges(
        Path(request["source_root"]), request["graph"],
        seed=request["association_seed"], maximum=numeric_maximum(request["course"]),
        per_source=4, capability=request["capability"]))


def prepare_step_sources(request: dict) -> dict:
    """Prepare one optimizer step without access to neural or writable run state."""
    if not isinstance(request, dict) or FORBIDDEN_AUTHORITY_KEYS & set(request):
        raise ValueError("SOURCE_PREFETCH_FORBIDDEN_AUTHORITY")
    required = {
        "identity", "source_root", "graph", "course", "capability", "lesson_grade",
        "batch_size", "fresh_seed", "prior_capability",
        "prior_seed", "fragile_fixed_rows", "fragile_requested", "fragile_seeds",
        "fragile_rotation", "association_seed", "boolean_association_bridge",
    }
    if set(request) != required:
        raise ValueError("SOURCE_PREFETCH_REQUEST_SCHEMA_DRIFT")
    identity = request["identity"]
    if (not isinstance(identity, str) or len(identity) != 64 or
            any(char not in "0123456789abcdef" for char in identity)):
        raise ValueError("SOURCE_PREFETCH_IDENTITY_INVALID")
    batch_size = request["batch_size"]
    source_root = Path(request["source_root"])
    fresh = draw_course_rows(
        source_root, request["graph"], request["course"],
        seed=request["fresh_seed"], capability=request["capability"],
        each=max(32, batch_size))
    prior = []
    if request["prior_capability"] is not None:
        prior = draw_course_rows(
            source_root, request["graph"], request["course"],
            seed=request["prior_seed"], capability=request["prior_capability"],
            each=max(batch_size, 6))
    preservation = _fragile_rows(request)
    association = _association_rows(request)
    return {
        "schema": SCHEMA,
        "identity": identity,
        "fresh": list(fresh),
        "prior": list(prior),
        "preservation": list(preservation),
        "association_rows": list(association),
    }
