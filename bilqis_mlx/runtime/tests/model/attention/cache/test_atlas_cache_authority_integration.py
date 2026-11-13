"""B14.4 cache rebuild authority comes from live B13/A12/context owners."""
from dataclasses import replace
import unittest

import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_cache_binding import binding_digest
from bilqis_mlx.runtime.atlas_cache_codec import (
    HEAD_WIDTH, CacheBinding, CacheEligibilityReceipt, codec_manifest,
    rebuild_revoked_cache,
)
from bilqis_mlx.runtime.atlas_cache_records import _encode_cold_cache
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.tests.model.attention.cache.authority_fixture import (
    OWNER_ID, PUBLIC_KEY_HEX, authority_for_registry, install_test_owner,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind

class CacheAuthorityIntegrationTests(unittest.TestCase):
    def setUp(self):
        install_test_owner(self, eligibility=False, current_binding=False)

    def test_caller_matching_receipt_is_not_authority(self):
        binding = CacheBinding(
            codec_manifest(), *(value * 64 for value in "123456789abcde"),
            17, OWNER_ID, PUBLIC_KEY_HEX)
        forged = CacheEligibilityReceipt(
            binding_digest(binding).hex(), binding.source_release_sha256,
            binding.semantic_release_sha256, binding.source_rights_sha256,
            binding.rights_purpose_sha256, binding.policy_epoch_sha256,
            binding.context_eligibility_sha256, True)
        authority = authority_for_registry(SourceAuthorityRegistry((SourceAuthorityKey(
            OWNER_ID, PUBLIC_KEY_HEX,
            (SourceAuthorityScope(DependencyKind.ARTIFACT, "cache:"),)),)))
        stale = _encode_cold_cache(
            np.zeros((256, HEAD_WIDTH), dtype=np.float32), binding.codec_manifest,
            binding=binding, authority=authority)
        with self.assertRaises(BilqisError):
            rebuild_revoked_cache(
                authority,
                stale, replace(binding, policy_epoch_sha256="f" * 64),
                eligibility_receipt=forged,
                persist=lambda _: self.fail("caller receipt persisted"))

if __name__ == "__main__":
    unittest.main()
