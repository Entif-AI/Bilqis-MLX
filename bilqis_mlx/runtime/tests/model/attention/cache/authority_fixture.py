"""Deterministic test-only cache authority; never production provenance."""
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey,
    SourceAuthorityRegistry,
    SourceAuthorityScope,
)
from bilqis_mlx.runtime.atlas_cache_codec import CacheAuthorityRuntime

_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
PUBLIC_KEY_HEX = _KEY.public_key().public_bytes(
    serialization.Encoding.Raw,
    serialization.PublicFormat.Raw,
).hex()
OWNER_ID = "bamf-cache-test-authority"


def authority_registry(
    public_key_hex: str = PUBLIC_KEY_HEX,
) -> SourceAuthorityRegistry:
    return SourceAuthorityRegistry((SourceAuthorityKey(
        OWNER_ID,
        public_key_hex,
        (SourceAuthorityScope(DependencyKind.ARTIFACT, "cache:"),),
    ),))


AUTHORITY_REGISTRY = authority_registry()
_CACHE_MAC_KEY = bytes(range(32, 64))


def _test_cache_authority(
    registry: SourceAuthorityRegistry, mac_key: bytes,
) -> CacheAuthorityRuntime:
    """Explicit same-process fixture construction; not an authority boundary."""
    authority = object.__new__(CacheAuthorityRuntime)
    object.__setattr__(
        authority, "_CacheAuthorityRuntime__registry", registry)
    object.__setattr__(
        authority, "_CacheAuthorityRuntime__mac_key", mac_key)
    return authority


CACHE_AUTHORITY = _test_cache_authority(AUTHORITY_REGISTRY, _CACHE_MAC_KEY)
