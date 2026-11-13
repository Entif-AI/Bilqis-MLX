"""Public guarded operations for BAMF derived-cache artifacts."""
from __future__ import annotations

from bilqis_mlx.errors import BilqisError
from .atlas_cache_binding import CacheArtifact, _require_cache_binding, binding_digest


def bind_cache_artifact_owner(authority, artifact, binding):
    from bilqis_mlx.runtime.atlas_cache_owner import (
        _issue_exact_cache_artifact_owner, cache_artifact_digest,
    )
    from .atlas_cache_runtime import (
        _accepted_cache_for_authority, _authority_state, _require_authority,
    )
    authority = _require_authority(authority)
    _, _, _, owners = _authority_state(authority)
    key = (bytes(binding_digest(binding)), cache_artifact_digest(artifact))
    owner = owners.get(key)
    if owner is None:
        owner = _issue_exact_cache_artifact_owner(authority, artifact, binding)
        owners[key] = owner
    accepted_cache = _accepted_cache_for_authority(authority)
    if accepted_cache is not None and accepted_cache._run_dir is not None:
        from bilqis_mlx.runtime.accepted_corrections import register_accepted_target
        register_accepted_target(
            accepted_cache._run_dir, accepted_cache.accepted_manifest_sha256,
            "EXACT_CACHE", owner)
    return owner


def apply_cache_correction(authority, artifact, binding, event):
    from .atlas_cache_runtime import _authority_state, _require_authority
    authority = _require_authority(authority)
    owner = bind_cache_artifact_owner(authority, artifact, binding)
    authority_registry, _, _, _ = _authority_state(authority)
    authority_registry.verify_correction(event)
    if not owner.index.direct_dependents(event.dependency):
        return owner.queue
    return owner.apply_correction(event, authority_registry)


def encode_cold_cache(authority, cache, codec_manifest, *, binding):
    from .atlas_cache_eligibility import validate_current_binding
    from .atlas_cache_records import _encode_cold_cache
    from .atlas_cache_runtime import _require_authority
    authority = _require_authority(authority)
    validate_current_binding(authority, binding)
    return _encode_cold_cache(
        cache, codec_manifest, binding=binding, authority=authority)


def decode_cache(authority, artifact, expected_binding):
    owner = _preflight_cache_artifact(authority, artifact, expected_binding)
    from .atlas_cache_records import _decode_cache
    return _decode_cache(artifact, expected_binding, authority=authority)


def _preflight_cache_artifact(authority, artifact, expected_binding):
    """Validate current ownership/authentication without performing lossy decode."""
    from .atlas_cache_eligibility import validate_current_binding
    from .atlas_cache_runtime import _require_authority
    authority = _require_authority(authority)
    validate_current_binding(authority, expected_binding)
    owner = bind_cache_artifact_owner(authority, artifact, expected_binding)
    owner.require(authority, artifact, expected_binding)
    return owner


def interactive_cache_inference(
    authority, artifact, expected_binding, *, cached_infer,
    fp32_recompute, quality_check, policy, artifact_owner=None,
):
    from .atlas_cache_policy import _interactive_cache_inference
    from .atlas_cache_runtime import _require_authority
    retained_owner = None
    if isinstance(artifact, CacheArtifact):
        try:
            from .atlas_cache_eligibility import validate_current_binding
            validate_current_binding(authority, expected_binding)
            _require_cache_binding(artifact, expected_binding, authority)
        except BilqisError:
            pass
        else:
            retained_owner = bind_cache_artifact_owner(
                authority, artifact, expected_binding)
            if artifact_owner is not None and artifact_owner is not retained_owner:
                from .atlas_cache_runtime import _invalid
                _invalid()
    return _interactive_cache_inference(
        artifact, expected_binding, artifact_owner=retained_owner,
        cached_infer=cached_infer, fp32_recompute=fp32_recompute,
        quality_check=quality_check, policy=policy,
        authority=_require_authority(authority))


def rebuild_revoked_cache(
    authority, stale_artifact, new_binding, *, eligibility_receipt, persist,
):
    from .atlas_cache_rebuild import _rebuild_revoked_cache
    from .atlas_cache_runtime import _require_authority
    return _rebuild_revoked_cache(
        stale_artifact, new_binding, eligibility_receipt=eligibility_receipt,
        persist=persist, authority=_require_authority(authority))


def rebuild_attention_cache(authority, stale_artifact, handle: str, *, persist):
    """Rebuild stale bytes only from the fresh owner-captured FP32 record."""
    from .atlas_cache_eligibility import issue_cache_eligibility
    from .atlas_cache_production_bridge import binding_for_handle

    _values, binding = binding_for_handle(authority, handle)
    receipt = issue_cache_eligibility(authority, binding)
    return rebuild_revoked_cache(
        authority, stale_artifact, binding,
        eligibility_receipt=receipt, persist=persist)


def issue_cache_eligibility(authority, binding):
    from .atlas_cache_eligibility import issue_cache_eligibility as _issue
    from .atlas_cache_runtime import _require_authority
    return _issue(_require_authority(authority), binding)
