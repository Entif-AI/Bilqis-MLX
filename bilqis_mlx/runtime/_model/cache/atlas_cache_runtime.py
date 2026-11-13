"""Opaque pre-bound authority capability for BAMF derived-cache boundaries."""
from __future__ import annotations

import hashlib
import hmac

from ..semantics.cognitive_dependencies import DependencyKind, DependencyRef

CACHE_AUTHENTICATOR_BYTES = 16


def _invalid() -> None:
    from .atlas_cache_codec import _invalid as codec_invalid
    codec_invalid()


def _new_authority_owner():
    """Create an isolated owner; only its lookup accepts its issued identities."""
    issued = {}

    def require(authority):
        entry = issued.get(id(authority))
        if entry is None or entry[0] is not authority:
            _invalid()
        return entry[1], entry[2], entry[3], entry[4]

    def issue(registry, mac_key, eligibility_source=None):
        if eligibility_source is not None and not callable(eligibility_source):
            _invalid()
        authority = object.__new__(CacheAuthorityRuntime)
        issued[id(authority)] = (
            authority, registry, mac_key, eligibility_source, {})
        return authority

    return require, issue


_authority_state, _raw_authority_issue = _new_authority_owner()


class CacheAuthorityRuntime:
    """Opaque capability supplied by the accepted upstream run authority."""

    __slots__ = ("__registry", "__mac_key")

    def __new__(cls, *args, **kwargs):
        _invalid()

    def __setattr__(self, name, value):
        _invalid()

    def _require_binding_authority(self, binding) -> None:
        registry, _, _, _ = _authority_state(self)
        registry.require_claimed_authority(
            binding.artifact_authority_id,
            DependencyRef(DependencyKind.ARTIFACT, f"cache:{binding.key_sha256}"),
            binding.artifact_authority_public_key_hex,
        )

    def _authenticate(self, binding, subject: bytes) -> bytes:
        if type(subject) is not bytes:
            _invalid()
        self._require_binding_authority(binding)
        _, mac_key, _, _ = _authority_state(self)
        return hmac.new(
            mac_key, subject, hashlib.sha256,
        ).digest()[:CACHE_AUTHENTICATOR_BYTES]

    def _verify(self, binding, subject: bytes, authenticator: bytes) -> None:
        expected = self._authenticate(binding, subject)
        if (type(authenticator) is not bytes
                or not hmac.compare_digest(authenticator, expected)):
            _invalid()

    def _verify_detached(self, owner_id, dependency, signature_hex, payload) -> None:
        registry, _, _, _ = _authority_state(self)
        registry.verify_detached(owner_id, dependency, signature_hex, payload)

    def _validate_export_clearance_context(
            self, receipt, selection, source_frontier, artifact_digests):
        from bilqis_mlx.semantics.atlas_release_audit import (
            validate_export_clearance_context,
        )
        registry, _, _, _ = _authority_state(self)
        return validate_export_clearance_context(
            receipt, selection, source_frontier, artifact_digests, registry)

    def _current_eligibility_inputs(self):
        _, _, source, _ = _authority_state(self)
        if source is None:
            _invalid()
        return source()

    def _current_causal_identity(self, binding):
        return None

    def _current_production_identity(self, binding):
        from .atlas_cache_production_bridge import production_capture_for_binding
        capture = production_capture_for_binding(self, binding)
        return None if capture is None else capture[1]

    def _current_canonical_fp32(self, binding):
        from .atlas_cache_production_bridge import production_capture_for_binding
        capture = production_capture_for_binding(self, binding)
        return None if capture is None or capture[0] is None else capture[0].copy()


from .atlas_cache_production_custody import new_production_authority_owner
(_provision_cache_authority_runtime,
 _production_authority_state,
 _capture_production_records) = new_production_authority_owner(_raw_authority_issue)
del _raw_authority_issue


def _accepted_cache_for_authority(authority):
    entry = _production_authority_state(authority)
    return None if entry is None else entry[1]


def _require_authority(authority: CacheAuthorityRuntime) -> CacheAuthorityRuntime:
    if type(authority) is not CacheAuthorityRuntime:
        _invalid()
    _authority_state(authority)
    accepted_cache = _accepted_cache_for_authority(authority)
    if accepted_cache is None:
        _invalid()
    from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
        require_accepted_execution_cache,
    )
    require_accepted_execution_cache(accepted_cache)
    return authority


def bind_accepted_cache_authority(accepted_cache):
    """Resolve the one B14 capability owned by an already-accepted B13 cache."""
    authority = _provision_cache_authority_runtime(accepted_cache)
    return _require_authority(authority)


def _capture_forward_attention_caches(accepted_cache, compiled_batch, producer):
    from .atlas_cache_production_bridge import capture_forward_attention_caches
    return capture_forward_attention_caches(accepted_cache, compiled_batch, producer)


def attention_cache_handles(authority):
    from .atlas_cache_production_bridge import attention_cache_handles as operation
    return operation(authority)


def attention_cache_binding(authority, handle):
    from .atlas_cache_production_bridge import attention_cache_binding as operation
    return operation(authority, handle)


def attention_cache_pairs(authority):
    from .atlas_cache_attention_restore import attention_cache_pairs as operation
    return operation(authority)


def restore_attention_cache(
    authority, key_artifact, key_handle, value_artifact, value_handle,
    parameters, spec, extents,
):
    from .atlas_cache_attention_restore import restore_attention_cache as operation
    return operation(
        authority, key_artifact, key_handle, value_artifact, value_handle,
        parameters, spec, extents)


def interactive_attention_cache_inference(
    authority, key_artifact, key_handle, value_artifact, value_handle,
    parameters, spec, extents, *, cached_infer, fp32_recompute,
    quality_check, policy,
):
    from .atlas_cache_attention_restore import (
        interactive_attention_cache_inference as operation,
    )
    return operation(
        authority, key_artifact, key_handle, value_artifact, value_handle,
        parameters, spec, extents, cached_infer=cached_infer,
        fp32_recompute=fp32_recompute, quality_check=quality_check, policy=policy)


def encode_attention_cache(authority, handle):
    from .atlas_cache_production_bridge import encode_attention_cache as operation
    return operation(authority, handle)


def bind_cache_artifact_owner(authority, artifact, binding):
    from .atlas_cache_operations import bind_cache_artifact_owner as operation
    return operation(authority, artifact, binding)


def apply_cache_correction(authority, artifact, binding, event):
    from .atlas_cache_operations import apply_cache_correction as operation
    return operation(authority, artifact, binding, event)


def encode_cold_cache(authority, cache, codec_manifest, *, binding):
    from .atlas_cache_operations import encode_cold_cache as operation
    return operation(authority, cache, codec_manifest, binding=binding)


def decode_cache(authority, artifact, expected_binding):
    from .atlas_cache_operations import decode_cache as operation
    return operation(authority, artifact, expected_binding)


def interactive_cache_inference(
    authority, artifact, expected_binding, *, cached_infer,
    fp32_recompute, quality_check, policy, artifact_owner=None,
):
    from .atlas_cache_operations import interactive_cache_inference as operation
    return operation(
        authority, artifact, expected_binding, cached_infer=cached_infer,
        fp32_recompute=fp32_recompute, quality_check=quality_check,
        policy=policy, artifact_owner=artifact_owner)


def rebuild_revoked_cache(
    authority, stale_artifact, new_binding, *, eligibility_receipt, persist,
):
    from .atlas_cache_operations import rebuild_revoked_cache as operation
    return operation(
        authority, stale_artifact, new_binding,
        eligibility_receipt=eligibility_receipt, persist=persist)


def rebuild_attention_cache(authority, stale_artifact, handle, *, persist):
    from .atlas_cache_operations import rebuild_attention_cache as operation
    return operation(authority, stale_artifact, handle, persist=persist)


def issue_cache_eligibility(authority, binding):
    from .atlas_cache_operations import issue_cache_eligibility as operation
    return operation(authority, binding)
