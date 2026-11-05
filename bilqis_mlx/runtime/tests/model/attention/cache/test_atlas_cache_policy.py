"""BAMF B14.3 causal binding, byte-cost, and inference-policy witnesses."""
from dataclasses import replace
import ast
from pathlib import Path
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
    reference_candidate_evaluation,
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


class CachePolicyTests(unittest.TestCase):
    def setUp(self):
        from bilqis_mlx.runtime.tests.model.attention.cache.authority_fixture import install_test_owner
        install_test_owner(self)
        self.manifest = codec_manifest()
        self.binding = _binding(self.manifest)
        self.values = np.ones((256, HEAD_WIDTH), dtype=np.float32)
        self.artifact = encode_cold_cache(self.values, self.manifest, binding=self.binding)

    def test_reference_candidate_evaluation_is_exact_fp32_only(self):
        values = np.arange(12, dtype=np.float32).reshape(3, 4)
        observed = reference_candidate_evaluation(
            values, lambda state: (state.dtype.str, state.tobytes())
        )
        self.assertEqual(observed, (values.dtype.str, values.tobytes()))
        for invalid in (
            values.astype(np.float16),
            np.full((1, 1), np.nan, dtype=np.float32),
        ):
            with self.subTest(dtype=invalid.dtype), self.assertRaises(BilqisError):
                reference_candidate_evaluation(invalid, lambda state: state)


    def test_interactive_quality_failures_recompute_fp32(self):
        reference = {"answer": "FP32"}
        cases = (
            (CacheQualityObservation(False, 0.0), "TYPED_ANSWER_INVALID"),
            (CacheQualityObservation(True, 0.02), "SCORE_DRIFT_EXCEEDED"),
        )
        for observation, reason in cases:
            with self.subTest(reason=reason):
                result = interactive_cache_inference(
                    self.artifact,
                    self.binding,
                    cached_infer=lambda _: {"answer": "CACHE"},
                    fp32_recompute=lambda: reference,
                    quality_check=lambda _: observation,
                    policy=CacheQualityPolicy(0.01),
                )
                self.assertEqual(result.value, reference)
                self.assertEqual(result.fallback_reason, reason)
                self.assertFalse(result.used_cache)

        accepted = interactive_cache_inference(
            self.artifact,
            self.binding,
            cached_infer=lambda _: {"answer": "CACHE"},
            fp32_recompute=lambda: reference,
            quality_check=lambda _: CacheQualityObservation(True, 0.01),
            policy=CacheQualityPolicy(0.01),
        )
        self.assertEqual(accepted.value, {"answer": "CACHE"})
        self.assertTrue(accepted.used_cache)
        self.assertIsNone(accepted.fallback_reason)
        self.assertEqual(accepted.byte_cost, cache_byte_cost(self.artifact))


    def test_lossy_cache_owners_have_no_training_gold_or_sidecar_dependencies(self):
        from bilqis_mlx.runtime import (
            atlas_cache_binding,
            atlas_cache_codec,
            atlas_cache_policy,
            atlas_cache_rebuild,
            atlas_cache_records,
        )

        imports = set()
        for module in (
            atlas_cache_binding,
            atlas_cache_codec,
            atlas_cache_policy,
            atlas_cache_rebuild,
            atlas_cache_records,
        ):
            tree = ast.parse(Path(module.__file__).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module)
        forbidden = (
            "bilqis_mlx.learning",
            "atlas_optimizer",
            "gold",
            "frame_sidecar",
        )
        self.assertEqual(
            sorted(name for name in imports if any(token in name for token in forbidden)),
            [],
        )



    def test_measured_attention_drift_and_answer_disagreement_use_fp32(self):
        # Fixed B14 attention fixture; both K and V use the same cold-record API.
        rng = np.random.default_rng(484)
        keys = rng.normal(size=(256, HEAD_WIDTH)).astype(np.float32)
        values = rng.normal(size=(256, HEAD_WIDTH)).astype(np.float32)
        query = rng.normal(size=(HEAD_WIDTH,)).astype(np.float32)

        def attention(k, v):
            logits = k @ query / np.sqrt(HEAD_WIDTH)
            weights = np.exp(logits - logits.max())
            weights /= weights.sum()
            return weights @ v

        reference = attention(keys, values)
        cached_values = decode_cache(
            encode_cold_cache(values, self.manifest, binding=self.binding), self.binding
        )
        key_artifact = encode_cold_cache(keys, self.manifest, binding=self.binding)
        approximate = attention(decode_cache(key_artifact, self.binding), cached_values)
        drift = float(np.linalg.norm(approximate-reference)/np.linalg.norm(reference))
        agreement = int(np.argmax(approximate)) == int(np.argmax(reference))
        result = interactive_cache_inference(
            key_artifact, self.binding,
            cached_infer=lambda k: attention(k, cached_values),
            fp32_recompute=lambda: reference.copy(),
            quality_check=lambda output: CacheQualityObservation(
                int(np.argmax(output)) == int(np.argmax(reference)),
                float(np.linalg.norm(output-reference)/np.linalg.norm(reference)),
            ),
            policy=CacheQualityPolicy(0.10),
        )
        self.assertTrue(agreement)
        self.assertAlmostEqual(drift, 0.3674886, places=5)
        self.assertFalse(result.used_cache)
        self.assertEqual(result.fallback_reason, "SCORE_DRIFT_EXCEEDED")
        np.testing.assert_array_equal(result.value, reference)

    def test_malformed_artifact_recomputes_instead_of_raw_attribute_error(self):
        for artifact in (None, object(), {"binding_sha256": b"x"*32}):
            result = interactive_cache_inference(
                artifact, self.binding,
                cached_infer=lambda _: self.fail("malformed cache influenced output"),
                fp32_recompute=lambda: "FP32",
                quality_check=lambda _: CacheQualityObservation(True, 0.0),
                policy=CacheQualityPolicy(0.10),
            )
            self.assertEqual((result.value, result.used_cache), ("FP32", False))
