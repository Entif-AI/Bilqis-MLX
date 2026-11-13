"""Public-safe C15 evidence-boundary and roadmap projections."""
from __future__ import annotations

from .publication_state import (
    C15_1A_HEAD,
    C15_1B_HEAD,
    C15_2_HEAD,
    C15_2_ISSUE_DIGEST,
    C15_EGM_CANDIDATE,
    C15_EGM_REPORT_HEAD,
    C15_FINAL_CANDIDATE,
    CONTRACT_DIGEST,
    ISSUE_BOOK_DIGEST,
    REVIEWED_UNIFIED,
    SOURCE_DIGEST,
)
from .sources import local_graph_proof, privacy_clause


def published_boundary_record() -> dict:
    """Public-safe C15.2 authority, graph, branch and privacy boundary."""
    graph = local_graph_proof()
    privacy_text, privacy_sha = privacy_clause()
    return {
        "schema": "bilqis.bamf.delivery-evidence-boundary/v1",
        "branch": "codex/bamf02-c-runtime",
        "source_head": C15_FINAL_CANDIDATE,
        "reviewed_unified": REVIEWED_UNIFIED,
        "authority_digests": {
            "architecture": CONTRACT_DIGEST,
            "workstack": SOURCE_DIGEST,
            "issue_book": ISSUE_BOOK_DIGEST,
            "issue_539_body": C15_2_ISSUE_DIGEST,
        },
        "cross_document_diff": {
            "scope": "C15 behavioral-conformance and grade-neutrality clauses",
            "reviewer": "google-egm-b3a359-initial",
            "candidate_sha": C15_2_HEAD,
            "repair_sha": C15_EGM_CANDIDATE,
            "active_reconciliation_sha": C15_FINAL_CANDIDATE,
            "initial_findings": {"blockers": 4, "majors": 5, "nits": 1},
            "disposition": "PASS_0_BLOCKERS_0_MAJORS_0_NITS",
            "report_head": C15_EGM_REPORT_HEAD,
        },
        "dependency_graph": {
            "status": graph.status,
            "owner_count": graph.owner_count,
            "child_count": graph.child_count,
            "node_count": graph.node_count,
            "held_keys": list(graph.held_keys),
            "mirror_mismatches": list(graph.mirror_mismatches),
            "unknown_dependencies": list(graph.unknown_dependencies),
            "cycles": list(graph.cycles),
        },
        "source_privacy_boundary": {
            "source_text": privacy_text,
            "source_sha256": privacy_sha,
            "public_allowed": ["PUBLIC_FIXTURE", "PUBLIC_DERIVED", "public issue receipts"],
            "protected_excluded": ["PRIVATE_REAL", "private journal payloads", "unclassified payloads"],
            "disposition": "PROTECTED_EVIDENCE_NOT_COPIED_TO_PUBLIC_ARTIFACTS",
        },
        "live_issue_parity": "PASS_43_OWNERS_172_CHILDREN_190_NATIVE_EDGES_215_DAG_NODES",
        "fresh_behavioral_proof": "C15_FINAL_REQUALIFICATION_44_OF_44_PLUS_2_GATES_PASS_AT_C4197F28",
    }


def published_roadmap_record() -> dict:
    """Current public C15 leaf/upstream projection, generated from frozen receipts."""
    return {
        "schema": "bilqis.bamf.delivery-roadmap-projection/v2",
        "source_reviewed_unified": REVIEWED_UNIFIED,
        "historical_issue_book_sha256": ISSUE_BOOK_DIGEST,
        "historical_workstack_sha256": SOURCE_DIGEST,
        "software_delivery_status": "READY_FOR_OWNER_MERGE",
        "student_mastery_status": "NOT_CLAIMED",
        "leaves": [
            {"issue": 537, "key": "C15.1a", "head_sha": C15_1A_HEAD,
             "status": "FINAL_REQUALIFICATION_PASS", "final_gate": "OWNER_MERGE"},
            {"issue": 538, "key": "C15.1b", "head_sha": C15_1B_HEAD,
             "status": "FINAL_REQUALIFICATION_PASS", "final_gate": "OWNER_MERGE"},
            {"issue": 539, "key": "C15.2", "head_sha": C15_2_HEAD,
             "status": "FINAL_REQUALIFICATION_PASS", "final_gate": "OWNER_MERGE"},
            {"issue": 540, "key": "C15.3", "head_sha": C15_FINAL_CANDIDATE,
             "status": "FINAL_REQUALIFICATION_PASS", "final_gate": "OWNER_MERGE"},
        ],
        "egm_repair_head": C15_EGM_CANDIDATE,
        "upstream": [
            {"issue": 385, "key": "C13",
             "head_sha": "9e06ea557c910bae7ecd879fe83f4d50aed84eb9",
             "status": "ACCEPTED_RELEASE_SCOPED_INTEGRATION"},
            {"issue": 386, "key": "C14", "head_sha": REVIEWED_UNIFIED,
             "status": "ACCEPTED_CONTINUING_DEVELOPMENT_PROGRAM"},
        ],
    }
