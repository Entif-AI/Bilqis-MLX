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
CACHE_MODE_FP32 = "FP32"
CACHE_MODE_ROT3 = "ROT3"
MAX_EFFECTIVE_BITS = 3.5


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
    header_bytes: bytes | None = None

    def __post_init__(self) -> None:
        if self.header_bytes is None:
            object.__setattr__(self, "header_bytes", record_header_bytes(self))


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
        if len(bytes.fromhex(value)) != BINDING_DIGEST_BYTES:
            return False
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
    from .atlas_cache_codec import HEAD_WIDTH
    if not isinstance(artifact, CacheArtifact):
        _invalid()
    if type(artifact.binding_sha256) is not bytes or (
        len(artifact.binding_sha256) != BINDING_DIGEST_BYTES
    ):
        _invalid()
    if (type(artifact.true_vectors) is not int
        or type(artifact.padded_vectors) is not int
        or type(artifact.head_width) is not int or artifact.head_width != HEAD_WIDTH
        or not 0 < artifact.true_vectors <= artifact.padded_vectors <= MAX_U32):
        _invalid()
    if artifact.mode == CACHE_MODE_FP32:
        mode = MODE_FP32_BYTE
    elif artifact.mode == CACHE_MODE_ROT3:
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
    if (not isinstance(artifact, CacheArtifact)
        or type(artifact.header_bytes) is not bytes
        or artifact.header_bytes != record_header_bytes(artifact)
        or not all(type(p) is bytes for p in (
            artifact.direction_codes, artifact.relative_norms,
            artifact.block_max_norms_fp32, artifact.fp32_payload))):
        _invalid()
    header_bytes = len(artifact.header_bytes)
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
    if not isinstance(artifact, CacheArtifact):
        _invalid()
    validate_binding(binding)
    if (type(artifact.header_bytes) is not bytes
        or artifact.header_bytes != record_header_bytes(artifact)):
        _invalid()
    if artifact.binding_sha256 != binding_digest(binding):
        _invalid()
