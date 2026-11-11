"""Authority-hardening and physical-record edge witnesses for B14."""
from dataclasses import replace
from inspect import signature
import unittest

import numpy as np
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime import atlas_cache_rebuild, atlas_cache_runtime
from bilqis_mlx.runtime.atlas_cache_codec import (
    HEAD_WIDTH, CacheAuthorityRuntime, CacheQualityObservation,
    CacheQualityPolicy, Rot3Manifest, cache_byte_cost, codec_manifest,
    record_header_bytes,
)
from bilqis_mlx.runtime.tests.model.attention.cache.authority_fixture import (
    CACHE_AUTHORITY, authority_registry, install_test_owner,
)
from bilqis_mlx.runtime.tests.model.attention.cache.test_atlas_cache_binding import (
    _RAW_DECODE, _RAW_ENCODE, _RAW_INFERENCE, _binding,
    decode_cache, encode_cold_cache, interactive_cache_inference,
)


class CacheRuntimeBoundaryTests(unittest.TestCase):
    def setUp(self):
        install_test_owner(self)
        self.manifest = codec_manifest()
        self.binding = _binding(self.manifest)
        self.values = np.ones((256, HEAD_WIDTH), dtype=np.float32)
        self.artifact = encode_cold_cache(
            self.values, self.manifest, binding=self.binding)

    def test_production_cache_runtime_exposes_no_authority_mint(self):
        self.assertFalse(hasattr(atlas_cache_runtime, "_host_cache_authority"))
        self.assertFalse(hasattr(CacheAuthorityRuntime, "_issue"))
        self.assertFalse(hasattr(atlas_cache_rebuild, "_issue_eligibility"))
        self.assertNotIn(
            "canonical_fp32_source",
            signature(atlas_cache_runtime.rebuild_revoked_cache).parameters,
        )
        public_boundaries = (
            "bind_accepted_cache_authority", "attention_cache_binding",
            "attention_cache_handles", "encode_attention_cache",
            "rebuild_attention_cache", "bind_cache_artifact_owner",
            "apply_cache_correction", "encode_cold_cache", "decode_cache",
            "interactive_cache_inference", "rebuild_revoked_cache",
            "issue_cache_eligibility",
        )
        for name in public_boundaries:
            parameters = set(signature(getattr(atlas_cache_runtime, name)).parameters)
            with self.subTest(callable=name):
                self.assertTrue(parameters.isdisjoint({"registry", "mac_key"}))

    def test_public_cache_boundary_rejects_caller_selected_registry(self):
        attacker = Ed25519PrivateKey.from_private_bytes(bytes([255]) * 32)
        attacker_public = attacker.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
        attacker_binding = replace(
            self.binding, artifact_authority_public_key_hex=attacker_public)
        attacker_registry = authority_registry(attacker_public)
        with self.assertRaises(BilqisError):
            CacheAuthorityRuntime(attacker_registry, bytes([255]) * 32)
        self.assertFalse(hasattr(CacheAuthorityRuntime, "_issue"))
        with self.assertRaises(BilqisError):
            _RAW_ENCODE(
                attacker_registry, self.values, self.manifest,
                binding=attacker_binding)
        with self.assertRaises(BilqisError):
            _RAW_ENCODE(
                CACHE_AUTHORITY, self.values, self.manifest,
                binding=attacker_binding)
        for call in (
            lambda: _RAW_ENCODE(
                CACHE_AUTHORITY, self.values, self.manifest,
                binding=self.binding, authority_registry=attacker_registry),
            lambda: _RAW_DECODE(
                CACHE_AUTHORITY, self.artifact, self.binding,
                authority_registry=attacker_registry),
            lambda: _RAW_INFERENCE(
                CACHE_AUTHORITY, self.artifact, self.binding,
                cached_infer=lambda _: "cache", fp32_recompute=lambda: "fp32",
                quality_check=lambda _: CacheQualityObservation(True, 0.0),
                policy=CacheQualityPolicy(0.01),
                authority_registry=attacker_registry),
        ):
            with self.assertRaises(TypeError):
                call()

    def test_exact_type_forgery_is_not_issued_by_cache_owner(self):
        class NoOpRegistry:
            def require_claimed_authority(self, *args):
                pass

        forged = object.__new__(CacheAuthorityRuntime)
        object.__setattr__(
            forged, "_CacheAuthorityRuntime__registry", NoOpRegistry())
        object.__setattr__(
            forged, "_CacheAuthorityRuntime__mac_key", bytes([255]) * 32)
        with self.assertRaises(BilqisError):
            _RAW_ENCODE(forged, self.values, self.manifest, binding=self.binding)
        with self.assertRaises(BilqisError):
            _RAW_DECODE(forged, self.artifact, self.binding)

    def test_replacing_issued_slots_does_not_replace_owner_state(self):
        object.__setattr__(
            CACHE_AUTHORITY, "_CacheAuthorityRuntime__registry", None)
        object.__setattr__(
            CACHE_AUTHORITY, "_CacheAuthorityRuntime__mac_key", b"attacker")
        artifact = _RAW_ENCODE(
            CACHE_AUTHORITY, self.values, self.manifest, binding=self.binding)
        decoded = _RAW_DECODE(CACHE_AUTHORITY, artifact, self.binding)
        self.assertEqual(decoded.shape, self.values.shape)

    def test_wrong_codec_manifest_recomputes_before_decode(self):
        wrong = Rot3Manifest(codebook_digest="0" * 64)
        result = interactive_cache_inference(
            self.artifact, replace(self.binding, codec_manifest=wrong),
            cached_infer=lambda _: self.fail("decoded stale codec"),
            fp32_recompute=lambda: "reference",
            quality_check=lambda _: CacheQualityObservation(True, 0.0),
            policy=CacheQualityPolicy(0.01),
        )
        self.assertEqual((result.value, result.used_cache), ("reference", False))

    def test_artifact_header_rejects_each_selected_byte_mutation(self):
        header = self.artifact.header_bytes
        self.assertEqual(header, record_header_bytes(self.artifact))
        for index in (0, 4, 5, 36, 37, 45, 52, 53, 57, 60):
            forged = header[:index] + bytes([header[index] ^ 1]) + header[index + 1:]
            with self.subTest(index=index), self.assertRaises(BilqisError):
                decode_cache(
                    replace(self.artifact, header_bytes=forged), self.binding)

    def test_padded_record_cost_decides_rot3_or_exact_fp32(self):
        for count, compressed in (
            (256, True), (257, False), (280, False), (282, False),
            (283, False), (288, True), (289, False), (320, True),
        ):
            values = np.ones((count, HEAD_WIDTH), dtype=np.float32)
            artifact = encode_cold_cache(
                values, self.manifest, binding=self.binding)
            cost = cache_byte_cost(artifact)
            with self.subTest(count=count):
                self.assertEqual(artifact.mode, "ROT3" if compressed else "FP32")
                self.assertEqual(len(artifact.header_bytes), cost.header_bytes)
                if compressed:
                    self.assertLessEqual(cost.effective_bits_per_channel, 3.5)
                else:
                    np.testing.assert_array_equal(
                        decode_cache(artifact, self.binding), values)


if __name__ == "__main__":
    unittest.main()
