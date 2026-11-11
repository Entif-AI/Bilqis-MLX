"""Exact non-K/V custody and guarded restoration for cold BAMF attention caches."""
from __future__ import annotations

from dataclasses import dataclass
from math import prod
import weakref

import mlx.core as mx


def _invalid() -> None:
    from .atlas_cache_codec import _invalid as codec_invalid
    codec_invalid()


@dataclass(frozen=True)
class CapturedAttentionMetadata:
    shape: tuple[int, ...]
    convolution: object
    scope_ids: mx.array
    sequence_ids: mx.array
    valid: mx.array
    layer: int
    generation: str
    parameter_digest: str
    prefix_digest: str
    start_offset: int
    rope_variant: tuple
    mlx_version: str


def capture_attention_metadata(cache) -> CapturedAttentionMetadata:
    from bilqis_mlx.runtime.atlas_attention import AttentionCache

    if type(cache) is not AttentionCache:
        _invalid()
    return CapturedAttentionMetadata(
        tuple(cache.key.shape), cache.convolution, cache.scope_ids,
        cache.sequence_ids, cache.valid, cache.layer, cache.generation,
        cache.parameter_digest, cache.prefix_digest, cache.start_offset,
        cache.rope_variant, cache.mlx_version)


def attention_cache_pairs(authority):
    """List owner-current K/V handle pairs by layer without exposing FP32 values."""
    from .atlas_cache_runtime import _production_authority_state, _require_authority

    authority = _require_authority(authority)
    entry = _production_authority_state(authority)
    grouped = {}
    for handle, record in entry[3].items():
        layer, kind = record[4]
        grouped.setdefault(layer, {})[kind] = handle
    if any(set(kinds) != {"key", "value"} for kinds in grouped.values()):
        _invalid()
    return tuple(
        (layer, grouped[layer]["key"], grouped[layer]["value"])
        for layer in sorted(grouped))


def restore_attention_cache(
    authority, key_artifact, key_handle: str,
    value_artifact, value_handle: str, parameters, spec, extents,
):
    """Restore one CCGQA continuation cache after both cold records validate."""
    from bilqis_mlx.runtime.atlas_attention import (
        AttentionCache, _attention_parameter_digest, _attention_parameters,
        attention_parameter_view,
    )
    from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
    from .atlas_cache_operations import (
        _preflight_cache_artifact, decode_cache,
    )
    from .atlas_cache_production_bridge import binding_for_handle
    from .atlas_cache_production_custody import production_record_for_handle

    key_record = production_record_for_handle(authority, key_handle)
    value_record = production_record_for_handle(authority, value_handle)
    if (key_record[4][1] != "key" or value_record[4][1] != "value"
            or key_record[4][0] != value_record[4][0]):
        _invalid()
    key_meta, value_meta = key_record[5], value_record[5]
    if key_meta is not value_meta:
        _invalid()
    _, key_binding = binding_for_handle(authority, key_handle)
    _, value_binding = binding_for_handle(authority, value_handle)
    common = (
        "generation_sha256", "lineage_sha256", "topology_sha256",
        "source_release_sha256", "semantic_release_sha256",
        "source_rights_sha256", "rights_purpose_sha256",
        "policy_epoch_sha256", "context_eligibility_sha256",
        "causal_prefix_sha256", "masks_sha256", "scope_sha256",
        "inference_state_sha256", "offset",
    )
    if any(getattr(key_binding, name) != getattr(value_binding, name)
           for name in common):
        _invalid()
    if execution_generation_digest(
            parameters, spec=spec, extents=extents) != key_meta.generation:
        _invalid()
    attention_parameters = attention_parameter_view(
        parameters, spec=spec, extents=extents, layer=key_meta.layer)
    parameters = _attention_parameters(attention_parameters)
    digest = _attention_parameter_digest(
        parameters, generation=key_meta.generation, layer=key_meta.layer)
    if digest != key_meta.parameter_digest:
        _invalid()
    _preflight_cache_artifact(authority, key_artifact, key_binding)
    _preflight_cache_artifact(authority, value_artifact, value_binding)
    key = decode_cache(authority, key_artifact, key_binding)
    value = decode_cache(authority, value_artifact, value_binding)
    if key.shape != value.shape or key.size != prod(key_meta.shape):
        _invalid()
    return AttentionCache(
        mx.array(key.reshape(key_meta.shape), dtype=mx.float32),
        mx.array(value.reshape(key_meta.shape), dtype=mx.float32),
        key_meta.convolution, key_meta.scope_ids, key_meta.sequence_ids,
        key_meta.valid, key_meta.layer, key_meta.generation,
        tuple(weakref.ref(item) for item in parameters),
        key_meta.parameter_digest, key_meta.prefix_digest,
        key_meta.start_offset, key_meta.rope_variant, key_meta.mlx_version)


def interactive_attention_cache_inference(
    authority, key_artifact, key_handle, value_artifact, value_handle,
    parameters, spec, extents, *, cached_infer, fp32_recompute,
    quality_check, policy,
):
    """Use a restored K/V pair only when the B14 quality policy accepts it."""
    from bilqis_mlx.errors import BilqisError
    from .atlas_cache_binding import CacheByteCost, cache_byte_cost
    from .atlas_cache_policy import (
        CacheInferenceResult, CacheQualityObservation, CacheQualityPolicy,
        FALLBACK_BINDING, FALLBACK_SCORE_DRIFT, FALLBACK_TYPED_ANSWER,
        _fallback,
    )

    if not isinstance(policy, CacheQualityPolicy):
        _invalid()
    policy.validate()
    try:
        restored = restore_attention_cache(
            authority, key_artifact, key_handle, value_artifact, value_handle,
            parameters, spec, extents)
    except BilqisError:
        return _fallback(fp32_recompute, FALLBACK_BINDING)
    if not callable(cached_infer) or not callable(quality_check):
        _invalid()
    candidate = cached_infer(restored)
    observation = quality_check(candidate)
    if not isinstance(observation, CacheQualityObservation):
        _invalid()
    observation.validate()
    if not observation.typed_answer_valid:
        return _fallback(fp32_recompute, FALLBACK_TYPED_ANSWER)
    if observation.score_drift > policy.max_score_drift:
        return _fallback(fp32_recompute, FALLBACK_SCORE_DRIFT)
    key_cost, value_cost = cache_byte_cost(key_artifact), cache_byte_cost(value_artifact)
    cost = CacheByteCost(
        key_cost.header_bytes + value_cost.header_bytes,
        key_cost.payload_bytes + value_cost.payload_bytes,
        key_cost.total_bytes + value_cost.total_bytes,
        (key_cost.effective_bits_per_channel
         + value_cost.effective_bits_per_channel) / 2.0,
    )
    return CacheInferenceResult(candidate, True, None, cost)
