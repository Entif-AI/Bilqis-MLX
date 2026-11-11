"""Safety-edge witnesses for B14.4 canonical-FP32 rebuilds."""
from dataclasses import replace
import hashlib
import hmac
import unittest

import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_cache_binding import (
    _payload_authenticator_subject_fields,
)
from bilqis_mlx.runtime.atlas_cache_codec import HEAD_WIDTH, binding_digest
from bilqis_mlx.runtime.tests.model.attention.cache.authority_fixture import (
    AUTHORITY_REGISTRY, CACHE_AUTHORITY,
)
from bilqis_mlx.runtime.tests.model.attention.cache.test_atlas_cache_rebuild import (
    RevokedCacheRebuildTests, _RAW_REBUILD, _receipt,
    decode_cache, rebuild_revoked_cache,
)


class RevokedCacheRebuildSafetyTests(unittest.TestCase):
    def setUp(self):
        RevokedCacheRebuildTests.setUp(self)

    def test_rebuild_requires_finite_exact_fp32_canonical_source(self):
        new_binding = replace(self.old_binding, policy_epoch_sha256="f" * 64)
        for values in (
            self.canonical.astype(np.float16),
            np.full((256, HEAD_WIDTH), np.nan, dtype=np.float32),
        ):
            with self.subTest(dtype=values.dtype), self.assertRaises(BilqisError):
                rebuild_revoked_cache(
                    self.stale, new_binding,
                    eligibility_receipt=_receipt(new_binding),
                    canonical_fp32_source=lambda values=values: values,
                    persist=lambda _: self.fail("persisted invalid rebuild"),
                )

    def test_stale_payload_cannot_be_relabelled_under_new_rights_binding(self):
        new_binding = replace(
            self.old_binding, source_rights_sha256="f" * 64)
        new_digest = binding_digest(new_binding)
        relabelled = replace(
            self.stale, binding_sha256=new_digest, header_bytes=None)
        self.assertEqual(relabelled.direction_codes, self.stale.direction_codes)
        self.assertEqual(relabelled.relative_norms, self.stale.relative_norms)
        self.assertEqual(
            relabelled.block_max_norms_fp32, self.stale.block_max_norms_fp32)
        with self.assertRaises(BilqisError):
            decode_cache(relabelled, new_binding)

        subject = _payload_authenticator_subject_fields(
            self.stale.mode, self.stale.true_vectors,
            self.stale.padded_vectors, self.stale.head_width, new_digest,
            self.stale.direction_codes, self.stale.relative_norms,
            self.stale.block_max_norms_fp32, self.stale.fp32_payload)
        forged_tag = hmac.new(
            bytes([255]) * 32, subject, hashlib.sha256).digest()[:16]
        relabelled_with_fresh_tag = replace(
            self.stale, binding_sha256=new_digest,
            payload_binding_tag=forged_tag, header_bytes=None)
        with self.assertRaises(BilqisError):
            decode_cache(relabelled_with_fresh_tag, new_binding)

    def test_public_rebuild_rejects_raw_authority_registry(self):
        new_binding = replace(self.old_binding, policy_epoch_sha256="f" * 64)
        with self.assertRaises(TypeError):
            _RAW_REBUILD(
                CACHE_AUTHORITY, self.stale, new_binding,
                eligibility_receipt=_receipt(new_binding),
                persist=lambda _: None,
                authority_registry=AUTHORITY_REGISTRY)

    def test_stale_record_cannot_be_relabelled_as_same_binding(self):
        with self.assertRaises(BilqisError):
            rebuild_revoked_cache(
                self.stale, self.old_binding,
                eligibility_receipt=_receipt(self.old_binding),
                canonical_fp32_source=lambda: self.canonical.copy(),
                persist=lambda _: self.fail("persisted relabelled stale record"))


if __name__ == "__main__":
    unittest.main()
