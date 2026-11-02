"""Host-owned authority capability for BAMF derived-cache boundaries."""
from __future__ import annotations

import hashlib
import hmac

from .atlas_revalidation import SourceAuthorityRegistry
from ..semantics.cognitive_dependencies import DependencyKind, DependencyRef


CACHE_MAC_KEY_BYTES = 32
CACHE_AUTHENTICATOR_BYTES = 16
_HOST_CACHE_AUTHORITY_ISSUER = object()


def _invalid() -> None:
    from .atlas_cache_codec import _invalid as codec_invalid
    codec_invalid()


class CacheAuthorityRuntime:
    """Opaque host-issued capability fixing cache trust-root provenance."""

    __slots__ = ("__registry", "__mac_key")

    def __new__(cls, *args, **kwargs):
        _invalid()

    @classmethod
    def _issue(
        cls, registry: SourceAuthorityRegistry, mac_key: bytes, *, _issuer=None,
    ) -> CacheAuthorityRuntime:
        if (_issuer is not _HOST_CACHE_AUTHORITY_ISSUER
                or not isinstance(registry, SourceAuthorityRegistry)
                or type(mac_key) is not bytes
                or len(mac_key) != CACHE_MAC_KEY_BYTES):
            _invalid()
        instance = object.__new__(cls)
        object.__setattr__(instance, "_CacheAuthorityRuntime__registry", registry)
        object.__setattr__(instance, "_CacheAuthorityRuntime__mac_key", mac_key)
        return instance

    def __setattr__(self, name, value):
        _invalid()

    def _require_binding_authority(self, binding) -> None:
        self.__registry.require_claimed_authority(
            binding.artifact_authority_id,
            DependencyRef(DependencyKind.ARTIFACT, f"cache:{binding.key_sha256}"),
            binding.artifact_authority_public_key_hex,
        )

    def _authenticate(self, binding, subject: bytes) -> bytes:
        if type(subject) is not bytes:
            _invalid()
        self._require_binding_authority(binding)
        return hmac.new(
            self.__mac_key, subject, hashlib.sha256,
        ).digest()[:CACHE_AUTHENTICATOR_BYTES]

    def _verify(self, binding, subject: bytes, authenticator: bytes) -> None:
        expected = self._authenticate(binding, subject)
        if (type(authenticator) is not bytes
                or not hmac.compare_digest(authenticator, expected)):
            _invalid()


def _host_cache_authority(
    registry: SourceAuthorityRegistry, mac_key: bytes,
) -> CacheAuthorityRuntime:
    """Internal host-bootstrap seam; never expose registry selection to cache calls."""
    return CacheAuthorityRuntime._issue(
        registry, mac_key, _issuer=_HOST_CACHE_AUTHORITY_ISSUER)


def _require_authority(authority: CacheAuthorityRuntime) -> CacheAuthorityRuntime:
    if type(authority) is not CacheAuthorityRuntime:
        _invalid()
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
