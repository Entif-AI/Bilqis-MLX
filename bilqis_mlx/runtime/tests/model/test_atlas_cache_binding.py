"""BAMF B14.3 causal binding, byte-cost, and inference-policy witnesses."""
from dataclasses import replace
import ast
from pathlib import Path
import unittest

import numpy as np

from bilqis_mlx.errors import BilqisError
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


def _binding(manifest=None) -> CacheBinding:
    return CacheBinding(
        manifest or codec_manifest(),
        generation_sha256="1" * 64,
        lineage_sha256="2" * 64,
        topology_sha256="3" * 64,
        source_rights_sha256="4" * 64,
        causal_prefix_sha256="5" * 64,
        masks_sha256="6" * 64,
        scope_sha256="7" * 64,
        key_sha256="8" * 64,
        offset=17,
    )


class CacheBindingAndCostTests(unittest.TestCase):
    def setUp(self):
        self.manifest = codec_manifest()
        self.binding = _binding(self.manifest)
        self.values = np.ones((256, HEAD_WIDTH), dtype=np.float32)
        self.artifact = encode_cold_cache(
            self.values, self.manifest, binding=self.binding
        )

    def test_full_record_reports_literal_actual_cost_below_parent_bound(self):
        header = record_header_bytes(self.artifact)
        cost = cache_byte_cost(self.artifact)
        self.assertEqual(len(header), 45)
        self.assertEqual(cost.header_bytes, 45)
        self.assertEqual(cost.payload_bytes, 2304 + 256 + 32)
        self.assertEqual(cost.total_bytes, 2637)
        self.assertAlmostEqual(
            cost.effective_bits_per_channel,
            2637 * 8 / (256 * HEAD_WIDTH),
        )
        self.assertLessEqual(cost.effective_bits_per_channel, 3.5)

    def test_fp32_fallback_reports_header_plus_exact_payload_bytes(self):
        values = np.ones((255, HEAD_WIDTH), dtype=np.float32)
        artifact = encode_cold_cache(
            values, self.manifest, binding=self.binding
        )
        cost = cache_byte_cost(artifact)
        self.assertEqual(cost.header_bytes, 45)
        self.assertEqual(cost.payload_bytes, values.size * 4)
        self.assertEqual(cost.total_bytes, 45 + values.size * 4)
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
            "source_rights_sha256": "c" * 64,
            "causal_prefix_sha256": "d" * 64,
            "masks_sha256": "e" * 64,
            "scope_sha256": "f" * 64,
            "key_sha256": "0" * 64,
            "offset": 18,
        }

        def forbidden_cache_use(_):
            raise AssertionError("stale lossy payload influenced output")

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

    def test_wrong_codec_manifest_recomputes_before_decode(self):
        from bilqis_mlx.runtime.atlas_cache_codec import Rot3Manifest

        wrong = Rot3Manifest(codebook_digest="0" * 64)
        result = interactive_cache_inference(
            self.artifact,
            replace(self.binding, codec_manifest=wrong),
            cached_infer=lambda _: self.fail("decoded stale codec"),
            fp32_recompute=lambda: "reference",
            quality_check=lambda _: CacheQualityObservation(True, 0.0),
            policy=CacheQualityPolicy(0.01),
        )
        self.assertEqual((result.value, result.used_cache), ("reference", False))

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
        from bilqis_mlx.runtime import atlas_cache_policy, atlas_cache_records

        imports = set()
        for module in (atlas_cache_policy, atlas_cache_records):
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


if __name__ == "__main__":
    unittest.main()
