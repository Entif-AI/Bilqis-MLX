"""Atlas-native use witness for B14 cold K/V restoration and FP32 fallback."""
from dataclasses import replace
import os
import unittest
from unittest.mock import patch

import mlx.core as mx
import numpy as np

from bilqis_mlx.learning.source_atoms.backbone import _b14_attention_caches
from bilqis_mlx.runtime.atlas_attention import (
    AttentionScope, attention_parameter_view, ccgqa,
)
from bilqis_mlx.runtime.atlas_cache_codec import (
    CacheQualityObservation, CacheQualityPolicy,
    attention_cache_pairs, encode_attention_cache,
    interactive_attention_cache_inference,
)
from bilqis_mlx.runtime.atlas_cache_runtime import _capture_forward_attention_caches
from bilqis_mlx.runtime.tests.model.attention.cache.cache_production_source_fixture import (
    source_backed_production_fixture,
)


@unittest.skipUnless(
    os.environ.get("BILQIS_ATLAS_REAL_ARTIFACT"),
    "real repo-pinned A01 artifact supplied at source turn-in",
)
class AtlasNativeColdCacheUseTests(unittest.TestCase):
    def test_restored_pair_enters_ccgqa_or_falls_back_to_exact_fp32(self):
        cache, batch, producer, parameters, _snapshot = (
            source_backed_production_fixture())
        with patch(
            "bilqis_mlx.runtime.bamf_bundle.execution_cache."
            "require_accepted_execution_cache", return_value=cache,
        ):
            authority = _capture_forward_attention_caches(cache, batch, producer)
            layer, key_handle, value_handle = attention_cache_pairs(authority)[0]
            key_artifact, _ = encode_attention_cache(authority, key_handle)
            value_artifact, _ = encode_attention_cache(authority, value_handle)

            params = attention_parameter_view(
                parameters, spec=producer._topology,
                extents=batch.compiled.extents, layer=layer)
            original = _b14_attention_caches(producer)[layer]
            batch_size = original.key.shape[0]
            hidden = mx.zeros(
                (batch_size, 1, producer._topology.width), dtype=mx.float32)
            valid = mx.ones((batch_size, 1), dtype=mx.bool_)
            scope_ids = original.scope_ids[:, -1:]
            scope = AttentionScope(
                scope_ids, layer, original.generation, "f" * 64,
                parent_prefix_digest=original.prefix_digest)
            offset = original.start_offset + original.key.shape[2]
            reference, _ = ccgqa(
                params, hidden, valid, scope, cache=original, offset=offset)
            reference_np = np.asarray(reference, dtype=np.float32)

            def cached_infer(restored):
                value, _ = ccgqa(
                    params, hidden, valid, scope, cache=restored, offset=offset)
                return np.asarray(value, dtype=np.float32)

            def quality(candidate):
                denominator = max(float(np.linalg.norm(reference_np)), 1e-12)
                drift = float(
                    np.linalg.norm(candidate - reference_np) / denominator)
                return CacheQualityObservation(
                    int(np.argmax(candidate)) == int(np.argmax(reference_np)),
                    drift)

            result = interactive_attention_cache_inference(
                authority, key_artifact, key_handle,
                value_artifact, value_handle, parameters,
                producer._topology, batch.compiled.extents,
                cached_infer=cached_infer,
                fp32_recompute=lambda: reference_np.copy(),
                quality_check=quality, policy=CacheQualityPolicy(0.10))

        if result.used_cache:
            observation = quality(result.value)
            self.assertTrue(observation.typed_answer_valid)
            self.assertLessEqual(observation.score_drift, 0.10)
        else:
            np.testing.assert_array_equal(result.value, reference_np)

    def test_pair_preflight_rejects_bad_value_before_decoding_key(self):
        cache, batch, producer, parameters, _snapshot = (
            source_backed_production_fixture())
        with patch(
            "bilqis_mlx.runtime.bamf_bundle.execution_cache."
            "require_accepted_execution_cache", return_value=cache,
        ):
            authority = _capture_forward_attention_caches(cache, batch, producer)
            _layer, key_handle, value_handle = attention_cache_pairs(authority)[0]
            key_artifact, _ = encode_attention_cache(authority, key_handle)
            value_artifact, _ = encode_attention_cache(authority, value_handle)
            bad_value = replace(
                value_artifact,
                header_bytes=value_artifact.header_bytes[:-1]
                + bytes([value_artifact.header_bytes[-1] ^ 1]),
            )
            with patch(
                "bilqis_mlx.runtime.atlas_cache_records._decode_cache"
            ) as raw_decode:
                result = interactive_attention_cache_inference(
                    authority, key_artifact, key_handle,
                    bad_value, value_handle, parameters,
                    producer._topology, batch.compiled.extents,
                    cached_infer=lambda _: self.fail("stale pair reached attention"),
                    fp32_recompute=lambda: "FP32",
                    quality_check=lambda _: self.fail("stale pair reached quality"),
                    policy=CacheQualityPolicy(0.10))
            raw_decode.assert_not_called()
            self.assertEqual(
                (result.value, result.used_cache, result.fallback_reason),
                ("FP32", False, "BINDING_MISMATCH"))


if __name__ == "__main__":
    unittest.main()
