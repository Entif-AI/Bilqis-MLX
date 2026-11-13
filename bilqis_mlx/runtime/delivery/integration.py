"""C15.1a composition rules for already-owned BAMF delivery receipts."""
from __future__ import annotations

from .contracts import (
    BamfDeliveryManifest, EgmStatus, ProofState, ReceiptStatus, require,
)

REQUIRED_COMPONENTS = ("B14", "C11", "C12", "C13", "C14", "C16")
REQUIRED_EGM_REVIEWERS = ("codebase-details", "implementation-readiness")
REQUIRED_COMMANDS = ("cold-resume", "owner-start", "preflight", "read-only-status")


def integrate_delivery_receipts(*, components, issues, commits, proofs, egm,
                                operator_commands) -> BamfDeliveryManifest:
    """Compose owned receipts without promoting provisional evidence to acceptance."""
    require(tuple(item.component_id for item in components) == REQUIRED_COMPONENTS,
            "C15_COMPONENT_SET")
    require(tuple(item.reviewer for item in egm) == REQUIRED_EGM_REVIEWERS,
            "C15_EGM_REVIEWERS")
    require(tuple(item.command_id for item in operator_commands) == REQUIRED_COMMANDS,
            "C15_OPERATOR_COMMANDS")
    require(all(item.state is ProofState.EXECUTED_PASS for item in operator_commands),
            "C15_OPERATOR_COMMAND_PROOF")

    blocked = any(item.status is ReceiptStatus.BLOCKED for item in components)
    provisional = any(item.status is ReceiptStatus.PROVISIONAL for item in components)
    failed_review = any(item.status is EgmStatus.FAIL for item in egm)
    pending_review = any(item.status is EgmStatus.PENDING for item in egm)
    software_status = (
        "BLOCKED" if blocked or failed_review else
        "IN_PROGRESS" if provisional or pending_review else
        "READY_FOR_OWNER_MERGE"
    )
    return BamfDeliveryManifest(
        components, issues, commits, proofs, egm, operator_commands,
        software_delivery_status=software_status,
        student_mastery_status="NOT_CLAIMED",
    )
