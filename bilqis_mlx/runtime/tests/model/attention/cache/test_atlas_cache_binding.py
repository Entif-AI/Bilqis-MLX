"""BAMF B14.3 causal binding, byte-cost, and inference-policy witnesses."""
from dataclasses import replace
import unittest

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
    CacheQualityObservation,
    CacheQualityPolicy,
    cache_byte_cost,
    codec_manifest,
    decode_cache,
    encode_cold_cache,
    interactive_cache_inference,
    record_header_bytes,
)


_RAW_ENCODE = encode_cold_cache
_RAW_DECODE = decode_cache
_RAW_INFERENCE = interactive_cache_inference


def encode_cold_cache(*args, **kwargs):
    return _RAW_ENCODE(CACHE_AUTHORITY, *args, **kwargs)


def decode_cache(*args, **kwargs):
    return _RAW_DECODE(CACHE_AUTHORITY, *args, **kwargs)


def interactive_cache_inference(*args, **kwargs):
    return _RAW_INFERENCE(CACHE_AUTHORITY, *args, **kwargs)


def _binding(manifest=None) -> CacheBinding:
    return CacheBinding(
        manifest or codec_manifest(),
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


class CacheBindingAndCostTests(unittest.TestCase):
    def setUp(self):
        from bilqis_mlx.runtime.tests.model.attention.cache.authority_fixture import install_test_owner
        install_test_owner(self)
        self.manifest = codec_manifest()
        self.binding = _binding(self.manifest)
        self.values = np.ones((256, HEAD_WIDTH), dtype=np.float32)
        self.artifact = encode_cold_cache(self.values, self.manifest, binding=self.binding)

    def test_full_record_reports_literal_actual_cost_below_parent_bound(self):
        header = record_header_bytes(self.artifact)
        cost = cache_byte_cost(self.artifact)
        self.assertEqual(len(header), 61)
        self.assertEqual(cost.header_bytes, 61)
        self.assertEqual(cost.payload_bytes, 2304 + 256 + 32)
        self.assertEqual(cost.total_bytes, 2653)
        self.assertFalse(hasattr(self.artifact, "authority_signature"))
        self.assertAlmostEqual(
            cost.effective_bits_per_channel,
            2653 * 8 / (256 * HEAD_WIDTH),
        )
        self.assertLessEqual(cost.effective_bits_per_channel, 3.5)


    def test_fp32_fallback_reports_header_plus_exact_payload_bytes(self):
        values = np.ones((255, HEAD_WIDTH), dtype=np.float32)
        artifact = encode_cold_cache(
            values, self.manifest, binding=self.binding
        )
        cost = cache_byte_cost(artifact)
        self.assertEqual(cost.header_bytes, 61)
        self.assertEqual(cost.payload_bytes, values.size * 4)
        self.assertEqual(cost.total_bytes, 61 + values.size * 4)
        self.assertAlmostEqual(
            cost.effective_bits_per_channel,
            cost.total_bytes * 8 / values.size,
        )


    def test_each_causal_identity_change_recomputes_before_lossy_use(self):
        reference = ("fp32", 484)
        changes = {
            "generation_sha256": "9" * 64,
            "lineage_sha256": "a" * 64,
            "topology_sha256": "b" * 64,
            "source_release_sha256": "f" * 64,
            "semantic_release_sha256": "0" * 64,
            "source_rights_sha256": "1" * 64,
            "rights_purpose_sha256": "2" * 64,
            "policy_epoch_sha256": "3" * 64,
            "context_eligibility_sha256": "4" * 64,
            "causal_prefix_sha256": "5" * 64,
            "masks_sha256": "6" * 64,
            "scope_sha256": "7" * 64,
            "key_sha256": "8" * 64,
            "inference_state_sha256": "9" * 64,
            "offset": 18,
        }

        def forbidden_cache_use(_):
            self.fail("stale lossy payload influenced output")

        for field, value in changes.items():
            with self.subTest(field=field):
                changed = replace(self.binding, **{field: value})
                with self.assertRaises(BilqisError):
                    decode_cache(self.artifact, changed)
                result = interactive_cache_inference(
                    self.artifact,
                    changed,
                    cached_infer=forbidden_cache_use,
                    fp32_recompute=lambda: reference,
                    quality_check=lambda _: CacheQualityObservation(True, 0.0),
                    policy=CacheQualityPolicy(0.01),
                )
                self.assertEqual(result.value, reference)
                self.assertFalse(result.used_cache)
                self.assertEqual(result.fallback_reason, "BINDING_MISMATCH")
                self.assertIsNone(result.byte_cost)




if __name__ == "__main__":
    unittest.main()
