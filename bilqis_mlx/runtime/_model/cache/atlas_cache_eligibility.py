"""Owner-derived eligibility for one fresh BAMF derived-cache rebuild."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .atlas_cache_binding import CacheBinding, binding_digest, validate_binding


@dataclass(frozen=True)
class CacheEligibilityInputs:
    """Current authority inputs supplied by the cache capability owner."""

    pointer_path: Path
    export_clearance: object
    atlas_selection: object
    source_frontier: object
    export_artifact_digests: tuple[str, ...]
    frames: tuple
    task_scope: object
    policy: object
    canonical_fp32_source: object


@dataclass(frozen=True)
class CacheEligibilityReceipt:
    """Opaque one-use permission for one exact, currently eligible binding."""

    binding_sha256: str
    source_release_sha256: str
    semantic_release_sha256: str
    source_rights_sha256: str
    rights_purpose_sha256: str
    policy_epoch_sha256: str
    context_eligibility_sha256: str
    eligible: bool


@dataclass(frozen=True)
class _AuthoritativeCacheIdentity:
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


@dataclass(frozen=True)
class _CausalCacheIdentity:
    causal_prefix_sha256: str
    masks_sha256: str
    scope_sha256: str
    key_sha256: str
    offset: int


@dataclass(frozen=True)
class _IssuedEligibility:
    receipt: CacheEligibilityReceipt
    authority: object
    identity: _AuthoritativeCacheIdentity


def _invalid() -> None:
    from .atlas_cache_codec import _invalid as codec_invalid
    codec_invalid()


def _require_inputs(inputs) -> CacheEligibilityInputs:
    from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
    from bilqis_mlx.semantics.atlas_release_audit import ExportClearanceReceipt
    from bilqis_mlx.semantics.context_eligibility import (
        ContextPolicy, SourceFrontier, TaskScope,
    )
    if (type(inputs) is not CacheEligibilityInputs
            or not isinstance(inputs.pointer_path, Path)
            or type(inputs.export_clearance) is not ExportClearanceReceipt
            or type(inputs.atlas_selection) is not AtlasArtifactSelection
            or type(inputs.source_frontier) is not SourceFrontier
            or type(inputs.task_scope) is not TaskScope
            or type(inputs.policy) is not ContextPolicy
            or type(inputs.frames) is not tuple
            or type(inputs.export_artifact_digests) is not tuple
            or not callable(inputs.canonical_fp32_source)):
        _invalid()
    return inputs


def _canonical_fp32_values(authority, binding: CacheBinding):
    """Recompute cache values through the authority owner's current source."""
    production = authority._current_canonical_fp32(binding)
    if production is not None:
        return production
    inputs = authority._current_eligibility_inputs()
    source = getattr(inputs, "canonical_fp32_source", None)
    if not callable(source):
        _invalid()
    return source(binding)


def _source_context_identity(authority, student, inputs) -> tuple[str, str, str, str]:
    from bilqis_mlx.semantics.context_eligibility import ApprovedContextProjection, project_context
    from bilqis_mlx.semantics.domains import contract_digest

    clearance = inputs.export_clearance
    frontier = inputs.source_frontier
    selection = inputs.atlas_selection
    task = inputs.task_scope
    policy = inputs.policy
    clearance_sha256 = authority._validate_export_clearance_context(
        clearance, selection, frontier, inputs.export_artifact_digests)
    projection = project_context(inputs.frames, task, frontier, policy)
    if type(projection) is not ApprovedContextProjection:
        _invalid()
    compiler = student.compiler_features
    correction = student.correction_frontier
    if (student.provenance.release_digest != selection.release_sha256
            or compiler.get("rights_epoch") != frontier.rights_epoch
            or compiler.get("correction_generation") != frontier.correction_generation
            or correction.get("rights_epoch") != frontier.rights_epoch
            or correction.get("correction_generation") != frontier.correction_generation
            or policy.rights_epoch != frontier.rights_epoch
            or task.semantic_release != selection.release_sha256):
        _invalid()
    purpose_sha256 = contract_digest({
        "purpose": task.purpose, "jurisdiction": task.jurisdiction,
        "scope": task.scope})
    policy_sha256 = contract_digest({
        "policy_id": policy.policy_id, "policy_epoch": policy.policy_epoch,
        "rights_epoch": policy.rights_epoch})
    return clearance_sha256, projection.digest, purpose_sha256, policy_sha256


def _current_identity(
    authority, binding: CacheBinding, causal: _CausalCacheIdentity,
) -> _AuthoritativeCacheIdentity:
    from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation_authority
    from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
    from bilqis_mlx.semantics.domains import contract_digest

    validate_binding(binding)
    inputs = _require_inputs(authority._current_eligibility_inputs())
    student, manifest_sha256 = load_bamf_generation_authority(inputs.pointer_path)
    clearance, context, purpose, policy = _source_context_identity(
        authority, student, inputs)
    lineage = contract_digest({
        "schema": "bilqis.mlx.bamf-cache-lineage/v1",
        "run_id": student.run_id,
    })
    inference = execution_generation_digest(
        student.retained_state.optimizer.parameters,
        spec=student.topology,
        extents=student.extents,
    )
    return _AuthoritativeCacheIdentity(
        manifest_sha256, lineage, student.topology.digest,
        inputs.atlas_selection.source_bundle_id,
        inputs.atlas_selection.release_sha256,
        clearance, purpose, policy, context,
        causal.causal_prefix_sha256, causal.masks_sha256,
        causal.scope_sha256, causal.key_sha256,
        inference, causal.offset,
    )


def _authoritative_identity(authority, binding: CacheBinding) -> _AuthoritativeCacheIdentity:
    validate_binding(binding)
    production = authority._current_production_identity(binding)
    if production is not None:
        if any(getattr(binding, name) != getattr(production, name)
               for name in production.__dataclass_fields__):
            _invalid()
        return production
    causal = authority._current_causal_identity(binding)
    if causal is None:
        # Test-only isolated owners have no production B13 bridge.  Their binding
        # remains the explicit fixture currentness source; production authorities
        # always supply an owner-derived causal identity above.
        causal = _CausalCacheIdentity(
            binding.causal_prefix_sha256,
            binding.masks_sha256,
            binding.scope_sha256,
            binding.key_sha256,
            binding.offset,
        )
    identity = _current_identity(authority, binding, causal)
    if any(getattr(binding, name) != getattr(identity, name)
           for name in identity.__dataclass_fields__):
        _invalid()
    return identity


def binding_from_identity(
    codec_manifest,
    identity: _AuthoritativeCacheIdentity,
    artifact_authority_id: str,
    artifact_authority_public_key_hex: str,
) -> CacheBinding:
    if type(identity) is not _AuthoritativeCacheIdentity:
        _invalid()
    binding = CacheBinding(
        codec_manifest,
        identity.generation_sha256,
        identity.lineage_sha256,
        identity.topology_sha256,
        identity.source_release_sha256,
        identity.semantic_release_sha256,
        identity.source_rights_sha256,
        identity.rights_purpose_sha256,
        identity.policy_epoch_sha256,
        identity.context_eligibility_sha256,
        identity.causal_prefix_sha256,
        identity.masks_sha256,
        identity.scope_sha256,
        identity.key_sha256,
        identity.inference_state_sha256,
        identity.offset,
        artifact_authority_id,
        artifact_authority_public_key_hex,
    )
    validate_binding(binding, codec_manifest)
    return binding


def derive_current_binding(
    authority,
    codec_manifest,
    causal: _CausalCacheIdentity,
    artifact_authority_id: str,
    artifact_authority_public_key_hex: str,
) -> CacheBinding:
    """Build one complete binding from owner-derived current and causal state."""
    if type(causal) is not _CausalCacheIdentity:
        _invalid()
    provisional = CacheBinding(
        codec_manifest,
        "0" * 64, "0" * 64, "0" * 64, "0" * 64, "0" * 64,
        "0" * 64, "0" * 64, "0" * 64, "0" * 64,
        causal.causal_prefix_sha256, causal.masks_sha256,
        causal.scope_sha256, causal.key_sha256, "0" * 64, causal.offset,
        artifact_authority_id, artifact_authority_public_key_hex,
    )
    identity = _current_identity(authority, provisional, causal)
    return binding_from_identity(
        codec_manifest, identity,
        artifact_authority_id, artifact_authority_public_key_hex)


def validate_current_binding(authority, binding: CacheBinding) -> None:
    """Require one cache binding to equal the owner's current authority state."""
    _authoritative_identity(authority, binding)


def _new_eligibility_boundary(authoritative_identity):
    """Return an isolated receipt owner; separate factories cannot register here."""
    issued = {}

    def issue(authority, binding: CacheBinding) -> CacheEligibilityReceipt:
        snapshot = authoritative_identity(authority, binding)
        receipt = CacheEligibilityReceipt(
            binding_digest(binding).hex(),
            binding.source_release_sha256,
            binding.semantic_release_sha256,
            binding.source_rights_sha256,
            binding.rights_purpose_sha256,
            binding.policy_epoch_sha256,
            binding.context_eligibility_sha256,
            True,
        )
        issued[id(receipt)] = _IssuedEligibility(receipt, authority, snapshot)
        return receipt

    def validate(authority, receipt: CacheEligibilityReceipt, binding: CacheBinding) -> None:
        validate_binding(binding)
        if not isinstance(receipt, CacheEligibilityReceipt) or receipt.eligible is not True:
            _invalid()
        entry = issued.get(id(receipt))
        if (entry is None or entry.receipt is not receipt
                or entry.authority is not authority):
            _invalid()
        current = authoritative_identity(authority, binding)
        if current != entry.identity:
            _invalid()
        expected = (
            binding_digest(binding).hex(), binding.source_release_sha256,
            binding.semantic_release_sha256, binding.source_rights_sha256,
            binding.rights_purpose_sha256, binding.policy_epoch_sha256,
            binding.context_eligibility_sha256,
        )
        actual = (
            receipt.binding_sha256, receipt.source_release_sha256,
            receipt.semantic_release_sha256, receipt.source_rights_sha256,
            receipt.rights_purpose_sha256, receipt.policy_epoch_sha256,
            receipt.context_eligibility_sha256,
        )
        if actual != expected:
            _invalid()

    def consume(authority, receipt: CacheEligibilityReceipt, binding: CacheBinding) -> None:
        validate(authority, receipt, binding)
        del issued[id(receipt)]

    return issue, validate, consume


issue_cache_eligibility, validate_eligibility, consume_eligibility = (
    _new_eligibility_boundary(_authoritative_identity)
)
