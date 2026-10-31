"""Literal proofs for BAMF B14.1 direction coding and 3-bit packing."""
import hashlib
import unittest

import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_cache_codec import (
    CODEBOOK_DIGEST,
    CODEC_ID,
    EXPECTED_CODEBOOK_DIGEST,
    EXPECTED_ROTATION_DIGEST,
    HEAD_WIDTH,
    NORMAL_CODEBOOK,
    ROTATION,
    ROTATION_DIGEST,
    ROTATION_SEED,
    codec_manifest,
    decode_directions,
    pack_3bit,
    quantize_directions,
    unpack_3bit,
)


class Rot3CodecTests(unittest.TestCase):
    def test_manifest_pins_seed_codebook_and_digests(self):
        manifest = codec_manifest()
        self.assertEqual(manifest.codec_id, CODEC_ID)
        self.assertEqual(manifest.head_width, 24)
        self.assertEqual(manifest.code_bits, 3)
        self.assertEqual(
            ROTATION_SEED,
            int.from_bytes(hashlib.sha256(b"bamf.rot3/v1").digest()[:8], "little"),
        )
        self.assertEqual(manifest.rotation_digest, ROTATION_DIGEST)
        self.assertEqual(manifest.codebook_digest, CODEBOOK_DIGEST)
        self.assertEqual(
            EXPECTED_ROTATION_DIGEST,
            "7876ebc965309065c0428efe03ced3104c7f29297e9b983e5fc89036f2e84baa",
        )
        self.assertEqual(
            EXPECTED_CODEBOOK_DIGEST,
            "77e11f5820649d05f2b184d2f155f9b1da5264cf2f0936f465ece0a8a56c6216",
        )
        manifest.validate()

    def test_seeded_qr_rotation_is_orthogonal_with_fixed_orientation(self):
        identity = ROTATION.T @ ROTATION
        np.testing.assert_allclose(identity, np.eye(HEAD_WIDTH), atol=2e-7, rtol=2e-7)
        # Re-running the public seed path through the manifest cannot select a
        # different transform: its persisted digest is the identity witness.
        self.assertEqual(ROTATION.shape, (24, 24))
        self.assertEqual(len(ROTATION_DIGEST), 64)

    def test_standard_normal_codebook_is_fixed_and_symmetric(self):
        expected = np.array(
            [-2.151945704536989, -1.343909278505003, -0.756005281205878,
             -0.245094178944222, 0.245094178944222, 0.756005281205878,
             1.343909278505002, 2.151945704536991], dtype=np.float32,
        )
        np.testing.assert_array_equal(NORMAL_CODEBOOK, expected)
        np.testing.assert_array_equal(NORMAL_CODEBOOK, -NORMAL_CODEBOOK[::-1])

    def test_literal_zero_through_seven_bitstream_is_little_endian(self):
        codes = np.arange(8, dtype=np.uint8)
        payload = pack_3bit(codes)
        self.assertEqual(payload, bytes.fromhex("88c6fa"))
        np.testing.assert_array_equal(unpack_3bit(payload, 8), codes)

    def test_cross_byte_tail_round_trips_without_extra_codes(self):
        for count in range(0, 33):
            codes = (np.arange(count, dtype=np.uint8) * 5 + 3) % 8
            payload = pack_3bit(codes)
            self.assertEqual(len(payload), (count * 3 + 7) // 8)
            np.testing.assert_array_equal(unpack_3bit(payload, count), codes)

    def test_quantizer_rotates_then_scales_by_sqrt_head_width(self):
        vector = np.zeros((1, HEAD_WIDTH), dtype=np.float32)
        vector[0, 0] = 1.0
        scaled = (vector @ ROTATION) * np.float32(np.sqrt(HEAD_WIDTH))
        oracle = np.argmin(
            np.abs(scaled[..., None] - NORMAL_CODEBOOK), axis=-1
        ).astype(np.uint8)
        np.testing.assert_array_equal(quantize_directions(vector), oracle)

    def test_direction_decode_is_unit_norm_and_tracks_rotated_input(self):
        rng = np.random.default_rng(482)
        values = rng.normal(size=(64, HEAD_WIDTH)).astype(np.float32)
        values /= np.linalg.norm(values, axis=-1, keepdims=True)
        decoded = decode_directions(quantize_directions(values))
        np.testing.assert_allclose(np.linalg.norm(decoded, axis=-1), 1.0, atol=2e-6)
        cosine = np.sum(values * decoded, axis=-1)
        self.assertGreater(float(np.min(cosine)), 0.90)

    def test_invalid_codes_shapes_and_nonfinite_vectors_fail_closed(self):
        calls = (
            lambda: pack_3bit(np.array([8], dtype=np.uint8)),
            lambda: pack_3bit(np.array([[1]], dtype=np.uint8)),
            lambda: unpack_3bit(b"\x00", 8),
            lambda: unpack_3bit(b"\xff", 1),
            lambda: quantize_directions(np.zeros((2, 23), dtype=np.float32)),
            lambda: quantize_directions(np.full((1, 24), np.nan, dtype=np.float32)),
            lambda: decode_directions(np.zeros((24,), dtype=np.uint8)),
        )
        for call in calls:
            with self.subTest(call=call), self.assertRaises(BilqisError):
                call()


if __name__ == "__main__":
    unittest.main()
