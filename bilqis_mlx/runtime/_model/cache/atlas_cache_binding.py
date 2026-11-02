"""Causal binding and literal byte accounting for BAMF derived caches."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import struct
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .atlas_revalidation import SourceAuthorityRegistry
from ..semantics.cognitive_dependencies import DependencyKind, DependencyRef

if TYPE_CHECKING:
    from .atlas_cache_codec import Rot3Manifest


DIGEST_HEX_CHARS = 64
BINDING_DIGEST_BYTES = 32
PAYLOAD_BINDING_TAG_BYTES = 16
ED25519_SIGNATURE_BYTES = 64
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
    source_release_sha256: str
    semantic_release_sha256: str
    source_rights_sha256: str
    rights_purpose_sha256: str
    policy_epoch_sha256: str
    context_eligibility_sha256: str
    causal_prefix_sha256: str
    masks_sha256: str
    scope_sha256: str
    key_sha256: str
    inference_state_sha256: str
    offset: int
    artifact_authority_id: str
    artifact_authority_public_key_hex: str


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
    payload_binding_tag: bytes | None = None
    header_bytes: bytes | None = None
    authority_signature: bytes | None = None

    def __post_init__(self) -> None:
        if type(self.payload_binding_tag) is not bytes or (
            len(self.payload_binding_tag) != PAYLOAD_BINDING_TAG_BYTES
        ):
            _invalid()
        if self.header_bytes is None:
            object.__setattr__(self, "header_bytes", record_header_bytes(self))
        if self.authority_signature is not None and (
            type(self.authority_signature) is not bytes
            or len(self.authority_signature) != ED25519_SIGNATURE_BYTES
        ):
            _invalid()


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
        binding.source_release_sha256,
        binding.semantic_release_sha256,
        binding.source_rights_sha256,
        binding.rights_purpose_sha256,
        binding.policy_epoch_sha256,
        binding.context_eligibility_sha256,
        binding.causal_prefix_sha256,
        binding.masks_sha256,
        binding.scope_sha256,
        binding.key_sha256,
        binding.inference_state_sha256,
    )):
        _invalid()
    if type(binding.offset) is not int or not 0 <= binding.offset <= MAX_U32:
        _invalid()
    if (not isinstance(binding.artifact_authority_id, str)
            or not binding.artifact_authority_id):
        _invalid()
    if not _sha256_hex(binding.artifact_authority_public_key_hex):
        _invalid()
    try:
        Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(binding.artifact_authority_public_key_hex)
        )
    except ValueError:
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
        "artifact_authority_id": binding.artifact_authority_id,
        "artifact_authority_public_key_hex": binding.artifact_authority_public_key_hex,
        "inference_state_sha256": binding.inference_state_sha256,
        "key_sha256": binding.key_sha256,
        "lineage_sha256": binding.lineage_sha256,
        "masks_sha256": binding.masks_sha256,
        "offset": binding.offset,
        "policy_epoch_sha256": binding.policy_epoch_sha256,
        "rights_purpose_sha256": binding.rights_purpose_sha256,
        "scope_sha256": binding.scope_sha256,
        "semantic_release_sha256": binding.semantic_release_sha256,
        "source_release_sha256": binding.source_release_sha256,
        "source_rights_sha256": binding.source_rights_sha256,
        "context_eligibility_sha256": binding.context_eligibility_sha256,
        "topology_sha256": binding.topology_sha256,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(canonical).digest()



def payload_binding_tag_fields(
    mode: str,
    true_vectors: int,
    padded_vectors: int,
    head_width: int,
    binding_sha256: bytes,
    direction_codes: bytes,
    relative_norms: bytes,
    block_max_norms_fp32: bytes,
    fp32_payload: bytes,
) -> bytes:
    """Mint the compact payload/authority integrity tag used in the record header."""
    if type(binding_sha256) is not bytes or len(binding_sha256) != BINDING_DIGEST_BYTES:
        _invalid()
    payloads = (
        direction_codes, relative_norms, block_max_norms_fp32, fp32_payload,
    )
    if not all(type(payload) is bytes for payload in payloads):
        _invalid()
    if mode == CACHE_MODE_FP32:
        mode_byte = MODE_FP32_BYTE
    elif mode == CACHE_MODE_ROT3:
        mode_byte = MODE_ROT3_BYTE
    else:
        _invalid()
    if (type(true_vectors) is not int
            or type(padded_vectors) is not int
            or type(head_width) is not int):
        _invalid()
    digest = hashlib.sha256()
    digest.update(b"bamf-cache-payload-binding-v1\0")
    digest.update(binding_sha256)
    digest.update(mode_byte)
    digest.update(struct.pack("<III", true_vectors, padded_vectors, head_width))
    for payload in payloads:
        digest.update(struct.pack("<Q", len(payload)))
        digest.update(payload)
    return digest.digest()[:PAYLOAD_BINDING_TAG_BYTES]


def payload_binding_tag(artifact: CacheArtifact) -> bytes:
    """Recompute the stored payload/authority tag without trusting its header."""
    if not isinstance(artifact, CacheArtifact):
        _invalid()
    return payload_binding_tag_fields(
        artifact.mode,
        artifact.true_vectors,
        artifact.padded_vectors,
        artifact.head_width,
        artifact.binding_sha256,
        artifact.direction_codes,
        artifact.relative_norms,
        artifact.block_max_norms_fp32,
        artifact.fp32_payload,
    )

def cache_artifact_signing_bytes(artifact: CacheArtifact) -> bytes:
    """Canonical detached-signature subject for one exact derived record."""
    if not isinstance(artifact, CacheArtifact):
        _invalid()
    if (type(artifact.header_bytes) is not bytes
            or artifact.header_bytes != record_header_bytes(artifact)
            or artifact.payload_binding_tag != payload_binding_tag(artifact)):
        _invalid()
    digest = hashlib.sha256()
    digest.update(b"bamf-cache-artifact-authority-v1\0")
    digest.update(artifact.header_bytes)
    for payload in (
        artifact.direction_codes,
        artifact.relative_norms,
        artifact.block_max_norms_fp32,
        artifact.fp32_payload,
    ):
        digest.update(struct.pack("<Q", len(payload)))
        digest.update(payload)
    return digest.digest()


def record_header_bytes(artifact: CacheArtifact) -> bytes:
    from .atlas_cache_codec import HEAD_WIDTH
    if not isinstance(artifact, CacheArtifact):
        _invalid()
    if type(artifact.binding_sha256) is not bytes or (
        len(artifact.binding_sha256) != BINDING_DIGEST_BYTES
    ):
        _invalid()
    if type(artifact.payload_binding_tag) is not bytes or (
        len(artifact.payload_binding_tag) != PAYLOAD_BINDING_TAG_BYTES
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
        + artifact.payload_binding_tag
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


def require_cache_binding(
    artifact: CacheArtifact,
    binding: CacheBinding,
    authority_registry: SourceAuthorityRegistry,
) -> None:
    """Reject stale rights/generation/prefix/mask/scope state before decode."""
    if not isinstance(artifact, CacheArtifact):
        _invalid()
    if not isinstance(authority_registry, SourceAuthorityRegistry):
        _invalid()
    validate_binding(binding)
    if (type(artifact.header_bytes) is not bytes
        or artifact.header_bytes != record_header_bytes(artifact)):
        _invalid()
    if artifact.binding_sha256 != binding_digest(binding):
        _invalid()
    if artifact.payload_binding_tag != payload_binding_tag(artifact):
        _invalid()
    if (type(artifact.authority_signature) is not bytes
            or len(artifact.authority_signature) != ED25519_SIGNATURE_BYTES):
        _invalid()
    authority_registry.verify_detached(
        binding.artifact_authority_id,
        DependencyRef(DependencyKind.ARTIFACT, f"cache:{binding.key_sha256}"),
        artifact.authority_signature.hex(),
        cache_artifact_signing_bytes(artifact),
        binding.artifact_authority_public_key_hex,
    )
