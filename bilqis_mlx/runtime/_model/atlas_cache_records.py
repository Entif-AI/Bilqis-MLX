"""Norm blocks and small-record fallback for the BAMF rot3/v1 cache."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .atlas_cache_codec import Rot3Manifest


BLOCK_VECTORS = 32
MIN_COMPRESSED_VECTORS = 256
VECTOR_DIMS = 2
CACHE_MODE_FP32 = "FP32"
CACHE_MODE_ROT3 = "ROT3"


@dataclass(frozen=True)
class CacheBinding:
    """B14.2 codec identity; B14.3 extends causal binding authority."""

    codec_manifest: Rot3Manifest


@dataclass(frozen=True)
class CacheArtifact:
    """One cold-cache record encoded either exactly or with rot3/v1."""

    mode: str
    true_vectors: int
    padded_vectors: int
    head_width: int
    direction_codes: bytes
    relative_norms: bytes
    block_max_norms_fp32: bytes
    fp32_payload: bytes


def _codec():
    from . import atlas_cache_codec
    return atlas_cache_codec


def _invalid() -> None:
    _codec()._invalid()


def _vectors(cache, head_width: int) -> np.ndarray:
    values = np.asarray(cache)
    if (
        values.ndim != VECTOR_DIMS
        or values.shape[0] <= 0
        or values.shape[1] != head_width
        or not np.issubdtype(values.dtype, np.floating)
        or not np.isfinite(values).all()
    ):
        _invalid()
    return values.astype(np.float32, copy=False)


def _validate_manifest(manifest: Rot3Manifest) -> None:
    codec = _codec()
    if not isinstance(manifest, codec.Rot3Manifest):
        _invalid()
    manifest.validate()


def encode_cold_cache(cache, codec_manifest: Rot3Manifest) -> CacheArtifact:
    """Encode one [vectors,24] cold record under the B14.2 size policy."""
    _validate_manifest(codec_manifest)
    codec = _codec()
    values = _vectors(cache, codec.HEAD_WIDTH)
    true_vectors = int(values.shape[0])
    if true_vectors < MIN_COMPRESSED_VECTORS:
        return CacheArtifact(
            CACHE_MODE_FP32,
            true_vectors,
            true_vectors,
            codec.HEAD_WIDTH,
            b"",
            b"",
            b"",
            np.asarray(values, dtype="<f4", order="C").tobytes(order="C"),
        )

    padded_vectors = (
        (true_vectors + BLOCK_VECTORS - 1) // BLOCK_VECTORS * BLOCK_VECTORS
    )
    padded = np.zeros((padded_vectors, codec.HEAD_WIDTH), dtype=np.float32)
    padded[:true_vectors] = values
    norms = np.linalg.norm(padded, axis=-1).astype(np.float32, copy=False)
    blocks = norms.reshape(-1, BLOCK_VECTORS)
    maxima = np.max(blocks, axis=1).astype(np.float32, copy=False)
    relative = np.zeros_like(blocks, dtype=np.uint8)
    nonzero = maxima > 0
    if np.any(nonzero):
        scaled = (
            blocks[nonzero]
            / maxima[nonzero, None]
            * np.float32(np.iinfo(np.uint8).max)
        )
        relative[nonzero] = np.rint(scaled).astype(np.uint8)

    codes = codec.quantize_directions(padded).reshape(-1)
    return CacheArtifact(
        CACHE_MODE_ROT3,
        true_vectors,
        padded_vectors,
        codec.HEAD_WIDTH,
        codec.pack_3bit(codes),
        relative.reshape(-1).tobytes(order="C"),
        np.asarray(maxima, dtype="<f4", order="C").tobytes(order="C"),
        b"",
    )


def _validate_artifact(artifact: CacheArtifact, binding: CacheBinding) -> None:
    if not isinstance(artifact, CacheArtifact) or not isinstance(binding, CacheBinding):
        _invalid()
    _validate_manifest(binding.codec_manifest)
    codec = _codec()
    if (
        type(artifact.true_vectors) is not int
        or type(artifact.padded_vectors) is not int
        or artifact.true_vectors <= 0
        or artifact.head_width != codec.HEAD_WIDTH
        or not all(
            type(payload) is bytes
            for payload in (
                artifact.direction_codes,
                artifact.relative_norms,
                artifact.block_max_norms_fp32,
                artifact.fp32_payload,
            )
        )
    ):
        _invalid()


def decode_cache(artifact: CacheArtifact, expected_binding: CacheBinding) -> np.ndarray:
    """Decode B14.2 record bytes and restore the stored vector norm."""
    _validate_artifact(artifact, expected_binding)
    codec = _codec()
    if artifact.mode == CACHE_MODE_FP32:
        if (
            artifact.padded_vectors != artifact.true_vectors
            or artifact.true_vectors >= MIN_COMPRESSED_VECTORS
            or artifact.direction_codes
            or artifact.relative_norms
            or artifact.block_max_norms_fp32
            or len(artifact.fp32_payload)
            != artifact.true_vectors * codec.HEAD_WIDTH * np.dtype("<f4").itemsize
        ):
            _invalid()
        decoded = (
            np.frombuffer(artifact.fp32_payload, dtype="<f4")
            .reshape(artifact.true_vectors, codec.HEAD_WIDTH)
            .astype(np.float32, copy=True)
        )
        if not np.isfinite(decoded).all():
            _invalid()
        return decoded

    if artifact.mode != CACHE_MODE_ROT3:
        _invalid()
    if (
        artifact.true_vectors < MIN_COMPRESSED_VECTORS
        or artifact.padded_vectors < artifact.true_vectors
        or artifact.padded_vectors % BLOCK_VECTORS
        or artifact.padded_vectors - artifact.true_vectors >= BLOCK_VECTORS
        or artifact.fp32_payload
    ):
        _invalid()
    blocks = artifact.padded_vectors // BLOCK_VECTORS
    code_count = artifact.padded_vectors * codec.HEAD_WIDTH
    expected_code_bytes = (code_count * 3 + 7) // 8
    if (
        len(artifact.direction_codes) != expected_code_bytes
        or len(artifact.relative_norms) != artifact.padded_vectors
        or len(artifact.block_max_norms_fp32)
        != blocks * np.dtype("<f4").itemsize
    ):
        _invalid()

    maxima = np.frombuffer(artifact.block_max_norms_fp32, dtype="<f4")
    if not np.isfinite(maxima).all() or np.any(maxima < 0):
        _invalid()
    relative = np.frombuffer(artifact.relative_norms, dtype=np.uint8).reshape(
        blocks, BLOCK_VECTORS
    )
    zero_blocks = maxima == 0
    if np.any(relative[zero_blocks]):
        _invalid()
    if np.any(~zero_blocks) and np.any(
        np.max(relative[~zero_blocks], axis=1) != np.iinfo(np.uint8).max
    ):
        _invalid()
    flat_relative = relative.reshape(-1)
    if np.any(flat_relative[artifact.true_vectors:]):
        _invalid()
    norms = (
        relative.astype(np.float32)
        * maxima[:, None]
        / np.float32(np.iinfo(np.uint8).max)
    ).reshape(-1, 1)
    codes = codec.unpack_3bit(artifact.direction_codes, code_count).reshape(
        artifact.padded_vectors, codec.HEAD_WIDTH
    )
    tail_count = artifact.padded_vectors - artifact.true_vectors
    if tail_count:
        canonical_tail = codec.quantize_directions(
            np.zeros((tail_count, codec.HEAD_WIDTH), dtype=np.float32)
        )
        if not np.array_equal(codes[artifact.true_vectors:], canonical_tail):
            _invalid()
    directions = codec.decode_directions(codes)
    decoded = directions * norms
    return decoded[:artifact.true_vectors].astype(np.float32, copy=False)
