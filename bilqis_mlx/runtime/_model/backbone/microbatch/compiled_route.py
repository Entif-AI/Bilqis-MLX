"""Stable MLX compilation policy for the ordinary route-training kernel."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import os

import mlx.core as mx

from .route_kernel import route_microbatch_loss_and_trajectory


_CACHE_LIMIT = 8
_COMPILE_ENV = "BILQIS_MLX_COMPILE_STABLE_KERNEL"
_DEFAULT_ENABLED = True
_CACHE = OrderedDict()
_HITS = 0
_MISSES = 0


@dataclass(frozen=True)
class StableRouteCompileKey:
    """Everything allowed to determine reuse of one compiled numerical route."""

    semantic_release: str
    topology_digest: str
    extents_digest: str
    shape_signature: tuple
    route_digest: str


def compile_stable_kernel_enabled() -> bool:
    """Return the qualified production toggle, with an explicit operator override."""
    value = os.environ.get(_COMPILE_ENV)
    if value is None:
        return _DEFAULT_ENABLED
    if value not in ("0", "1"):
        raise ValueError(f"{_COMPILE_ENV} must be 0 or 1")
    return value == "1"


def _decision_signature(decision):
    return (
        decision.decision_id,
        decision.kind.value,
        tuple(decision.legal_values),
        tuple(decision.depends_on),
        decision.occurrence,
    )


def _route_digest(answer_plans, targets, masks) -> str:
    payload = []
    for plan, row_targets, mask in zip(answer_plans, targets, masks):
        payload.append({
            "execution_order": tuple(plan.execution_order),
            "decisions": tuple(_decision_signature(item) for item in plan.decisions),
            "targets": tuple(
                (item.decision_id, item.value) for item in row_targets),
            "mask": tuple(sorted(mask.items())),
        })
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def stable_route_compile_key(backend, row_batches, answer_plans, targets, masks, kernel):
    """Bind release, topology, extents, concrete shape and route semantics exactly."""
    first = row_batches[0]
    shape_signature = (
        len(row_batches),
        tuple(len(item.compiled.compiled.rows[0].positions) for item in row_batches),
        tuple(len(plan.execution_order) for plan in answer_plans),
        tuple(tuple(len(item.legal_values) for item in plan.decisions)
              for plan in answer_plans),
        tuple(kernel.lengths.shape),
        tuple(tuple(value.shape) for value in kernel.candidate_vectors),
        bool(kernel.has_salience),
    )
    return StableRouteCompileKey(
        semantic_release=first.compiled.features.semantic_release,
        topology_digest=backend.topology.digest,
        extents_digest=first.compiled.extents.digest,
        shape_signature=shape_signature,
        route_digest=_route_digest(answer_plans, targets, masks),
    )


def _compile_route(kernel):
    """Compile only pure tensor math; authority and evidence remain outside."""
    def numerical_route(parameters, hidden):
        return route_microbatch_loss_and_trajectory(
            parameters,
            hidden,
            kernel,
            salience_hidden=hidden,
            refinement_routing_loss=None,
            return_logits=True,
        )

    return mx.compile(numerical_route)


def learning_first_compiled_route(
        backend, row_batches, answer_plans, targets, masks, kernel):
    """Return a stable compiled route and whether this request populated the cache."""
    global _HITS, _MISSES
    if not compile_stable_kernel_enabled():
        return None, "disabled"
    key = stable_route_compile_key(
        backend, row_batches, answer_plans, targets, masks, kernel)
    compiled = _CACHE.get(key)
    if compiled is not None:
        _HITS += 1
        _CACHE.move_to_end(key)
        return compiled, "hit"
    compiled = _compile_route(kernel)
    _MISSES += 1
    _CACHE[key] = compiled
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_LIMIT:
        _CACHE.popitem(last=False)
    return compiled, "miss"


def compiled_route_cache_size() -> int:
    return len(_CACHE)


def compiled_route_cache_stats() -> dict:
    """Return process-local qualification facts without exposing compiled objects."""
    return {"entries": len(_CACHE), "hits": _HITS, "misses": _MISSES}


def _reset_compiled_route_cache_for_tests() -> None:
    global _HITS, _MISSES
    _CACHE.clear()
    _HITS = 0
    _MISSES = 0


__all__ = (
    "StableRouteCompileKey", "compile_stable_kernel_enabled",
    "compiled_route_cache_size", "compiled_route_cache_stats",
    "learning_first_compiled_route",
    "stable_route_compile_key",
)
