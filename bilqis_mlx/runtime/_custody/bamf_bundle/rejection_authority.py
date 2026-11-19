"""Portable owner-authenticated authority for rejected BAMF candidates."""
from __future__ import annotations

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_source_authority import SourceAuthorityRegistry
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef

from .records import canonical, invalid, sha


PORTABLE_REJECTION_AUTHORITY_SCHEMA = "bilqis.mlx.bamf-rejection-authority/v2"
PORTABLE_REJECTION_RECEIPT_SCHEMA = "bilqis.mlx.bamf-rejection-receipt/v2"
_DEPENDENCY_PREFIX = "salience-event:bamf-rejection:"


def rejection_registry(correction_frontier) -> SourceAuthorityRegistry | None:
    """Recover the public C09 registry embedded in accepted generation custody."""
    if not isinstance(correction_frontier, dict):
        return None
    record_present = "source_authority_registry" in correction_frontier
    digest_present = "source_authority_registry_sha256" in correction_frontier
    if record_present != digest_present:
        invalid("BAMF_REJECTION_PORTABLE_AUTHORITY_INVALID")
    if not record_present:
        return None
    record = correction_frontier.get("source_authority_registry")
    digest = correction_frontier.get("source_authority_registry_sha256")
    try:
        registry = SourceAuthorityRegistry.from_record(record)
    except BilqisError:
        invalid("BAMF_REJECTION_PORTABLE_AUTHORITY_INVALID")
    if registry.digest != digest:
        invalid("BAMF_REJECTION_PORTABLE_AUTHORITY_INVALID")
    return registry


def _claim(
        *, run_id: str, generation: int, student_manifest_sha256: str,
        optimizer_step: int, evidence: dict, owner_id: str,
        public_key_hex: str) -> dict:
    return {
        "schema": PORTABLE_REJECTION_AUTHORITY_SCHEMA,
        "run_id": run_id,
        "generation": generation,
        "student_manifest_sha256": student_manifest_sha256,
        "optimizer_step": optimizer_step,
        "evidence_sha256": sha(canonical(evidence)),
        "source_owner": owner_id,
        "source_public_key_hex": public_key_hex,
    }


def issue_portable_rejection_authority(
        registry: SourceAuthorityRegistry, *, run_id: str, generation: int,
        student_manifest_sha256: str, optimizer_step: int, evidence: dict) -> dict:
    """Sign rejection identity with the fixed C06 owner key already trusted by C09."""
    if not isinstance(registry, SourceAuthorityRegistry):
        invalid("BAMF_REJECTION_PORTABLE_AUTHORITY_INVALID")
    from ._darwin_salience_signer import read_host_system_source_authority_signer

    signer = read_host_system_source_authority_signer(registry)
    claim = _claim(
        run_id=run_id, generation=generation,
        student_manifest_sha256=student_manifest_sha256,
        optimizer_step=optimizer_step, evidence=evidence,
        owner_id=signer.owner_id, public_key_hex=signer.public_key_hex)
    dependency_key = _DEPENDENCY_PREFIX + sha(canonical(claim))
    signed = {**claim, "dependency_key": dependency_key}
    dependency = DependencyRef(DependencyKind.ARTIFACT, dependency_key)
    return {
        **signed,
        "source_signature_hex": signer.sign(dependency, canonical(signed)),
    }


def try_issue_portable_rejection_authority(
        registry: SourceAuthorityRegistry, *, run_id: str, generation: int,
        student_manifest_sha256: str, optimizer_step: int, evidence: dict) -> dict | None:
    """Issue portable authority when the fixed host signer is provisioned.

    Missing signer custody or a signer not authorized by this accepted registry
    preserves the historical live-only rejection path.  Malformed signer custody
    and invalid claims remain hard failures.
    """
    try:
        return issue_portable_rejection_authority(
            registry, run_id=run_id, generation=generation,
            student_manifest_sha256=student_manifest_sha256,
            optimizer_step=optimizer_step, evidence=evidence)
    except BilqisError as error:
        if error.context.get("reason") in {
            "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_REQUIRED",
            "BAMF_C09_SOURCE_AUTHORITY_UNREGISTERED",
            "BAMF_C09_SOURCE_AUTHORITY_KEY_MISMATCH",
            "BAMF_C09_SOURCE_AUTHORITY_SCOPE_MISMATCH",
        }:
            return None
        raise


def verify_portable_rejection_authority(
        authority, registry: SourceAuthorityRegistry, *, run_id: str,
        generation: int, student_manifest_sha256: str, optimizer_step: int,
        evidence: dict) -> None:
    """Verify an inline rejection authority without host-local or shared state."""
    fields = {
        "schema", "run_id", "generation", "student_manifest_sha256",
        "optimizer_step", "evidence_sha256", "source_owner",
        "source_public_key_hex", "dependency_key", "source_signature_hex",
    }
    if (not isinstance(authority, dict) or set(authority) != fields
            or authority.get("schema") != PORTABLE_REJECTION_AUTHORITY_SCHEMA):
        invalid("BAMF_REJECTION_PORTABLE_AUTHORITY_INVALID")
    claim = _claim(
        run_id=run_id, generation=generation,
        student_manifest_sha256=student_manifest_sha256,
        optimizer_step=optimizer_step, evidence=evidence,
        owner_id=authority.get("source_owner"),
        public_key_hex=authority.get("source_public_key_hex"))
    expected_dependency = _DEPENDENCY_PREFIX + sha(canonical(claim))
    signed = {**claim, "dependency_key": expected_dependency}
    if (authority.get("dependency_key") != expected_dependency
            or authority.get("evidence_sha256") != claim["evidence_sha256"]):
        invalid("BAMF_REJECTION_PORTABLE_AUTHORITY_INVALID")
    registry.verify_detached(
        authority["source_owner"],
        DependencyRef(DependencyKind.ARTIFACT, expected_dependency),
        authority["source_signature_hex"], canonical(signed),
        authority["source_public_key_hex"],
    )


def portable_rejection_receipt(
        *, run_id: str, generation: int, student_manifest_sha256: str,
        optimizer_step: int, authority_sha256: str) -> dict:
    return {
        "schema": PORTABLE_REJECTION_RECEIPT_SCHEMA,
        "run_id": run_id,
        "generation": generation,
        "student_manifest_sha256": student_manifest_sha256,
        "optimizer_step": optimizer_step,
        "rejection_authority_sha256": authority_sha256,
    }


__all__ = (
    "PORTABLE_REJECTION_AUTHORITY_SCHEMA", "PORTABLE_REJECTION_RECEIPT_SCHEMA",
    "issue_portable_rejection_authority", "portable_rejection_receipt",
    "rejection_registry", "try_issue_portable_rejection_authority",
    "verify_portable_rejection_authority",
)
