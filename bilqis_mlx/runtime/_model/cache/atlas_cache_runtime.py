"""Opaque pre-bound authority capability for BAMF derived-cache boundaries."""
from __future__ import annotations

import hashlib
import hmac

from bilqis_mlx.errors import BilqisError
from ..semantics.cognitive_dependencies import DependencyKind, DependencyRef
from .atlas_cache_binding import (
    CacheArtifact, _require_cache_binding, binding_digest,
)


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


class _AcceptedCacheAuthorityIssuer:
    """Non-callable issuer owned by authenticated B13 execution custody."""

    def __init__(self, issue):
        self._issue = issue
        self._accepted_caches = {}

    def issue(self, accepted_cache, eligibility_source=None):
        from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
            require_accepted_execution_cache,
        )
        from bilqis_mlx.runtime.atlas_revalidation import SourceAuthorityRegistry

        cache = require_accepted_execution_cache(accepted_cache)
        registry = cache._correction_registry
        if (type(registry) is not SourceAuthorityRegistry
                or cache.source_authority_registry_sha256 is None
                or registry.digest != cache.source_authority_registry_sha256):
            _invalid()
        authority = self._issue(
            registry, cache._cache_mac_key, eligibility_source)
        self._accepted_caches[id(authority)] = cache
        return authority

    def accepted_cache(self, authority):
        return self._accepted_caches.get(id(authority))


_authority_state, _raw_authority_issue = _new_authority_owner()
_ACCEPTED_CACHE_AUTHORITY_ISSUER = _AcceptedCacheAuthorityIssuer(
    _raw_authority_issue)
del _raw_authority_issue


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
        """Verify a source-owner statement through this host-bound registry."""
        registry, _, _, _ = _authority_state(self)
        registry.verify_detached(owner_id, dependency, signature_hex, payload)

    def _validate_export_clearance_context(
            self, receipt, selection, source_frontier, artifact_digests):
        """Validate A12 clearance without exposing the bound authority registry."""
        from bilqis_mlx.semantics.atlas_release_audit import (
            validate_export_clearance_context,
        )
        registry, _, _, _ = _authority_state(self)
        return validate_export_clearance_context(
            receipt, selection, source_frontier, artifact_digests, registry)
    def _current_eligibility_inputs(self):
        """Read current rebuild authority from the owner-bound resolver."""
        _, _, source, _ = _authority_state(self)
        if source is None:
            _invalid()
        return source()

def _require_authority(authority: CacheAuthorityRuntime) -> CacheAuthorityRuntime:
    if type(authority) is not CacheAuthorityRuntime:
        _invalid()
    _authority_state(authority)
    return authority


def bind_cache_artifact_owner(authority, artifact, binding):
    from bilqis_mlx.runtime.atlas_cache_owner import (
        _issue_exact_cache_artifact_owner, cache_artifact_digest,
    )
    authority = _require_authority(authority)
    _, _, _, owners = _authority_state(authority)
    key = (bytes(binding_digest(binding)), cache_artifact_digest(artifact))
    owner = owners.get(key)
    if owner is None:
        owner = _issue_exact_cache_artifact_owner(authority, artifact, binding)
        owners[key] = owner
    accepted_cache = _ACCEPTED_CACHE_AUTHORITY_ISSUER.accepted_cache(authority)
    if accepted_cache is not None and accepted_cache._run_dir is not None:
        from bilqis_mlx.runtime.accepted_corrections import (
            register_accepted_target,
        )
        from bilqis_mlx.runtime.atlas_owner_ingress import _route
        register_accepted_target(
            accepted_cache._run_dir,
            accepted_cache.accepted_manifest_sha256,
            "EXACT_CACHE", owner,
            lambda current, event, registry: _route(current, event, registry),
        )
    return owner


def apply_cache_correction(
    authority, artifact, binding, event, authority_registry,
):
    """Deliver one qualified C09 correction into opaque cache custody."""
    owner = bind_cache_artifact_owner(authority, artifact, binding)
    authority_registry.verify_correction(event)
    if not owner.index.direct_dependents(event.dependency):
        return owner.queue
    return owner.apply_correction(event, authority_registry)


def encode_cold_cache(authority, cache, codec_manifest, *, binding):
    from .atlas_cache_records import _encode_cold_cache
    from .atlas_cache_eligibility import validate_current_binding
    authority = _require_authority(authority)
    validate_current_binding(authority, binding)
    return _encode_cold_cache(
        cache, codec_manifest, binding=binding,
        authority=authority,
    )


def decode_cache(authority, artifact, expected_binding):
    from .atlas_cache_records import _decode_cache
    from .atlas_cache_eligibility import validate_current_binding
    authority = _require_authority(authority)
    validate_current_binding(authority, expected_binding)
    owner = bind_cache_artifact_owner(authority, artifact, expected_binding)
    owner.require(authority, artifact, expected_binding)
    return _decode_cache(
        artifact, expected_binding, authority=authority,
    )


def interactive_cache_inference(
    authority, artifact, expected_binding, *, cached_infer,
    fp32_recompute, quality_check, policy, artifact_owner=None,
):
    from .atlas_cache_policy import _interactive_cache_inference
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
                _invalid()
    return _interactive_cache_inference(
        artifact, expected_binding,
        artifact_owner=retained_owner,
        cached_infer=cached_infer,
        fp32_recompute=fp32_recompute,
        quality_check=quality_check,
        policy=policy,
        authority=_require_authority(authority),
    )


def rebuild_revoked_cache(
    authority, stale_artifact, new_binding, *, eligibility_receipt, persist,
):
    from .atlas_cache_rebuild import _rebuild_revoked_cache
    return _rebuild_revoked_cache(
        stale_artifact,
        new_binding,
        eligibility_receipt=eligibility_receipt,
        persist=persist,
        authority=_require_authority(authority),
    )


def issue_cache_eligibility(authority, binding):
    from .atlas_cache_eligibility import issue_cache_eligibility as _issue
    return _issue(_require_authority(authority), binding)
