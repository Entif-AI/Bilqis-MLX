"""Pure host-side lesson preparation for the three-lane human trainer.

Workers receive source/curriculum inputs only.  They never receive model
parameters, optimizers, run-state paths, checkpoint authority, or MLX handles.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from pathlib import Path
import signal

from bilqis_mlx.learning.fragile_replay import fresh_preservation_rows
from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.live_curriculum import draw_course_rows
from bilqis_mlx.factory.teaching import optional_teaching_rows
from .source_execution import SourceExecutionContext


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


def _source_execution_context(request: dict) -> SourceExecutionContext | None:
    release = request.get("executable_release")
    if release is None:
        return None
    return SourceExecutionContext(
        release=release,
        graph=request["graph"],
        source_root=Path(request["source_root"]),
        source_registry=live_source_registry(),
        answer_registry=live_answer_registry(),
    )


def _source_rows(request, *, seed: int, capability: str, each: int,
                 source_context: SourceExecutionContext | None = None):
    """Only pure, previously admitted source contracts enter worker processes."""
    root = Path(request["source_root"])
    release = request.get("executable_release")
    if release is not None:
        context = source_context or _source_execution_context(request)
        return context.draw_rows(seed=seed, capability=capability, each=each)
    return draw_course_rows(
        root, request["graph"], request["course"],
        seed=seed, capability=capability, each=each)


def _fragile_rows(request: dict, *,
                  source_context: SourceExecutionContext | None = None) -> tuple[dict, ...]:
    fixed = tuple(request["fragile_fixed_rows"])
    requested = tuple(request["fragile_requested"])
    if not fixed or not requested:
        return ()
    def seed_for(name, attempt):
        seeds = tuple(request["fragile_seeds"].get(name, ()))
        if len(seeds) != 3:
            raise ValueError("SOURCE_PREFETCH_FRAGILE_SEEDS_INVALID")
        return seeds[attempt]
    return fresh_preservation_rows(
        fixed, capabilities=requested, rotation=request["fragile_rotation"],
        batch_size=request["batch_size"], seed_for=seed_for,
        draw_rows=lambda **kwargs: _source_rows(
            request, source_context=source_context, **kwargs))


def _teaching_enrichment_rows(request: dict):
    if request.get("executable_release") is not None:
        return optional_teaching_rows(Path(request["source_root"]), request["graph"],
            request["executable_release"], live_source_registry(), capability=request["capability"],
            seed=request["teaching_seed"], enabled=request["teaching_enrichment_enabled"],
            legacy_course=request["course"])
    return live_source_registry().optional_teaching_rows(
        request["course"], capability=request["capability"],
        source_root=Path(request["source_root"]), graph=request["graph"],
        seed=request["teaching_seed"], enabled=request["teaching_enrichment_enabled"])


def _retention_support_rows(request: dict, *,
                            source_context: SourceExecutionContext | None = None):
    capability = request["retention_support_capability"]
    if capability is None:
        return ()
    from bilqis_mlx.runtime.candidate_evidence import (
        _select_fresh_retention_support_rows,
    )
    rows = _source_rows(
        request, seed=request["retention_support_seed"],
        capability=capability, each=max(request["batch_size"], 6),
        source_context=source_context)
    return _select_fresh_retention_support_rows(
        rows, rotation=request["retention_support_rotation"])


def prepare_step_sources(request: dict) -> dict:
    """Prepare one optimizer step without access to neural or writable run state."""
    if not isinstance(request, dict) or FORBIDDEN_AUTHORITY_KEYS & set(request):
        raise ValueError("SOURCE_PREFETCH_FORBIDDEN_AUTHORITY")
    required = {
        "identity", "source_root", "graph", "course", "capability",
        "batch_size", "fresh_seed", "prior_capability",
        "prior_seed", "fragile_fixed_rows", "fragile_requested", "fragile_seeds",
        "fragile_rotation", "retention_support_capability",
        "retention_support_seed", "retention_support_rotation",
        "teaching_seed", "teaching_enrichment_enabled",
    }
    if set(request) not in (required, required | {"executable_release"}):
        raise ValueError("SOURCE_PREFETCH_REQUEST_SCHEMA_DRIFT")
    identity = request["identity"]
    if (not isinstance(identity, str) or len(identity) != 64 or
            any(char not in "0123456789abcdef" for char in identity)):
        raise ValueError("SOURCE_PREFETCH_IDENTITY_INVALID")
    batch_size = request["batch_size"]
    source_root = Path(request["source_root"])
    source_context = _source_execution_context(request)
    if source_context is not None:
        source_context.require_capabilities(tuple(
            capability for capability in (
                request["capability"], request["prior_capability"],
                *request["fragile_requested"], request["retention_support_capability"])
            if capability is not None))
    fresh = _source_rows(
        request, seed=request["fresh_seed"],
        capability=request["capability"], each=max(32, batch_size),
        source_context=source_context)
    prior = []
    if request["prior_capability"] is not None:
        prior = _source_rows(
            request, seed=request["prior_seed"],
            capability=request["prior_capability"], each=max(batch_size, 6),
            source_context=source_context)
    preservation = _fragile_rows(request, source_context=source_context)
    retention_support = _retention_support_rows(request, source_context=source_context)
    enrichment = _teaching_enrichment_rows(request)
    return {
        "schema": SCHEMA,
        "identity": identity,
        "fresh": list(fresh),
        "prior": list(prior),
        "preservation": list(preservation),
        "retention_support": list(retention_support),
        "teaching_enrichment_rows": list(enrichment),
    }
