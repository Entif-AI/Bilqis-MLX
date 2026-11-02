"""BAMF B14.4 revoked-source rejection and qualified FP32 rebuild proofs."""
from dataclasses import replace
import hashlib
import hmac
import unittest
from unittest.mock import patch

import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.tests.model.attention.cache.authority_fixture import (
    CACHE_AUTHORITY,
    OWNER_ID,
    PUBLIC_KEY_HEX,
)
from bilqis_mlx.runtime.atlas_cache_codec import (
    HEAD_WIDTH,
    CacheBinding,
    CacheEligibilityReceipt,
    codec_manifest,
    decode_cache,
    encode_cold_cache,
    rebuild_revoked_cache,
)
from bilqis_mlx.runtime.atlas_cache_binding import (
    _payload_authenticator_subject_fields,
)


_RAW_ENCODE = encode_cold_cache
_RAW_DECODE = decode_cache


def encode_cold_cache(*args, **kwargs):
    return _RAW_ENCODE(CACHE_AUTHORITY, *args, **kwargs)


def decode_cache(*args, **kwargs):
    return _RAW_DECODE(CACHE_AUTHORITY, *args, **kwargs)


_RAW_REBUILD = rebuild_revoked_cache


def rebuild_revoked_cache(*args, **kwargs):
    return _RAW_REBUILD(CACHE_AUTHORITY, *args, **kwargs)


def _binding() -> CacheBinding:
    return CacheBinding(
        codec_manifest(),
        generation_sha256="1" * 64,
        lineage_sha256="2" * 64,
        topology_sha256="3" * 64,
        source_release_sha256="4" * 64,
        semantic_release_sha256="5" * 64,
        source_rights_sha256="6" * 64,
        rights_purpose_sha256="7" * 64,
        policy_epoch_sha256="8" * 64,
        context_eligibility_sha256="9" * 64,
        causal_prefix_sha256="a" * 64,
        masks_sha256="b" * 64,
        scope_sha256="c" * 64,
        key_sha256="d" * 64,
        inference_state_sha256="e" * 64,
        offset=17,
        artifact_authority_id=OWNER_ID,
        artifact_authority_public_key_hex=PUBLIC_KEY_HEX,
    )


def _receipt(binding: CacheBinding, *, eligible=True) -> CacheEligibilityReceipt:
    return CacheEligibilityReceipt(
        binding.source_release_sha256,
        binding.semantic_release_sha256,
        binding.source_rights_sha256,
        binding.rights_purpose_sha256,
        binding.policy_epoch_sha256,
        binding.context_eligibility_sha256,
        eligible,
    )


class RevokedCacheRebuildTests(unittest.TestCase):
    def setUp(self):
        from bilqis_mlx.runtime.tests.model.attention.cache.authority_fixture import install_test_owner
        install_test_owner(self)
        self.old_binding = _binding()
        old_values = np.full((256, HEAD_WIDTH), 3.0, dtype=np.float32)
        self.stale = encode_cold_cache(
            old_values, self.old_binding.codec_manifest, binding=self.old_binding
        )
        rng = np.random.default_rng(485)
        self.canonical = rng.normal(size=(256, HEAD_WIDTH)).astype(np.float32)

    def test_rights_or_permission_epoch_change_rebuilds_from_fresh_fp32(self):
        for field in ("source_rights_sha256", "policy_epoch_sha256"):
            new_binding = replace(
                self.old_binding, **{field: "f" * 64}
            )
            with self.subTest(field=field), self.assertRaises(BilqisError):
                decode_cache(self.stale, new_binding)

            persisted = []
            rebuilt = rebuild_revoked_cache(
                self.stale,
                new_binding,
                eligibility_receipt=_receipt(new_binding),
                canonical_fp32_source=lambda: self.canonical.copy(),
                persist=persisted.append,
            )
            expected = encode_cold_cache(
                self.canonical, new_binding.codec_manifest, binding=new_binding
            )
            self.assertTrue(rebuilt.persisted)
            self.assertEqual(rebuilt.artifact, expected)
            self.assertEqual(persisted, [expected])
            self.assertNotEqual(
                rebuilt.artifact.direction_codes, self.stale.direction_codes
            )

    def test_prefix_and_topology_only_changes_invalidate_before_decode(self):
        for changed in (
            replace(self.old_binding, causal_prefix_sha256="f" * 64),
            replace(self.old_binding, topology_sha256="f" * 64),
        ):
            with self.subTest(binding=changed), self.assertRaises(BilqisError):
                decode_cache(self.stale, changed)
            persisted = []
            rebuilt = rebuild_revoked_cache(
                self.stale,
                changed,
                eligibility_receipt=_receipt(changed),
                canonical_fp32_source=lambda: self.canonical.copy(),
                persist=persisted.append,
            )
            expected = encode_cold_cache(
                self.canonical, changed.codec_manifest, binding=changed,
            )
            self.assertEqual(rebuilt.artifact, expected)
            self.assertEqual(persisted, [expected])

    def test_binding_rejection_precedes_codec_and_payload_decode(self):
        from bilqis_mlx.runtime import atlas_cache_records

        changed_bindings = (
            replace(self.old_binding, source_rights_sha256="f" * 64),
            replace(self.old_binding, causal_prefix_sha256="f" * 64),
            replace(self.old_binding, topology_sha256="f" * 64),
        )
        for changed in changed_bindings:
            with self.subTest(binding=changed), patch.object(
                atlas_cache_records,
                "_codec",
                side_effect=AssertionError("codec entered before stale binding rejected"),
            ):
                with self.assertRaises(BilqisError):
                    decode_cache(self.stale, changed)

    def test_rebuild_result_is_independent_of_stale_lossy_payload(self):
        alternate_values = np.full((256, HEAD_WIDTH), -7.0, dtype=np.float32)
        alternate_stale = encode_cold_cache(
            alternate_values,
            self.old_binding.codec_manifest,
            binding=self.old_binding,
        )
        self.assertNotEqual(
            alternate_stale.direction_codes,
            self.stale.direction_codes,
        )
        new_binding = replace(self.old_binding, policy_epoch_sha256="f" * 64)
        rebuilt = []
        for stale in (self.stale, alternate_stale):
            result = rebuild_revoked_cache(
                stale,
                new_binding,
                eligibility_receipt=_receipt(new_binding),
                canonical_fp32_source=lambda: self.canonical.copy(),
                persist=lambda artifact: None,
            )
            rebuilt.append(result.artifact)
        self.assertEqual(rebuilt[0], rebuilt[1])

    def test_each_new_identity_field_invalidates_old_record(self):
        changes = {
            "source_release_sha256": "f" * 64,
            "semantic_release_sha256": "f" * 64,
            "rights_purpose_sha256": "f" * 64,
            "policy_epoch_sha256": "f" * 64,
            "context_eligibility_sha256": "f" * 64,
            "inference_state_sha256": "f" * 64,
        }
        for field, value in changes.items():
            with self.subTest(field=field), self.assertRaises(BilqisError):
                decode_cache(self.stale, replace(self.old_binding, **{field: value}))

    def test_ineligible_or_mismatched_receipt_cannot_persist(self):
        new_binding = replace(self.old_binding, policy_epoch_sha256="f" * 64)
        cases = (
            _receipt(new_binding, eligible=False),
            replace(
                _receipt(new_binding),
                context_eligibility_sha256="0" * 64,
            ),
        )
        for receipt in cases:
            persisted = []
            with self.subTest(receipt=receipt), self.assertRaises(BilqisError):
                rebuild_revoked_cache(
                    self.stale,
                    new_binding,
                    eligibility_receipt=receipt,
                    canonical_fp32_source=lambda: self.canonical.copy(),
                    persist=persisted.append,
                )
            self.assertEqual(persisted, [])

    def test_rebuild_requires_finite_exact_fp32_canonical_source(self):
        new_binding = replace(self.old_binding, policy_epoch_sha256="f" * 64)
        for values in (
            self.canonical.astype(np.float16),
            np.full((256, HEAD_WIDTH), np.nan, dtype=np.float32),
        ):
            with self.subTest(dtype=values.dtype), self.assertRaises(BilqisError):
                rebuild_revoked_cache(
                    self.stale,
                    new_binding,
                    eligibility_receipt=_receipt(new_binding),
                    canonical_fp32_source=lambda values=values: values,
                    persist=lambda _: self.fail("persisted invalid rebuild"),
                )

    def test_stale_payload_cannot_be_relabelled_under_new_rights_binding(self):
        new_binding = replace(
            self.old_binding, source_rights_sha256="f" * 64
        )
        from bilqis_mlx.runtime.atlas_cache_codec import binding_digest

        new_digest = binding_digest(new_binding)
        relabelled = replace(
            self.stale,
            binding_sha256=new_digest,
            header_bytes=None,
        )
        self.assertEqual(relabelled.direction_codes, self.stale.direction_codes)
        self.assertEqual(relabelled.relative_norms, self.stale.relative_norms)
        self.assertEqual(
            relabelled.block_max_norms_fp32,
            self.stale.block_max_norms_fp32,
        )
        with self.assertRaises(BilqisError):
            decode_cache(relabelled, new_binding)

        # The algorithm is public, but the host-owned MAC key is not. An
        # attacker-chosen key cannot reauthenticate stale bytes under new rights.
        subject = _payload_authenticator_subject_fields(
            self.stale.mode,
            self.stale.true_vectors,
            self.stale.padded_vectors,
            self.stale.head_width,
            new_digest,
            self.stale.direction_codes,
            self.stale.relative_norms,
            self.stale.block_max_norms_fp32,
            self.stale.fp32_payload,
        )
        forged_tag = hmac.new(
            bytes([255]) * 32, subject, hashlib.sha256,
        ).digest()[:16]
        relabelled_with_fresh_tag = replace(
            self.stale,
            binding_sha256=new_digest,
            payload_binding_tag=forged_tag,
            header_bytes=None,
        )
        with self.assertRaises(BilqisError):
            decode_cache(relabelled_with_fresh_tag, new_binding)

    def test_public_rebuild_rejects_raw_authority_registry(self):
        from bilqis_mlx.runtime.tests.model.attention.cache.authority_fixture import (
            AUTHORITY_REGISTRY,
        )

        new_binding = replace(self.old_binding, policy_epoch_sha256="f" * 64)
        with self.assertRaises(TypeError):
            _RAW_REBUILD(
                CACHE_AUTHORITY,
                self.stale,
                new_binding,
                eligibility_receipt=_receipt(new_binding),
                canonical_fp32_source=lambda: self.canonical.copy(),
                persist=lambda _: None,
                authority_registry=AUTHORITY_REGISTRY,
            )

    def test_stale_record_cannot_be_relabelled_as_same_binding(self):
        with self.assertRaises(BilqisError):
            rebuild_revoked_cache(
                self.stale,
                self.old_binding,
                eligibility_receipt=_receipt(self.old_binding),
                canonical_fp32_source=lambda: self.canonical.copy(),
                persist=lambda _: self.fail("persisted relabelled stale record"),
            )


if __name__ == "__main__":
    unittest.main()
