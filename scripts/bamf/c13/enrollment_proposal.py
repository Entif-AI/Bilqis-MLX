"""Non-authoritative operator proposal for the C13 C07 enrollment gate."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation


PROPOSAL_SCHEMA = "bilqis.c13.atlas-enrollment-proposal/v1"
ATLAS_APPROVAL_PREFIX = "atlas-approval:"


def build_enrollment_proposal(run_dir: str | Path) -> dict:
    """Expose only accepted public facts needed by the external approval signer."""
    run_dir = Path(run_dir).resolve()
    student = load_accepted_generation(run_dir)
    identity = student.run_identity
    if identity is None:
        raise ValueError("BAMF_C13_ENROLLMENT_RUN_IDENTITY_REQUIRED")
    correction = student.correction_frontier
    registry = correction.get("source_authority_registry")
    registry_sha256 = correction.get("source_authority_registry_sha256")
    if (not isinstance(registry, dict) or not isinstance(registry_sha256, str)
            or len(registry_sha256) != 64):
        raise ValueError("BAMF_C13_ENROLLMENT_SOURCE_AUTHORITY_REQUIRED")
    signers = []
    for key in registry.get("keys", ()):
        if not isinstance(key, dict):
            continue
        scopes = tuple(
            scope for scope in key.get("allowed_scopes", ())
            if isinstance(scope, dict)
            and scope.get("kind") == "ARTIFACT"
            and ATLAS_APPROVAL_PREFIX.startswith(scope.get("key_prefix", ""))
        )
        if scopes:
            signers.append({
                "owner_id": key.get("owner_id"),
                "public_key_hex": key.get("public_key_hex"),
                "allowed_scopes": list(scopes),
            })
    return {
        "schema": PROPOSAL_SCHEMA,
        "authority": "NON_AUTHORITATIVE_PROPOSAL_ONLY",
        "requested_run_id": identity.run_id,
        "requested_run_seed": identity.run_seed,
        "requested_topology_digest": identity.initial_topology_digest,
        "atlas_release_sha256": identity.initial_release_digest,
        "source_authority_registry_sha256": registry_sha256,
        "eligible_atlas_approval_signers": signers,
        "blocking_reason": (
            None if signers else
            "NO_ACCEPTED_C09_KEY_WITH_ARTIFACT_ATLAS_APPROVAL_SCOPE"
        ),
        "required_source_approval_fields": [
            "approval_id", "atlas_release_sha256", "source_family_ids",
            "operator_ids", "rights_receipt_sha256", "rights_epoch",
            "prerequisite_policy_sha256", "progression_policy_sha256",
            "authority_audit_receipt_sha256", "audit_passed",
            "rights_compatible", "source_owner", "signature_hex",
            "delta_budget_policy",
        ],
        "required_enrollment_request_fields": [
            "lease_id", "requested_run_id", "requested_run_seed",
            "requested_topology_digest", "source_approval", "resource_ceiling",
            "requested_at", "human_command_sha256", "admission_policy",
            "schema_version",
        ],
        "note": (
            "A repository process must not sign this proposal. The matching external "
            "source owner signs AtlasSourceApproval, then the human operator supplies "
            "the complete AtlasAdmissionEnrollmentRequestV2 to C07."
        ),
    }


__all__ = ("ATLAS_APPROVAL_PREFIX", "PROPOSAL_SCHEMA", "build_enrollment_proposal")
