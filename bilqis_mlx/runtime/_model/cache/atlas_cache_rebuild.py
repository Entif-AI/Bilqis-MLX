"""Revoked-cache rejection and rebuild from qualified canonical FP32 state."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from .atlas_cache_binding import (
    CacheArtifact,
    CacheBinding,
    binding_digest,
    validate_binding,
)


def _new_eligibility_owner():
    issued = {}

    def require(receipt):
        entry = issued.get(id(receipt))
        if entry is None or entry is not receipt:
            _invalid()

    def issue(receipt):
        issued[id(receipt)] = receipt
        return receipt

    return require, issue


_eligibility_state, _issue_eligibility = _new_eligibility_owner()


@dataclass(frozen=True)
class CacheEligibilityReceipt:
    """Rights/source/context evidence authorizing one fresh derived rebuild."""

    binding_sha256: str
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
    _eligibility_state(receipt)
    expected = (
        binding_digest(binding).hex(),
        binding.source_release_sha256,
        binding.semantic_release_sha256,
        binding.source_rights_sha256,
        binding.rights_purpose_sha256,
        binding.policy_epoch_sha256,
        binding.context_eligibility_sha256,
    )
    actual = (
        receipt.binding_sha256,
        receipt.source_release_sha256,
        receipt.semantic_release_sha256,
        receipt.source_rights_sha256,
        receipt.rights_purpose_sha256,
        receipt.policy_epoch_sha256,
        receipt.context_eligibility_sha256,
    )
    if actual != expected:
        _invalid()


def issue_cache_eligibility(
    authority,
    binding: CacheBinding,
    *,
    pointer_path: Path,
    export_clearance,
    atlas_selection,
    source_frontier,
    export_artifact_digests,
    frames,
    task_scope,
    policy,
) -> CacheEligibilityReceipt:
    """Derive one rebuild permission from live B13, signed A12, and C09 context."""
    from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation_authority
    from bilqis_mlx.semantics.atlas_release_audit import (
        ExportClearanceReceipt, validate_export_clearance_context,
    )
    from bilqis_mlx.semantics.context_eligibility import (
        ApprovedContextProjection, ContextPolicy, SourceFrontier, TaskScope,
        project_context,
    )
    from bilqis_mlx.semantics.domains import contract_digest

    validate_binding(binding)
    if (not isinstance(pointer_path, Path)
            or type(export_clearance) is not ExportClearanceReceipt
            or type(source_frontier) is not SourceFrontier
            or type(task_scope) is not TaskScope
            or type(policy) is not ContextPolicy
            or type(frames) is not tuple
            or type(export_artifact_digests) is not tuple):
        _invalid()
    student, manifest_sha256 = load_bamf_generation_authority(pointer_path)
    authority._verify_detached(
        export_clearance.source_owner, export_clearance.dependency(),
        export_clearance.signature_hex, export_clearance.signing_bytes())
    clearance_sha256 = validate_export_clearance_context(
        export_clearance, atlas_selection, source_frontier,
        export_artifact_digests)
    projection = project_context(frames, task_scope, source_frontier, policy)
    if type(projection) is not ApprovedContextProjection:
        _invalid()
    compiler = student.compiler_features
    correction = student.correction_frontier
    if (student.provenance.release_digest != atlas_selection.release_sha256
            or compiler.get("rights_epoch") != source_frontier.rights_epoch
            or compiler.get("correction_generation")
               != source_frontier.correction_generation
            or correction.get("rights_epoch") != source_frontier.rights_epoch
            or correction.get("correction_generation")
               != source_frontier.correction_generation
            or policy.rights_epoch != source_frontier.rights_epoch
            or task_scope.semantic_release != atlas_selection.release_sha256):
        _invalid()
    purpose_sha256 = contract_digest({
        "purpose": task_scope.purpose,
        "jurisdiction": task_scope.jurisdiction,
        "scope": task_scope.scope,
    })
    policy_sha256 = contract_digest({
        "policy_id": policy.policy_id,
        "policy_epoch": policy.policy_epoch,
        "rights_epoch": policy.rights_epoch,
    })
    expected = {
        "generation_sha256": manifest_sha256,
        "topology_sha256": student.topology.digest,
        "source_release_sha256": atlas_selection.source_bundle_id,
        "semantic_release_sha256": atlas_selection.release_sha256,
        "source_rights_sha256": clearance_sha256,
        "rights_purpose_sha256": purpose_sha256,
        "policy_epoch_sha256": policy_sha256,
        "context_eligibility_sha256": projection.digest,
    }
    if any(getattr(binding, name) != value for name, value in expected.items()):
        _invalid()
    return _issue_eligibility(CacheEligibilityReceipt(
        binding_digest(binding).hex(),
        binding.source_release_sha256,
        binding.semantic_release_sha256,
        binding.source_rights_sha256,
        binding.rights_purpose_sha256,
        binding.policy_epoch_sha256,
        binding.context_eligibility_sha256,
        True,
    ))


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

    from .atlas_cache_records import _encode_cold_cache
    rebuilt = _encode_cold_cache(
        values,
        new_binding.codec_manifest,
        binding=new_binding,
        authority=authority,
    )
    if rebuilt.binding_sha256 != binding_digest(new_binding):
        _invalid()
    persist(rebuilt)
    return CacheRebuildResult(rebuilt, True)
