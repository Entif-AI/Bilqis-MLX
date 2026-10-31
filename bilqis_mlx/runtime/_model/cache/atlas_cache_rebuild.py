"""Revoked-cache rejection and rebuild from qualified canonical FP32 state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from .atlas_cache_binding import (
    CacheArtifact,
    CacheBinding,
    binding_digest,
    validate_binding,
)


@dataclass(frozen=True)
class CacheEligibilityReceipt:
    """Rights/source/context evidence authorizing one fresh derived rebuild."""

    source_release_sha256: str
    semantic_release_sha256: str
    source_rights_sha256: str
    rights_purpose_sha256: str
    policy_epoch_sha256: str
    context_eligibility_sha256: str
    eligible: bool


@dataclass(frozen=True)
class CacheRebuildResult:
    artifact: CacheArtifact
    persisted: bool


def _invalid() -> None:
    from .atlas_cache_codec import _invalid as codec_invalid
    codec_invalid()


def validate_eligibility(
    receipt: CacheEligibilityReceipt, binding: CacheBinding,
) -> None:
    validate_binding(binding)
    if not isinstance(receipt, CacheEligibilityReceipt) or receipt.eligible is not True:
        _invalid()
    expected = (
        binding.source_release_sha256,
        binding.semantic_release_sha256,
        binding.source_rights_sha256,
        binding.rights_purpose_sha256,
        binding.policy_epoch_sha256,
        binding.context_eligibility_sha256,
    )
    actual = (
        receipt.source_release_sha256,
        receipt.semantic_release_sha256,
        receipt.source_rights_sha256,
        receipt.rights_purpose_sha256,
        receipt.policy_epoch_sha256,
        receipt.context_eligibility_sha256,
    )
    if actual != expected:
        _invalid()


def rebuild_revoked_cache(
    stale_artifact: CacheArtifact,
    new_binding: CacheBinding,
    *,
    eligibility_receipt: CacheEligibilityReceipt,
    canonical_fp32_source: Callable[[], np.ndarray],
    persist: Callable[[CacheArtifact], None],
) -> CacheRebuildResult:
    """Build a new derived artifact without decoding or relabeling stale bytes."""
    if not isinstance(stale_artifact, CacheArtifact):
        _invalid()
    validate_eligibility(eligibility_receipt, new_binding)
    if stale_artifact.binding_sha256 == binding_digest(new_binding):
        _invalid()
    if not callable(canonical_fp32_source) or not callable(persist):
        _invalid()
    values = canonical_fp32_source()
    if not isinstance(values, np.ndarray):
        _invalid()
    if values.dtype != np.dtype(np.float32) or not np.isfinite(values).all():
        _invalid()

    from .atlas_cache_records import encode_cold_cache
    rebuilt = encode_cold_cache(
        values, new_binding.codec_manifest, binding=new_binding,
    )
    if rebuilt.binding_sha256 != binding_digest(new_binding):
        _invalid()
    persist(rebuilt)
    return CacheRebuildResult(rebuilt, True)
