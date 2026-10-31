"""BAMF B14.2 norm reconstruction and small-record fallback proofs."""
import subprocess
import sys
import unittest

import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_cache_codec import (
    BLOCK_VECTORS,
    CACHE_MODE_FP32,
    CACHE_MODE_ROT3,
    HEAD_WIDTH,
    MIN_COMPRESSED_VECTORS,
    CacheBinding,
    codec_manifest,
    decode_cache,
    encode_cold_cache,
    pack_3bit,
    quantize_directions,
    unpack_3bit,
)


class Rot3NormAndFallbackTests(unittest.TestCase):
    def setUp(self):
        self.manifest = codec_manifest()
        self.binding = CacheBinding(
            self.manifest,
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

    def test_direct_records_import_is_order_independent(self):
        result = subprocess.run(
            [sys.executable, "-c",
             "import bilqis_mlx.runtime.atlas_cache_records as r; print(r.BLOCK_VECTORS)"],
            capture_output=True, text=True,
        )
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "32"))

    def test_small_records_remain_exact_finite_fp32(self):
        rng = np.random.default_rng(483)
        values = rng.normal(size=(MIN_COMPRESSED_VECTORS - 1, HEAD_WIDTH)).astype(np.float32)
        values[5] = 0.0
        artifact = encode_cold_cache(values, self.manifest, binding=self.binding)
        self.assertEqual(artifact.mode, CACHE_MODE_FP32)
        self.assertEqual(artifact.true_vectors, MIN_COMPRESSED_VECTORS - 1)
        self.assertEqual(artifact.padded_vectors, MIN_COMPRESSED_VECTORS - 1)
        self.assertEqual(artifact.direction_codes, b"")
        self.assertEqual(artifact.relative_norms, b"")
        self.assertEqual(artifact.block_max_norms_fp32, b"")
        self.assertEqual(len(artifact.fp32_payload), values.size * 4)
        np.testing.assert_array_equal(decode_cache(artifact, self.binding), values)
        forged = bytearray(artifact.fp32_payload)
        forged[:4] = np.asarray([np.nan], dtype="<f4").tobytes()
        invalid = artifact.__class__(**{**artifact.__dict__, "fp32_payload": bytes(forged)})
        with self.assertRaises(BilqisError):
            decode_cache(invalid, self.binding)

    def test_full_threshold_record_uses_eight_norm_blocks(self):
        values = np.ones((MIN_COMPRESSED_VECTORS, HEAD_WIDTH), dtype=np.float32)
        artifact = encode_cold_cache(values, self.manifest, binding=self.binding)
        self.assertEqual(artifact.mode, CACHE_MODE_ROT3)
        self.assertEqual(artifact.true_vectors, 256)
        self.assertEqual(artifact.padded_vectors, 256)
        self.assertEqual(len(artifact.relative_norms), 256)
        self.assertEqual(len(artifact.block_max_norms_fp32), (256 // BLOCK_VECTORS) * 4)
        self.assertEqual(len(artifact.direction_codes), 256 * HEAD_WIDTH * 3 // 8)
        self.assertEqual(artifact.fp32_payload, b"")

    def test_relative_norms_are_block_local_uint8_and_restore_scale(self):
        values = np.zeros((MIN_COMPRESSED_VECTORS, HEAD_WIDTH), dtype=np.float32)
        norms = np.linspace(0.0, 31.0, BLOCK_VECTORS, dtype=np.float32)
        values[:BLOCK_VECTORS, 0] = norms
        artifact = encode_cold_cache(values, self.manifest, binding=self.binding)
        expected = np.rint(norms / np.float32(31.0) * np.float32(255.0)).astype(np.uint8)
        np.testing.assert_array_equal(
            np.frombuffer(artifact.relative_norms[:BLOCK_VECTORS], dtype=np.uint8),
            expected,
        )
        maxima = np.frombuffer(artifact.block_max_norms_fp32, dtype="<f4")
        self.assertEqual(float(maxima[0]), 31.0)
        decoded = decode_cache(artifact, self.binding)
        recovered = np.linalg.norm(decoded[:BLOCK_VECTORS], axis=-1)
        expected_norms = expected.astype(np.float32) * np.float32(31.0 / 255.0)
        np.testing.assert_allclose(recovered, expected_norms, atol=2e-5, rtol=2e-5)

    def test_zero_vectors_decode_exactly_zero_in_compressed_record(self):
        rng = np.random.default_rng(1483)
        values = rng.normal(size=(MIN_COMPRESSED_VECTORS, HEAD_WIDTH)).astype(np.float32)
        values[[0, 31, 32, 255]] = 0.0
        decoded = decode_cache(
            encode_cold_cache(values, self.manifest, binding=self.binding),
            self.binding,
        )
        np.testing.assert_array_equal(decoded[[0, 31, 32, 255]], 0.0)

    def test_tail_padding_is_canonical_and_decode_returns_true_length(self):
        rng = np.random.default_rng(2483)
        values = rng.normal(size=(MIN_COMPRESSED_VECTORS + 1, HEAD_WIDTH)).astype(np.float32)
        artifact = encode_cold_cache(values, self.manifest, binding=self.binding)
        self.assertEqual((artifact.true_vectors, artifact.padded_vectors), (257, 288))
        self.assertEqual(artifact.relative_norms[257:], bytes(31))
        codes = unpack_3bit(artifact.direction_codes, artifact.padded_vectors * HEAD_WIDTH)
        codes = codes.reshape(artifact.padded_vectors, HEAD_WIDTH)
        canonical = quantize_directions(np.zeros((31, HEAD_WIDTH), dtype=np.float32))
        np.testing.assert_array_equal(codes[257:], canonical)
        self.assertEqual(decode_cache(artifact, self.binding).shape, values.shape)

        forged_norms = bytearray(artifact.relative_norms)
        forged_norms[257] = 1
        forged_codes = codes.copy()
        forged_codes[257, 0] = (int(forged_codes[257, 0]) + 1) % 8
        for changes in (
            {"relative_norms": bytes(forged_norms)},
            {"direction_codes": pack_3bit(forged_codes.reshape(-1))},
        ):
            forged = artifact.__class__(**{**artifact.__dict__, **changes})
            with self.assertRaises(BilqisError):
                decode_cache(forged, self.binding)

    def test_malformed_record_payloads_fail_closed(self):
        values = np.ones((MIN_COMPRESSED_VECTORS, HEAD_WIDTH), dtype=np.float32)
        artifact = encode_cold_cache(values, self.manifest, binding=self.binding)
        malformed = (
            artifact.__class__(**{**artifact.__dict__, "relative_norms": artifact.relative_norms[:-1]}),
            artifact.__class__(**{**artifact.__dict__, "block_max_norms_fp32": b"\xff" * len(artifact.block_max_norms_fp32)}),
            artifact.__class__(**{**artifact.__dict__, "padded_vectors": artifact.padded_vectors - 1}),
        )
        for candidate in malformed:
            with self.subTest(candidate=candidate), self.assertRaises(BilqisError):
                decode_cache(candidate, self.binding)

    def test_norm_blocks_reject_noncanonical_zero_and_maximum_relatives(self):
        zero_artifact = encode_cold_cache(
            np.zeros((MIN_COMPRESSED_VECTORS, HEAD_WIDTH), dtype=np.float32),
            self.manifest, binding=self.binding,
        )
        forged_zero = bytearray(zero_artifact.relative_norms)
        forged_zero[0] = 1
        full_artifact = encode_cold_cache(
            np.ones((MIN_COMPRESSED_VECTORS, HEAD_WIDTH), dtype=np.float32),
            self.manifest, binding=self.binding,
        )
        forged_full = bytearray(full_artifact.relative_norms)
        forged_full[:BLOCK_VECTORS] = bytes([254]) * BLOCK_VECTORS
        for artifact, payload in (
            (zero_artifact, forged_zero),
            (full_artifact, forged_full),
        ):
            forged = artifact.__class__(
                **{**artifact.__dict__, "relative_norms": bytes(payload)}
            )
            with self.subTest(mode=artifact.mode), self.assertRaises(BilqisError):
                decode_cache(forged, self.binding)


if __name__ == "__main__":
    unittest.main()
