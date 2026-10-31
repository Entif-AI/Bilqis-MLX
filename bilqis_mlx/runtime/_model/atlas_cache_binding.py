"""Causal binding and literal byte accounting for BAMF derived caches."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .atlas_cache_codec import Rot3Manifest


DIGEST_HEX_CHARS = 64
BINDING_DIGEST_BYTES = 32
RECORD_HEADER_LIMIT = 64
RECORD_HEADER_MAGIC = b"B3C1"
MODE_FP32_BYTE = b"F"
MODE_ROT3_BYTE = b"R"
MAX_U32 = (1 << 32) - 1


@dataclass(frozen=True)
class CacheBinding:
    """All identities that can make a derived cache causally incompatible."""

    codec_manifest: Rot3Manifest
    generation_sha256: str
    lineage_sha256: str
    topology_sha256: str
    source_rights_sha256: str
    causal_prefix_sha256: str
    masks_sha256: str
    scope_sha256: str
    key_sha256: str
    offset: int


@dataclass(frozen=True)
class CacheArtifact:
    """One cold-cache record plus its composite causal-binding digest."""

    mode: str
    true_vectors: int
    padded_vectors: int
    head_width: int
    binding_sha256: bytes
    direction_codes: bytes
    relative_norms: bytes
    block_max_norms_fp32: bytes
    fp32_payload: bytes


@dataclass(frozen=True)
class CacheByteCost:
    header_bytes: int
    payload_bytes: int
    total_bytes: int
    effective_bits_per_channel: float


def _invalid() -> None:
    from .atlas_cache_codec import _invalid as codec_invalid
    codec_invalid()


def _sha256_hex(value: str) -> bool:
    if not isinstance(value, str) or len(value) != DIGEST_HEX_CHARS:
        return False
    try:
        bytes.fromhex(value)
    except ValueError:
        return False
    return True


def validate_binding(binding: CacheBinding, codec_manifest=None) -> None:
    from .atlas_cache_codec import Rot3Manifest
    if not isinstance(binding, CacheBinding):
        _invalid()
    manifest = binding.codec_manifest
    if not isinstance(manifest, Rot3Manifest):
        _invalid()
    manifest.validate()
    if codec_manifest is not None and manifest != codec_manifest:
        _invalid()
    if any(not _sha256_hex(value) for value in (
        binding.generation_sha256,
        binding.lineage_sha256,
        binding.topology_sha256,
        binding.source_rights_sha256,
        binding.causal_prefix_sha256,
        binding.masks_sha256,
        binding.scope_sha256,
        binding.key_sha256,
    )):
        _invalid()
    if type(binding.offset) is not int or not 0 <= binding.offset <= MAX_U32:
        _invalid()


def binding_digest(binding: CacheBinding) -> bytes:
    """Digest the full typed binding plus exact out-of-band codec identity."""
    validate_binding(binding)
    manifest = binding.codec_manifest
    payload = {
        "causal_prefix_sha256": binding.causal_prefix_sha256,
        "codec": {
            "code_bits": manifest.code_bits,
            "codebook_digest": manifest.codebook_digest,
            "codec_id": manifest.codec_id,
            "head_width": manifest.head_width,
            "rotation_digest": manifest.rotation_digest,
            "rotation_seed": manifest.rotation_seed,
        },
        "generation_sha256": binding.generation_sha256,
        "key_sha256": binding.key_sha256,
        "lineage_sha256": binding.lineage_sha256,
        "masks_sha256": binding.masks_sha256,
        "offset": binding.offset,
        "scope_sha256": binding.scope_sha256,
        "source_rights_sha256": binding.source_rights_sha256,
        "topology_sha256": binding.topology_sha256,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(canonical).digest()


def record_header_bytes(artifact: CacheArtifact) -> bytes:
    if not isinstance(artifact, CacheArtifact):
        _invalid()
    if type(artifact.binding_sha256) is not bytes or (
        len(artifact.binding_sha256) != BINDING_DIGEST_BYTES
    ):
        _invalid()
    if not 0 < artifact.true_vectors <= artifact.padded_vectors <= MAX_U32:
        _invalid()
    if artifact.mode == "FP32":
        mode = MODE_FP32_BYTE
    elif artifact.mode == "ROT3":
        mode = MODE_ROT3_BYTE
    else:
        _invalid()
    header = (
        RECORD_HEADER_MAGIC
        + mode
        + artifact.binding_sha256
        + struct.pack("<II", artifact.true_vectors, artifact.padded_vectors)
    )
    if len(header) > RECORD_HEADER_LIMIT:
        _invalid()
    return header


def cache_byte_cost(artifact: CacheArtifact) -> CacheByteCost:
    header_bytes = len(record_header_bytes(artifact))
    payload_bytes = sum(len(payload) for payload in (
        artifact.direction_codes,
        artifact.relative_norms,
        artifact.block_max_norms_fp32,
        artifact.fp32_payload,
    ))
    channels = artifact.true_vectors * artifact.head_width
    if channels <= 0:
        _invalid()
    total = header_bytes + payload_bytes
    bits = total * 8 / channels
    if not math.isfinite(bits):
        _invalid()
    return CacheByteCost(header_bytes, payload_bytes, total, bits)


def require_cache_binding(artifact: CacheArtifact, binding: CacheBinding) -> None:
    """Reject stale rights/generation/prefix/mask/scope state before decode."""
    validate_binding(binding)
    if artifact.binding_sha256 != binding_digest(binding):
        _invalid()
