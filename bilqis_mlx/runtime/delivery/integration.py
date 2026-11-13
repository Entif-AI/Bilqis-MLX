"""C15.1a composition rules for already-owned BAMF delivery receipts."""
from __future__ import annotations

from .contracts import (
    BamfDeliveryManifest, EgmStatus, ProofState, ReceiptStatus, require,
)

REQUIRED_COMPONENTS = ("B14", "C11", "C12", "C13", "C14", "C16")
REQUIRED_EGM_REVIEWERS = ("codebase-details", "implementation-readiness")
REQUIRED_COMMANDS = ("cold-resume", "owner-start", "preflight", "read-only-status")


def integrate_delivery_receipts(*, components, issues, commits, proofs, egm,
                                operator_commands, conformance) -> BamfDeliveryManifest:
    """Compose owned receipts without promoting provisional evidence to acceptance."""
    component_ids = tuple(item.component_id for item in components)
    require(all(name in component_ids for name in REQUIRED_COMPONENTS),
            "C15_COMPONENT_SET")
    require(tuple(item.reviewer for item in egm) == REQUIRED_EGM_REVIEWERS,
            "C15_EGM_REVIEWERS")
    require(tuple(item.command_id for item in operator_commands) == REQUIRED_COMMANDS,
            "C15_OPERATOR_COMMANDS")
    require(all(item.state is ProofState.EXECUTED_PASS for item in operator_commands),
            "C15_OPERATOR_COMMAND_PROOF")
    require(getattr(conformance, "student_mastery_status", None) == "NOT_CLAIMED",
            "C15_CONFORMANCE_MASTERY_SEPARATION")
    conformance_status = getattr(conformance, "software_delivery_status", None)
    require(conformance_status in {
        "IN_PROGRESS", "READY_FOR_OWNER_MERGE", "DELIVERED", "BLOCKED",
    }, "C15_CONFORMANCE_STATUS")

    blocked = any(item.status is ReceiptStatus.BLOCKED for item in components)
    provisional = any(item.status is ReceiptStatus.PROVISIONAL for item in components)
    failed_review = any(item.status is EgmStatus.FAIL for item in egm)
    pending_review = any(item.status is EgmStatus.PENDING for item in egm)
    receipts_status = (
        "BLOCKED" if blocked or failed_review else
        "IN_PROGRESS" if provisional or pending_review else
        "READY_FOR_OWNER_MERGE")
    if "BLOCKED" in {receipts_status, conformance_status}:
        software_status = "BLOCKED"
    elif "IN_PROGRESS" in {receipts_status, conformance_status}:
        software_status = "IN_PROGRESS"
    else:
        require(conformance_status in {"READY_FOR_OWNER_MERGE", "DELIVERED"},
                "C15_CONFORMANCE_NOT_READY")
        software_status = "READY_FOR_OWNER_MERGE"
    return BamfDeliveryManifest(
        components, issues, commits, proofs, egm, operator_commands,
        software_delivery_status=software_status,
        student_mastery_status="NOT_CLAIMED",
    )
