"""Deterministic direction coding primitives for the BAMF ``rot3/v1`` cache.

This leaf owns only rotation, scalar-codebook quantization, and 3-bit packing.
Norm storage, record eligibility/fallback, binding validation, and cache custody
remain with later B14 owners.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math

import numpy as np

from bilqis_mlx.errors import ErrorBus, SCHOOL


CODEC_ID = "bamf.rot3/v1"
HEAD_WIDTH = 24
CODE_BITS = 3
CODE_COUNT = 1 << CODE_BITS
ROTATION_SEED = int.from_bytes(
    hashlib.sha256(CODEC_ID.encode("ascii")).digest()[:8], "little"
)
NORMAL_CODEBOOK = np.array(
    (
        -2.151945704536989,
        -1.343909278505003,
        -0.756005281205878,
        -0.245094178944222,
        0.245094178944222,
        0.756005281205878,
        1.343909278505002,
        2.151945704536991,
    ),
    dtype=np.float32,
)


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _fp32_digest(value: np.ndarray) -> str:
    canonical = np.asarray(value, dtype="<f4", order="C")
    return hashlib.sha256(canonical.tobytes(order="C")).hexdigest()


def _seeded_rotation(seed: int) -> np.ndarray:
    """Generate one Haar-style orthogonal transform with fixed QR orientation."""
    if type(seed) is not int or not 0 <= seed < 1 << 64:
        _invalid()
    generator = np.random.Generator(np.random.PCG64(seed))
    gaussian = generator.standard_normal((HEAD_WIDTH, HEAD_WIDTH))
    q, r = np.linalg.qr(gaussian)
    diagonal = np.diag(r)
    signs = np.where(diagonal < 0.0, -1.0, 1.0)
    # QR has a column-sign ambiguity. Multiplying each Q column by the sign of
    # the matching R diagonal gives one deterministic orientation.
    return np.asarray(q * signs[None, :], dtype=np.float32)


ROTATION = _seeded_rotation(ROTATION_SEED)
ROTATION_DIGEST = _fp32_digest(ROTATION)
CODEBOOK_DIGEST = _fp32_digest(NORMAL_CODEBOOK)
EXPECTED_ROTATION_DIGEST = "7876ebc965309065c0428efe03ced3104c7f29297e9b983e5fc89036f2e84baa"
EXPECTED_CODEBOOK_DIGEST = "77e11f5820649d05f2b184d2f155f9b1da5264cf2f0936f465ece0a8a56c6216"


@dataclass(frozen=True)
class Rot3Manifest:
    """Shared immutable constants referenced by cold-cache records."""

    codec_id: str = CODEC_ID
    head_width: int = HEAD_WIDTH
    code_bits: int = CODE_BITS
    rotation_seed: int = ROTATION_SEED
    rotation_digest: str = EXPECTED_ROTATION_DIGEST
    codebook_digest: str = EXPECTED_CODEBOOK_DIGEST

    def validate(self) -> None:
        if (
            self.codec_id != CODEC_ID
            or self.head_width != HEAD_WIDTH
            or self.code_bits != CODE_BITS
            or self.rotation_seed != ROTATION_SEED
            or self.rotation_digest != EXPECTED_ROTATION_DIGEST
            or self.codebook_digest != EXPECTED_CODEBOOK_DIGEST
            or ROTATION_DIGEST != EXPECTED_ROTATION_DIGEST
            or CODEBOOK_DIGEST != EXPECTED_CODEBOOK_DIGEST
        ):
            _invalid()


def codec_manifest() -> Rot3Manifest:
    """Return the exact constants that identify ``bamf.rot3/v1``."""
    manifest = Rot3Manifest()
    manifest.validate()
    return manifest


def pack_3bit(codes: np.ndarray) -> bytes:
    """Pack integer codes into an LSB-first little-endian bitstream."""
    values = np.asarray(codes)
    if values.ndim != 1 or not np.issubdtype(values.dtype, np.integer):
        _invalid()
    integers = values.astype(np.int64, copy=False)
    if np.any(integers < 0) or np.any(integers >= CODE_COUNT):
        _invalid()
    output = bytearray()
    accumulator = 0
    bit_count = 0
    for code in integers.tolist():
        accumulator |= int(code) << bit_count
        bit_count += CODE_BITS
        while bit_count >= 8:
            output.append(accumulator & 0xFF)
            accumulator >>= 8
            bit_count -= 8
    if bit_count:
        output.append(accumulator & 0xFF)
    return bytes(output)


def unpack_3bit(payload: bytes, count: int) -> np.ndarray:
    """Decode exactly ``count`` codes and reject truncated/noncanonical tails."""
    if type(payload) is not bytes or type(count) is not int or count < 0:
        _invalid()
    expected_bytes = (count * CODE_BITS + 7) // 8
    if len(payload) != expected_bytes:
        _invalid()
    output = np.empty((count,), dtype=np.uint8)
    accumulator = 0
    bit_count = 0
    offset = 0
    for index in range(count):
        while bit_count < CODE_BITS:
            accumulator |= payload[offset] << bit_count
            offset += 1
            bit_count += 8
        output[index] = accumulator & (CODE_COUNT - 1)
        accumulator >>= CODE_BITS
        bit_count -= CODE_BITS
    if accumulator != 0 or (bit_count and payload[-1] >> (8 - bit_count)):
        _invalid()
    return output


def quantize_directions(vectors: np.ndarray) -> np.ndarray:
    """Rotate unit directions, scale by sqrt(24), and emit nearest 3-bit codes."""
    values = np.asarray(vectors)
    if (
        values.ndim < 2
        or values.shape[-1] != HEAD_WIDTH
        or not np.issubdtype(values.dtype, np.floating)
        or not np.isfinite(values).all()
    ):
        _invalid()
    values = values.astype(np.float32, copy=False)
    norms = np.linalg.norm(values, axis=-1, keepdims=True)
    units = np.divide(values, norms, out=np.zeros_like(values), where=norms != 0)
    scaled = (units @ ROTATION) * np.float32(math.sqrt(HEAD_WIDTH))
    distances = np.abs(scaled[..., None] - NORMAL_CODEBOOK)
    return np.argmin(distances, axis=-1).astype(np.uint8)


def decode_directions(codes: np.ndarray) -> np.ndarray:
    """Reconstruct unit directions only; B14.2 restores stored vector norms."""
    values = np.asarray(codes)
    if (
        values.ndim < 2
        or values.shape[-1] != HEAD_WIDTH
        or not np.issubdtype(values.dtype, np.integer)
        or np.any(values < 0)
        or np.any(values >= CODE_COUNT)
    ):
        _invalid()
    rotated = NORMAL_CODEBOOK[values.astype(np.int64)] / np.float32(math.sqrt(HEAD_WIDTH))
    reconstructed = rotated @ ROTATION.T
    norms = np.linalg.norm(reconstructed, axis=-1, keepdims=True)
    return np.divide(
        reconstructed,
        norms,
        out=np.zeros_like(reconstructed, dtype=np.float32),
        where=norms != 0,
    ).astype(np.float32, copy=False)


from .atlas_cache_records import (  # noqa: E402
    BLOCK_VECTORS,
    CACHE_MODE_FP32,
    CACHE_MODE_ROT3,
    MIN_COMPRESSED_VECTORS,
    CacheArtifact,
    CacheBinding,
    decode_cache,
    encode_cold_cache,
)
