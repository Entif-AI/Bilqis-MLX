"""Deterministic test-only cache authority; never production provenance."""
from unittest.mock import patch

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


# An isolated test owner issues fixtures; its lookup is installed only in tests.
from bilqis_mlx.runtime import atlas_cache_runtime as _runtime

_test_lookup, _test_issue = _runtime._new_authority_owner()
def install_test_owner(test_case):
    patcher = patch.object(_runtime, "_authority_state", _test_lookup)
    patcher.start()
    test_case.addCleanup(patcher.stop)


CACHE_AUTHORITY = _test_issue(AUTHORITY_REGISTRY, _CACHE_MAC_KEY)
