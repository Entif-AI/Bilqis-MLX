"""Pure host-side lesson preparation for the three-lane human trainer.

Workers receive source/curriculum inputs only.  They never receive model
parameters, optimizers, run-state paths, checkpoint authority, or MLX handles.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from pathlib import Path
import signal

from bilqis_mlx.learning.fragile_replay import (
    select_preservation_rows,
    select_structural_preservation_rows,
)
from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.live_curriculum import draw_course_rows


SCHEMA = "bilqis.mlx.source-prefetch/v1"
FORBIDDEN_AUTHORITY_KEYS = frozenset({
    "parameters", "params", "optimizer", "run_dir", "checkpoint",
    "student", "receipt", "teacher", "school_state",
})


def source_prefetch_worker_initializer() -> None:
    """Keep Ctrl+C ownership in the human trainer parent process."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def source_prefetch_pool(workers: int) -> ProcessPoolExecutor:
    return ProcessPoolExecutor(
        max_workers=workers,
        mp_context=multiprocessing.get_context("spawn"),
        initializer=source_prefetch_worker_initializer,
    )


def _source_rows(request, *, seed: int, capability: str, each: int):
    """Only pure, previously admitted source contracts enter worker processes."""
    root = Path(request["source_root"])
    release = request.get("executable_release")
    if release is not None:
        from bilqis_mlx.factory.generation import draw_executable_release_rows
        return draw_executable_release_rows(
            root, request["graph"], release, live_source_registry(),
            seed=seed, capability=capability, each=each,
            legacy_course=request["course"])
    return draw_course_rows(
        root, request["graph"], request["course"],
        seed=seed, capability=capability, each=each)


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
            fresh.extend(_source_rows(
                request, seed=seed, capability=name,
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


def _teaching_enrichment_rows(request: dict):
    return live_source_registry().optional_teaching_rows(
        request["course"], capability=request["capability"],
        source_root=Path(request["source_root"]), graph=request["graph"],
        seed=request["teaching_seed"], enabled=request["teaching_enrichment_enabled"])


def prepare_step_sources(request: dict) -> dict:
    """Prepare one optimizer step without access to neural or writable run state."""
    if not isinstance(request, dict) or FORBIDDEN_AUTHORITY_KEYS & set(request):
        raise ValueError("SOURCE_PREFETCH_FORBIDDEN_AUTHORITY")
    required = {
        "identity", "source_root", "graph", "course", "capability",
        "batch_size", "fresh_seed", "prior_capability",
        "prior_seed", "fragile_fixed_rows", "fragile_requested", "fragile_seeds",
        "fragile_rotation", "teaching_seed", "teaching_enrichment_enabled",
    }
    if set(request) not in (required, required | {"executable_release"}):
        raise ValueError("SOURCE_PREFETCH_REQUEST_SCHEMA_DRIFT")
    identity = request["identity"]
    if (not isinstance(identity, str) or len(identity) != 64 or
            any(char not in "0123456789abcdef" for char in identity)):
        raise ValueError("SOURCE_PREFETCH_IDENTITY_INVALID")
    batch_size = request["batch_size"]
    source_root = Path(request["source_root"])
    fresh = _source_rows(
        request, seed=request["fresh_seed"],
        capability=request["capability"], each=max(32, batch_size))
    prior = []
    if request["prior_capability"] is not None:
        prior = _source_rows(
            request, seed=request["prior_seed"],
            capability=request["prior_capability"], each=max(batch_size, 6))
    preservation = _fragile_rows(request)
    enrichment = _teaching_enrichment_rows(request)
    return {
        "schema": SCHEMA,
        "identity": identity,
        "fresh": list(fresh),
        "prior": list(prior),
        "preservation": list(preservation),
        "teaching_enrichment_rows": list(enrichment),
    }
