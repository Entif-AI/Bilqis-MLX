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
from bilqis_mlx.runtime import atlas_cache_rebuild as _rebuild
from bilqis_mlx.runtime.atlas_cache_binding import binding_digest
from bilqis_mlx.runtime.atlas_cache_rebuild import CacheEligibilityReceipt

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
_test_eligibility_lookup, _test_eligibility_issue = _rebuild._new_eligibility_owner()
def install_test_owner(test_case, *, eligibility=True):
    patcher = patch.object(_runtime, "_authority_state", _test_lookup)
    patcher.start()
    test_case.addCleanup(patcher.stop)
    if eligibility:
        eligibility_owner = patch.object(
            _rebuild, "_eligibility_state", _test_eligibility_lookup)
        eligibility_owner.start()
        test_case.addCleanup(eligibility_owner.stop)


def eligibility_receipt(binding, *, eligible=True):
    return _test_eligibility_issue(CacheEligibilityReceipt(
        binding_digest(binding).hex(),
        binding.source_release_sha256,
        binding.semantic_release_sha256,
        binding.source_rights_sha256,
        binding.rights_purpose_sha256,
        binding.policy_epoch_sha256,
        binding.context_eligibility_sha256,
        eligible,
    ))


def authority_for_registry(registry):
    return _test_issue(registry, _CACHE_MAC_KEY)


CACHE_AUTHORITY = _test_issue(AUTHORITY_REGISTRY, _CACHE_MAC_KEY)
