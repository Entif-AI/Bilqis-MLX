"""C15 conformance projection from repository authority and immutable run receipts."""
from __future__ import annotations

import json

from .conformance import (
    ConformanceProjection,
    ConformanceRow,
    EvidenceBinding,
    ExecutionReceipt,
    FailureGate,
    required_claim_ids,
)
from .contracts import ProofState, require
from .publication_state import (
    BLOCKED_CLAIMS,
    C15_REQUALIFICATION_RECEIPT_COMMIT,
    FIXTURE_OWNERS,
    REQ_OWNERS,
)
from .sources import (
    ROOT,
    authority_identity,
    expected_behavior,
    fixture_source_text,
    item_by_key,
    literal_test_ref,
    requirement_texts,
)

_GLOBAL_GATE_IDS = ("GRADE_NEUTRAL_INVARIANCE", "NO_LEGACY_BAV_RUNTIME_NAMESPACE")


def _owner(index: int) -> str:
    return (REQ_OWNERS[index] if index < len(REQ_OWNERS)
            else FIXTURE_OWNERS[index - len(REQ_OWNERS)])


def _evidence_binding(claim_id: str, owner: str, index: int,
                      state: ProofState, test_ref: str) -> EvidenceBinding:
    primary = owner.split("/")[0]
    item = item_by_key(primary)
    normative = (requirement_texts()[claim_id] if index < len(REQ_OWNERS)
                 else fixture_source_text(claim_id, primary))
    blocked = state in {ProofState.BLOCKED, ProofState.REQUALIFICATION_REQUIRED}
    return EvidenceBinding(
        normative_text=normative,
        variant_revision="BAMF-0.2-SPEC-001@v0.2.0",
        owner_issue=item["number"],
        owner_commit="PENDING_DIRECT_OWNER_COMMIT_BINDING",
        contract_path="docs/architecture/BAMF_0_2.md#requirements-continuity",
        input_fixture=test_ref,
        expected_behavior=expected_behavior(primary, claim_id),
        observed_output="BLOCKED" if blocked else "NOT_EXECUTED",
        runner_environment="PENDING_CURRENT_HEAD_RUNNER",
        run_receipt=None,
        receipt_commit="PENDING_ATTESTATION_COMMIT",
        reviewer_decision="BLOCKED" if blocked else "PENDING",
        authority_identity=authority_identity(primary),
    )


def _requalification_index() -> dict | None:
    if C15_REQUALIFICATION_RECEIPT_COMMIT is None:
        return None
    record = json.loads(
        (ROOT / "docs/evidence/bamf/delivery/runs/index.json").read_text())
    require(
        record.get("schema") == "bilqis.bamf.c15-requalification/v1"
        and bool(record.get("all_pass"))
        and len(record.get("claims", ())) == len(required_claim_ids())
        and len(record.get("gates", ())) == len(_GLOBAL_GATE_IDS),
        "PUBLICATION_REQUALIFICATION_INDEX",
    )
    return record


def _executed_binding(claim_id: str, owner: str, index: int,
                      run: dict) -> EvidenceBinding:
    primary = owner.split("/")[0]
    test_ref = literal_test_ref(primary, claim_id)
    expected = expected_behavior(primary, claim_id)
    require(
        run.get("claim_id") == claim_id and run.get("owner_ref") == owner
        and run.get("primary_owner") == primary and run.get("test_ref") == test_ref
        and run.get("expected_behavior") == expected,
        "PUBLICATION_REQUALIFICATION_ROW",
    )
    receipt = ExecutionReceipt(**run["run_receipt"])
    state = ProofState.EXECUTED_PASS if receipt.disposition == "PASS" else ProofState.EXECUTED_FAIL
    return EvidenceBinding(
        normative_text=(requirement_texts()[claim_id] if index < len(REQ_OWNERS)
                        else fixture_source_text(claim_id, primary)),
        variant_revision="BAMF-0.2-SPEC-001@v0.2.0",
        owner_issue=item_by_key(primary)["number"],
        owner_commit=receipt.candidate_sha,
        contract_path="docs/architecture/BAMF_0_2.md#requirements-continuity",
        input_fixture=test_ref,
        expected_behavior=expected,
        observed_output=run["observed_output"],
        runner_environment=run["runner_environment"],
        run_receipt=receipt,
        receipt_commit=C15_REQUALIFICATION_RECEIPT_COMMIT,
        reviewer_decision="PASS" if state is ProofState.EXECUTED_PASS else "FAIL",
        authority_identity=authority_identity(primary),
    )


def _executed_projection(record: dict) -> ConformanceProjection:
    by_claim = {row["claim_id"]: row for row in record["claims"]}
    rows = []
    for index, claim_id in enumerate(required_claim_ids()):
        owner = _owner(index)
        evidence = _executed_binding(claim_id, owner, index, by_claim[claim_id])
        rows.append(ConformanceRow(
            claim_id, owner, "docs/architecture/BAMF_0_2.md#requirements-continuity",
            evidence.input_fixture,
            ProofState.EXECUTED_PASS if evidence.run_receipt.disposition == "PASS"
            else ProofState.EXECUTED_FAIL,
            evidence))
    gates_by_id = {gate["gate_id"]: gate for gate in record["gates"]}
    gates = tuple(FailureGate(
        gate_id, gates_by_id[gate_id]["test_ref"],
        ProofState.EXECUTED_PASS if gates_by_id[gate_id]["pass"]
        else ProofState.EXECUTED_FAIL,
        gates_by_id[gate_id]["observed"])
        for gate_id in _GLOBAL_GATE_IDS)
    return ConformanceProjection(tuple(rows), gates, "READY_FOR_OWNER_MERGE", "NOT_CLAIMED")


def _pending_projection() -> ConformanceProjection:
    rows = []
    for index, claim_id in enumerate(required_claim_ids()):
        owner = _owner(index)
        if claim_id == "F15":
            state = ProofState.REQUALIFICATION_REQUIRED
            test_ref = "bilqis_mlx/runtime/tests/correction/test_atlas_stale_replay.py"
        elif claim_id in BLOCKED_CLAIMS:
            state = ProofState.BLOCKED
            test_ref = "BLOCKED_SOURCE_OWNER:C13/C14:accepted-integrated-witness"
        else:
            test_ref = literal_test_ref(owner.split("/")[0], claim_id)
            state = (ProofState.SPECIFIED if test_ref.startswith("BLOCKED_SOURCE_OWNER:")
                     else ProofState.CODE_PRESENT)
        rows.append(ConformanceRow(
            claim_id, owner, "docs/architecture/BAMF_0_2.md#requirements-continuity",
            test_ref, state, _evidence_binding(claim_id, owner, index, state, test_ref)))
    gates = (
        FailureGate("GRADE_NEUTRAL_INVARIANCE",
                    "bilqis_mlx/learning/tests/teaching/test_c03_parent_acceptance.py",
                    ProofState.CODE_PRESENT,
                    "explicit grade-ID permutation witness present; fresh current-head run pending"),
        FailureGate("NO_LEGACY_BAV_RUNTIME_NAMESPACE",
                    "bilqis_mlx/runtime/delivery/tests/test_no_legacy_bav_namespace.py",
                    ProofState.CODE_PRESENT,
                    "runtime namespace refusal witness present; fresh current-head run pending"),
    )
    return ConformanceProjection(tuple(rows), gates, "IN_PROGRESS", "NOT_CLAIMED")


def published_conformance_record() -> dict:
    """Return the current deterministic 24+20 conformance projection."""
    requalification = _requalification_index()
    projection = (_executed_projection(requalification) if requalification is not None
                  else _pending_projection())
    return {**projection.to_record(), "conformance_sha256": projection.digest()}
