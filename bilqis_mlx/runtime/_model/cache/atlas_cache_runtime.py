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
        return entry[1], entry[2]

    def issue(registry, mac_key):
        authority = object.__new__(CacheAuthorityRuntime)
        issued[id(authority)] = (authority, registry, mac_key)
        return authority

    return require, issue


# No production issuer is exposed until the upstream run owner supplies one.
_authority_state, _discarded_issuer = _new_authority_owner()
del _discarded_issuer


class CacheAuthorityRuntime:
    """Opaque capability supplied by the accepted upstream run authority."""

    __slots__ = ("__registry", "__mac_key")

    def __new__(cls, *args, **kwargs):
        _invalid()

    def __setattr__(self, name, value):
        _invalid()

    def _require_binding_authority(self, binding) -> None:
        registry, _ = _authority_state(self)
        registry.require_claimed_authority(
            binding.artifact_authority_id,
            DependencyRef(DependencyKind.ARTIFACT, f"cache:{binding.key_sha256}"),
            binding.artifact_authority_public_key_hex,
        )

    def _authenticate(self, binding, subject: bytes) -> bytes:
        if type(subject) is not bytes:
            _invalid()
        self._require_binding_authority(binding)
        _, mac_key = _authority_state(self)
        return hmac.new(
            mac_key, subject, hashlib.sha256,
        ).digest()[:CACHE_AUTHENTICATOR_BYTES]

    def _verify(self, binding, subject: bytes, authenticator: bytes) -> None:
        expected = self._authenticate(binding, subject)
        if (type(authenticator) is not bytes
                or not hmac.compare_digest(authenticator, expected)):
            _invalid()

def _require_authority(authority: CacheAuthorityRuntime) -> CacheAuthorityRuntime:
    if type(authority) is not CacheAuthorityRuntime:
        _invalid()
    _authority_state(authority)
    return authority


def encode_cold_cache(authority, cache, codec_manifest, *, binding):
    from .atlas_cache_records import _encode_cold_cache
    return _encode_cold_cache(
        cache, codec_manifest, binding=binding,
        authority=_require_authority(authority),
    )


def decode_cache(authority, artifact, expected_binding):
    from .atlas_cache_records import _decode_cache
    return _decode_cache(
        artifact, expected_binding, authority=_require_authority(authority),
    )


def interactive_cache_inference(
    authority, artifact, expected_binding, *, cached_infer,
    fp32_recompute, quality_check, policy,
):
    from .atlas_cache_policy import _interactive_cache_inference
    return _interactive_cache_inference(
        artifact, expected_binding,
        cached_infer=cached_infer,
        fp32_recompute=fp32_recompute,
        quality_check=quality_check,
        policy=policy,
        authority=_require_authority(authority),
    )


def rebuild_revoked_cache(
    authority, stale_artifact, new_binding, *, eligibility_receipt,
    canonical_fp32_source, persist,
):
    from .atlas_cache_rebuild import _rebuild_revoked_cache
    return _rebuild_revoked_cache(
        stale_artifact,
        new_binding,
        eligibility_receipt=eligibility_receipt,
        canonical_fp32_source=canonical_fp32_source,
        persist=persist,
        authority=_require_authority(authority),
    )
