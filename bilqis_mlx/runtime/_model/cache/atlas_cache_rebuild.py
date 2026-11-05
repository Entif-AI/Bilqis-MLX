"""Revoked-cache rejection and rebuild from qualified canonical FP32 state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from .atlas_cache_binding import CacheArtifact, CacheBinding, binding_digest
from .atlas_cache_eligibility import (
    CacheEligibilityReceipt,
    consume_eligibility,
    issue_cache_eligibility,
    validate_eligibility,
)


@dataclass(frozen=True)
class CacheRebuildResult:
    artifact: CacheArtifact
    persisted: bool


def _invalid() -> None:
    from .atlas_cache_codec import _invalid as codec_invalid
    codec_invalid()


def _rebuild_revoked_cache(
    stale_artifact: CacheArtifact,
    new_binding: CacheBinding,
    *,
    eligibility_receipt: CacheEligibilityReceipt,
    canonical_fp32_source: Callable[[], np.ndarray],
    persist: Callable[[CacheArtifact], None],
    authority,
) -> CacheRebuildResult:
    """Build a new derived artifact without decoding or relabeling stale bytes."""
    if not isinstance(stale_artifact, CacheArtifact):
        _invalid()
    validate_eligibility(authority, eligibility_receipt, new_binding)
    if stale_artifact.binding_sha256 == binding_digest(new_binding):
        _invalid()
    if not callable(canonical_fp32_source) or not callable(persist):
        _invalid()
    values = canonical_fp32_source()
    if not isinstance(values, np.ndarray):
        _invalid()
    if values.dtype != np.dtype(np.float32) or not np.isfinite(values).all():
        _invalid()

    from .atlas_cache_records import _encode_cold_cache
    rebuilt = _encode_cold_cache(
        values,
        new_binding.codec_manifest,
        binding=new_binding,
        authority=authority,
    )
    if rebuilt.binding_sha256 != binding_digest(new_binding):
        _invalid()
    consume_eligibility(authority, eligibility_receipt, new_binding)
    persist(rebuilt)
    return CacheRebuildResult(rebuilt, True)
