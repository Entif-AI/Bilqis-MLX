"""Source-backed B11 cache capture and owner-derived B14 bindings."""
from __future__ import annotations

import hashlib

import numpy as np

ATTENTION_CACHE_RANK, B14_HEAD_WIDTH = 4, 24
KIND_COUNT, CAPTURE_HANDLE_HEX_LENGTH = 2, 64
def _invalid() -> None:
    from .atlas_cache_codec import _invalid as codec_invalid
    codec_invalid()


def _array_fp32(value) -> np.ndarray:
    values = np.asarray(value)
    if (values.ndim != ATTENTION_CACHE_RANK
            or values.shape[-1] != B14_HEAD_WIDTH
            or values.dtype != np.float32 or not np.isfinite(values).all()):
        _invalid()
    return np.asarray(
        values.reshape(-1, values.shape[-1]), dtype=np.float32, order="C")


def _digest_array(label: str, value) -> str:
    values = np.asarray(value)
    digest = hashlib.sha256()
    digest.update(label.encode("ascii"))
    digest.update(b"\0")
    digest.update(str(values.dtype).encode("ascii"))
    digest.update(b"\0")
    digest.update(repr(tuple(values.shape)).encode("ascii"))
    digest.update(b"\0")
    digest.update(np.asarray(values, order="C").tobytes(order="C"))
    return digest.hexdigest()


def _causal_identities(attention_cache):
    from bilqis_mlx.runtime.atlas_attention import AttentionCache
    from .atlas_cache_eligibility import _CausalCacheIdentity

    if type(attention_cache) is not AttentionCache:
        _invalid()
    key_values = _array_fp32(attention_cache.key)
    value_values = _array_fp32(attention_cache.value)
    masks_sha256 = hashlib.sha256(
        (_digest_array("valid", attention_cache.valid)
         + _digest_array("sequence", attention_cache.sequence_ids)
         + str(attention_cache.start_offset)).encode("ascii")
    ).hexdigest()
    scope_sha256 = hashlib.sha256(
        (str(attention_cache.layer)
         + _digest_array("scope", attention_cache.scope_ids)).encode("ascii")
    ).hexdigest()
    key_material = key_values.tobytes(order="C")

    def identity(kind: str):
        key_sha256 = hashlib.sha256(
            str(attention_cache.layer).encode("ascii") + b"\0"
            + kind.encode("ascii") + b"\0" + key_material
        ).hexdigest()
        return _CausalCacheIdentity(
            attention_cache.prefix_digest, masks_sha256, scope_sha256,
            key_sha256, attention_cache.start_offset)

    return {
        "key": (key_values, identity("key")),
        "value": (value_values, identity("value")),
    }


def _production_identity(
    accepted_cache, compiled_batch, producer, attention_cache, causal,
):
    from bilqis_mlx.learning.atlas_engram_reads.source_owner import _B13_EXECUTION_SEAL
    from bilqis_mlx.learning.source_atoms.backbone import _SourceBackboneProducerSession
    from bilqis_mlx.runtime.atlas_model_contracts import BamfCompiledBatch
    from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
        require_accepted_execution_cache,
    )
    from bilqis_mlx.semantics.context_eligibility import ApprovedContextProjection
    from bilqis_mlx.semantics.domains import contract_digest
    from .atlas_cache_eligibility import _AuthoritativeCacheIdentity

    cache = require_accepted_execution_cache(accepted_cache)
    if (type(compiled_batch) is not BamfCompiledBatch
            or type(producer) is not _SourceBackboneProducerSession):
        _invalid()
    compiled_batch.__post_init__()
    compiled = compiled_batch.compiled
    if (producer._compiled is not compiled
            or producer._sources is not compiled_batch.sources
            or producer._feature_schema is not compiled_batch.feature_schema
            or producer._artifact_owner is not compiled_batch.atlas_feature_artifact_owner
            or producer._motif_manifest is not cache.motif_manifest
            or producer._motif_seal is not _B13_EXECUTION_SEAL
            or producer._input_motif_read is None):
        _invalid()
    producer._validated_receipts(producer._topology.depth_groups)
    row = compiled.compiled.rows[0]
    frame_nodes = compiled.packed_frame_artifact_owner.require_row(row)
    from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
    rights = tuple(sorted(
        ref.key.removeprefix("rights:")
        for node in frame_nodes
        for ref in node.immediate_dependencies
        if ref.kind is DependencyKind.RIGHTS and ref.key.startswith("rights:")
    ))
    if len(set(rights)) != 1:
        _invalid()
    source_rights_sha256 = rights[0]
    config = compiled.compiler_configs[0]
    projection = compiled._projections[0]
    selection = compiled_batch.sources[0].selection
    if (type(projection) is not ApprovedContextProjection
            or producer._generation != cache.generation_binding
            or attention_cache.generation != producer._generation
            or cache.run_id != compiled_batch.active_semantic_rows.run_id
            or cache.generation != compiled_batch.active_semantic_rows.generation
            or config.task.semantic_release != selection.release_sha256):
        _invalid()
    lineage = contract_digest({
        "schema": "bilqis.mlx.bamf-cache-lineage/v1", "run_id": cache.run_id})
    purpose = contract_digest({
        "purpose": config.task.purpose, "jurisdiction": config.task.jurisdiction,
        "scope": config.task.scope})
    policy = contract_digest({
        "policy_id": config.policy.policy_id,
        "policy_epoch": config.policy.policy_epoch,
        "rights_epoch": config.policy.rights_epoch})
    return _AuthoritativeCacheIdentity(
        cache.accepted_manifest_sha256, lineage, producer._topology.digest,
        selection.source_bundle_id, selection.release_sha256,
        source_rights_sha256, purpose, policy, projection.digest,
        causal.causal_prefix_sha256, causal.masks_sha256,
        causal.scope_sha256, causal.key_sha256, producer._generation,
        causal.offset)


def capture_forward_attention_caches(accepted_cache, compiled_batch, producer):
    """Capture only B11-sealed CCGQA caches after accepted source-backed forward."""
    from bilqis_mlx.learning.source_atoms.backbone import _b14_attention_caches
    from .atlas_cache_production_custody import _capture_handle
    from .atlas_cache_runtime import (
        _capture_production_records, _provision_cache_authority_runtime,
    )

    authority = _provision_cache_authority_runtime(accepted_cache)
    captures = {}
    for attention_cache in _b14_attention_caches(producer):
        from .atlas_cache_attention_restore import capture_attention_metadata
        metadata = capture_attention_metadata(attention_cache)
        for kind, (values, causal) in _causal_identities(attention_cache).items():
            identity = _production_identity(
                accepted_cache, compiled_batch, producer, attention_cache, causal)
            handle = _capture_handle(identity)
            captures[handle] = (
                values.copy(), identity,
                compiled_batch.compiled.packed_frame_artifact_owner,
                compiled_batch.compiled.compiled.rows[0],
                (attention_cache.layer, kind),
                metadata,
            )
    if len(captures) != producer._topology.layers * KIND_COUNT:
        _invalid()
    _capture_production_records(authority, captures)
    return authority


def production_capture_for_handle(authority, handle):
    from .atlas_cache_production_custody import production_record_for_handle
    record = production_record_for_handle(authority, handle)
    return record[0], record[1]


def production_capture_for_binding(authority, binding):
    from .atlas_cache_runtime import _production_authority_state
    entry = _production_authority_state(authority)
    if entry is None:
        return None
    matches = tuple(
        (handle, capture) for handle, capture in entry[3].items()
        if capture[1].key_sha256 == binding.key_sha256
        and all(getattr(binding, name) == getattr(capture[1], name)
                for name in capture[1].__dataclass_fields__))
    if len(matches) != 1:
        _invalid()
    return production_capture_for_handle(authority, matches[0][0])


def attention_cache_handles(authority):
    from .atlas_cache_runtime import _production_authority_state, _require_authority
    authority = _require_authority(authority)
    entry = _production_authority_state(authority)
    return tuple(sorted(entry[3])) if entry is not None else ()


def binding_for_handle(authority, handle: str):
    from .atlas_cache_codec import codec_manifest
    from .atlas_cache_eligibility import binding_from_identity
    from .atlas_cache_runtime import _production_authority_state, _require_authority

    if (not isinstance(handle, str)
            or len(handle) != CAPTURE_HANDLE_HEX_LENGTH):
        _invalid()
    authority = _require_authority(authority)
    entry = _production_authority_state(authority)
    if entry is None:
        _invalid()
    captured_records = entry[3]
    if handle not in captured_records:
        _invalid()
    values, identity = production_capture_for_handle(authority, handle)
    key = entry[2]
    binding = binding_from_identity(
        codec_manifest(), identity, key.owner_id, key.public_key_hex)
    return values, binding


def attention_cache_binding(authority, handle: str):
    """Return the owner-derived binding for a fresh captured K/V record."""
    return binding_for_handle(authority, handle)[1]


def encode_attention_cache(authority, handle: str):
    """Encode owner-captured K/V state, then release its retained FP32 copy."""
    from .atlas_cache_operations import encode_cold_cache
    from .atlas_cache_runtime import _production_authority_state

    values, binding = binding_for_handle(authority, handle)
    if values is None:
        _invalid()
    artifact = encode_cold_cache(
        authority, values, binding.codec_manifest, binding=binding)
    entry = _production_authority_state(authority)
    capture = entry[3][handle]
    entry[3][handle] = (None, *capture[1:])
    return artifact, binding
