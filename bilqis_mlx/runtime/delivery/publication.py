"""Deterministic public-safe C15.1b delivery publication."""
from __future__ import annotations
import json

from bilqis_mlx.runtime.delivery import (
    CommitReceipt, ComponentReceipt, EgmReceipt, EgmStatus, IssueReceipt,
    OperatorCommandReceipt, ProofReceipt, ProofState, ReceiptStatus,
    integrate_delivery_receipts, seal_manifest,
)
from .conformance import ExecutionReceipt

from .conformance import (
    ConformanceProjection, ConformanceRow, EvidenceBinding, FailureGate,
    required_claim_ids,
)
from .sources import (
    ARCHITECTURE, ISSUE_BOOK, ROOT, WORKSTACK, authority_identity, child_by_key,
    expected_behavior, file_digest, fixture_source_text, item_by_key, literal_test_ref,
    local_graph_proof, privacy_clause, requirement_texts,
)

PINNED_EGM = "b3a35956759bf7f024af2ff061b2e0b44b438e4c"
C15_1A_HEAD = "4759336facf7a3482254b32c8647013ae447f074"
C15_1B_HEAD = "030aa51d5e3f1e669648831cee2b7b340dab1c67"
C15_2_HEAD = "96ec126f0a9a02d9e1adaafcdd5dbf859d6d1111"
C15_EGM_REPAIR_HEAD = "a008e1d2770c968e1b7784d00194e4f75e402041"
C15_EGM_CANDIDATE = "66277ed61d0ae4cabb088dfb508ab7188415003c"
C15_EGM_REPORT_HEAD = "fc04b9379e5657cd046836c4af9ea4dd76df4795"
C15_3_RECONCILIATION_HEAD = "16117bfb782ce0b1a3f301e2f5441917a915fd9d"
C15_REQUALIFICATION_RECEIPT_COMMIT: str | None = None
SOURCE_DIGEST = file_digest(WORKSTACK)
CONTRACT_DIGEST = file_digest(ARCHITECTURE)
ISSUE_BOOK_DIGEST = file_digest(ISSUE_BOOK)
C15_2_ISSUE_DIGEST = child_by_key("C15.2")["body_sha256"]
REVIEWED_UNIFIED = "9e06ea557c910bae7ecd879fe83f4d50aed84eb9"


def _component_receipts() -> tuple[ComponentReceipt, ...]:
    rows = (
        ComponentReceipt("B14", 375, "dd63880fdfde9d01eccbbff876e39828dbded3f6",
                         ReceiptStatus.ACCEPTED, "issue:375#issuecomment-6800933565"),
        ComponentReceipt("C11", 384, "ce09a0c1887069385b903ac10a4d576d22d04881",
                         ReceiptStatus.ACCEPTED, "issue:384#issuecomment-6840426430"),
        ComponentReceipt("C12", 381, "516725b6170f258ad86b0c5d4ca050907238e59d",
                         ReceiptStatus.ACCEPTED, "issue:381#issuecomment-6754534350"),
        ComponentReceipt("C13", 385, "4b486268825f07330c4bd8147ca2439a36be5fee",
                         ReceiptStatus.ACCEPTED, "issue:530#issuecomment-6864723375"),
        ComponentReceipt("C14", 386, "29101af83aaa592ab1ace59c68bfdba153c7fb53",
                         ReceiptStatus.PROVISIONAL, "issue:535#issuecomment-6864928413"),
        ComponentReceipt("C16", 382, "c672c62113108695a2a60cd0eb0d7f19d085f838",
                         ReceiptStatus.ACCEPTED, "issue:382#issuecomment-6832648874"),
        ComponentReceipt("architecture", 540, C15_3_RECONCILIATION_HEAD,
                         ReceiptStatus.PROVISIONAL,
                         f"docs/architecture/BAMF_0_2.md@sha256:{CONTRACT_DIGEST}"),
        ComponentReceipt("codec", 375,
                         "1265200be9bac5b97a3aecd0e82127af1dd4d98ca86da6829ea0ce0e9b69c000",
                         ReceiptStatus.ACCEPTED,
                         "bilqis_mlx/runtime/_model/cache/atlas_cache_codec.py"),
        ComponentReceipt("compiler", 357,
                         "acafc03e20353d55bd02c4a0d70ab3d7b36c1558632932b0d75b1cf9399de3a1",
                         ReceiptStatus.ACCEPTED,
                         "bilqis_mlx/runtime/_custody/bamf_bundle/vocabulary/compiler_binding.py"),
        ComponentReceipt("delivery-tests", 539, C15_EGM_CANDIDATE,
                         ReceiptStatus.PROVISIONAL,
                         f"git:{C15_EGM_CANDIDATE}:bilqis_mlx/runtime/delivery/tests"),
        ComponentReceipt("factory-head", 358, "0b9b6d8589e7cea1fcd03aeac270b2488736d2a2",
                         ReceiptStatus.ACCEPTED, "git:bilqis_mlx/factory"),
        ComponentReceipt("issue-book", 341, REVIEWED_UNIFIED,
                         ReceiptStatus.ACCEPTED,
                         f"docs/tasks/bamf-0.2/ISSUE_BOOK.md@sha256:{ISSUE_BOOK_DIGEST}"),
        ComponentReceipt("plasticity", 368,
                         "8f7d65638b2cb6978f924c4b803982a2a0283e46756336129e903a04a193e8c9",
                         ReceiptStatus.ACCEPTED,
                         "bilqis_mlx/learning/_retention/atlas_plasticity.py"),
        ComponentReceipt("semantic-release", 345,
                         "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306",
                         ReceiptStatus.ACCEPTED,
                         "bilqis_mlx/semantics/atlas_source_pins_v1.json:A01_SOURCE_ATTESTED_NOT_NEURAL_ADMITTED"),
        ComponentReceipt("teacher-head", 376, "0b9b6d8589e7cea1fcd03aeac270b2488736d2a2",
                         ReceiptStatus.ACCEPTED, "git:bilqis_mlx/runtime/_teacher"),
        ComponentReceipt("topology", 382,
                         "3e7f7ff6e83096fcd66c611d9188b3473160237ca4a69aee61a6b3eeed6fa428",
                         ReceiptStatus.ACCEPTED, "configs/models/bamf-0.2.json"),
        ComponentReceipt("workstack", 341, REVIEWED_UNIFIED,
                         ReceiptStatus.ACCEPTED,
                         f"docs/tasks/bamf-0.2/workstack.json@sha256:{SOURCE_DIGEST}"),
    )
    return tuple(sorted(rows, key=lambda item: item.component_id))


def _issue_receipts() -> tuple[IssueReceipt, ...]:
    rows = (
        IssueReceipt(375, "B14", "CLOSED", ReceiptStatus.ACCEPTED,
                     "dd63880fdfde9d01eccbbff876e39828dbded3f6",
                     "issue:375#issuecomment-6800933565"),
        IssueReceipt(381, "C12", "CLOSED", ReceiptStatus.ACCEPTED,
                     "516725b6170f258ad86b0c5d4ca050907238e59d",
                     "issue:381#issuecomment-6754534350"),
        IssueReceipt(382, "C16", "CLOSED", ReceiptStatus.ACCEPTED,
                     "c672c62113108695a2a60cd0eb0d7f19d085f838",
                     "issue:382#issuecomment-6832648874"),
        IssueReceipt(384, "C11", "CLOSED", ReceiptStatus.ACCEPTED,
                     "ce09a0c1887069385b903ac10a4d576d22d04881",
                     "issue:384#issuecomment-6840426430"),
        IssueReceipt(385, "C13", "CLOSED", ReceiptStatus.ACCEPTED,
                     "9e06ea557c910bae7ecd879fe83f4d50aed84eb9",
                     "pull:1042"),
        IssueReceipt(386, "C14", "OPEN", ReceiptStatus.PROVISIONAL,
                     "29101af83aaa592ab1ace59c68bfdba153c7fb53",
                     "issue:535#issuecomment-6864928413"),
        IssueReceipt(537, "C15.1a", "OPEN", ReceiptStatus.PROVISIONAL,
                     C15_1A_HEAD, "issue:537#issuecomment-6856503488"),
        IssueReceipt(538, "C15.1b", "OPEN", ReceiptStatus.PROVISIONAL,
                     C15_1B_HEAD, "issue:538#issuecomment-6856845206"),
        IssueReceipt(539, "C15.2", "OPEN", ReceiptStatus.PROVISIONAL,
                     C15_2_HEAD, "issue:539#issuecomment-6857007014"),
    )
    return tuple(sorted(rows, key=lambda item: item.issue))


def _commit_receipts() -> tuple[CommitReceipt, ...]:
    rows = (
        CommitReceipt("0ae919779e1de44f5c7c96e911b3f61780099e21", 384,
                      "C11 accepted integration"),
        CommitReceipt("5166aca71f01f09cfb4e533d61dc41e53a987726", 375,
                      "B14 accepted integration"),
        CommitReceipt("516725b6170f258ad86b0c5d4ca050907238e59d", 381,
                      "C12 accepted integration"),
        CommitReceipt(C15_1A_HEAD, 537, "C15.1a development checkpoint"),
        CommitReceipt(C15_1B_HEAD, 538, "C15.1b development checkpoint"),
        CommitReceipt(C15_2_HEAD, 539, "C15.2 development checkpoint"),
        CommitReceipt("4b486268825f07330c4bd8147ca2439a36be5fee", 385,
                      "C13 accepted release-scoped handoff"),
        CommitReceipt("c672c62113108695a2a60cd0eb0d7f19d085f838", 382,
                      "C16 accepted integration"),
    )
    return tuple(sorted(rows, key=lambda item: item.sha))


def _proof_receipts() -> tuple[ProofReceipt, ...]:
    rows = (
        ProofReceipt("c11.operator-contract", ProofState.EXECUTED_PASS,
                     "bilqis.bamf.operator-cli/v2", "bilqis.bamf.operator-lifecycle/v1",
                     "issue:384#issuecomment-6840426430",
                     "73/73 parent selections PASS; final review 0 Blocker/Major/Minor/Nit"),
        ProofReceipt("c13.integrated-learning", ProofState.EXECUTED_PASS,
                     "bilqis.c13.episode-binding-generator/v1", "bilqis.c13.acceptance/v1",
                     "docs/evidence/bamf/C13/integration-handoff-20261113.md",
                     "release-scoped integrated wiring accepted: C13 owner 13/13 and rollback/custody 54/54 PASS; real M3 Ultra generation-zero path accepted; extended learning soak deferred to BAMF-0.3 #1039"),
        ProofReceipt("c14.training-program", ProofState.BLOCKED,
                     "bilqis.bamf.developmental-program/v1", "bilqis.bamf.training-program-proof/v1",
                     "issue:535#issuecomment-6864928413",
                     "complete C14 stack review-clean at 29101af83aaa592ab1ace59c68bfdba153c7fb53; parent acceptance waits on human PR chain #1043 -> #1044 -> #1045 -> #535 turn-in"),
        ProofReceipt("c15.delivery-contract", ProofState.EXECUTED_PASS,
                     "bilqis.bamf.delivery-manifest/v1", "bilqis.bamf.delivery-manifest/v1",
                     "issue:537#issuecomment-6856503488", "9/9 focused C15.1a ring PASS"),
        ProofReceipt("c15.workstack", ProofState.EXECUTED_PASS,
                     "bilqis.bamf.workstack/v1", "bilqis.bamf.workstack.validation/v1",
                     "scripts/check_bamf_workstack.py",
                     "172 children; 43 live owner mirrors; held_keys=[]; executable order 215"),
    )
    return tuple(sorted(rows, key=lambda item: item.proof_id))


def _commands() -> tuple[OperatorCommandReceipt, ...]:
    rows = (
        OperatorCommandReceipt(
            "cold-resume",
            ("npm", "run", "train", "--", "--human-run", "--resume", "--run-dir",
             "<accepted-bamf-run>"), ProofState.EXECUTED_PASS,
            "bilqis_mlx/presentation/operator_cli/tests/bamf_lifecycle/test_bamf_resume.py",
            "issue:384#issuecomment-6840426430"),
        OperatorCommandReceipt(
            "owner-start",
            ("npm", "run", "train", "--", "--human-run", "--resume", "--run-dir",
             "/absolute/path/to/bamf-run", "--minutes", "90", "--reserve-gib", "100",
             "--max-visits", "1"), ProofState.EXECUTED_PASS,
            "bilqis_mlx/presentation/operator_cli/tests/bamf_lifecycle/test_bamf_resume.py",
            "docs/operations/BAMF_0_2_RUNBOOK.md"),
        OperatorCommandReceipt(
            "preflight", ("npm", "run", "train", "--", "--dry-run", "--model-topology",
                          "configs/models/bamf-0.2.json", "--atlas-release-manifest",
                          "<manifest.json>", "--run-dir", "<new-bamf-run>"),
            ProofState.EXECUTED_PASS,
            "bilqis_mlx/presentation/operator_cli/tests/test_bamf_preflight.py",
            "issue:384#issuecomment-6840426430"),
        OperatorCommandReceipt(
            "read-only-status", ("npm", "run", "dashboard", "--", "--run-dir",
                                 "/absolute/path/to/run", "--once", "--atlas-details"),
            ProofState.EXECUTED_PASS,
            "bilqis_mlx/presentation/tests/test_operator_dashboard_events.py",
            "docs/operations/BAMF_0_2_RUNBOOK.md"),
    )
    return tuple(sorted(rows, key=lambda item: item.command_id))


def published_manifest_record() -> dict:
    egm = tuple(EgmReceipt(
        name, EgmStatus.PASS, C15_EGM_CANDIDATE,
        f"git:{C15_EGM_REPORT_HEAD}:docs/evidence/bamf/delivery/egm-c15-537-539-20261113.md")
                for name in ("codebase-details", "implementation-readiness"))
    conformance_record = published_conformance_record()
    from .conformance import load_conformance_record
    conformance = load_conformance_record(conformance_record)
    manifest = integrate_delivery_receipts(
        components=_component_receipts(), issues=_issue_receipts(),
        commits=_commit_receipts(), proofs=_proof_receipts(), egm=egm,
        operator_commands=_commands(), conformance=conformance)
    return seal_manifest(manifest)


_REQ_OWNERS = (
    "A01/A02/A12", "A01/A02/A12", "A03/A04/A05", "A03/A04/A05",
    "A05/B04/B06/B08/B11/C13", "A03/A10/C10", "B01/B04/B11", "B01/B04/B11",
    "B05", "B07/B08/A02/B13/A13", "B07/B08/A02/B13/A13", "B06/C04",
    "B06/C04", "B14", "C02/C07/C14", "B12/B13/C05/C13", "C03/C13/C14",
    "C06", "A11/C09/C13", "C09/C10", "A10/C05/C12", "C08/C11/C16",
    "C01/B13/C13", "C05/C11/C13/C14",
)
_FIXTURE_OWNERS = (
    "A03/A11", "A03/A04", "A03/A04", "A03/A04", "A05/B04/B06/B11/C13",
    "A10/C09", "C09", "A13/C06", "A13", "A10/C05", "B07",
    "B07/B09/B12/B13/C13", "B14", "B01/B13", "C09", "A05/C02/C05/C13/C14",
    "A01/A12/C07", "C05", "C06/C09", "B13/C13/C16",
)
_BLOCKED = frozenset((
    "BAMF-REQ-015", "BAMF-REQ-016", "BAMF-REQ-017", "BAMF-REQ-019",
    "BAMF-REQ-023", "BAMF-REQ-024", "F05", "F12", "F16", "F20",
))

def _evidence_binding(claim_id: str, owner: str, index: int,
                      state: ProofState, test_ref: str) -> EvidenceBinding:
    primary = owner.split("/")[0]
    item = item_by_key(primary)
    normative = (requirement_texts()[claim_id] if index < len(_REQ_OWNERS)
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
    path = ROOT / "docs/evidence/bamf/delivery/runs/index.json"
    record = json.loads(path.read_text())
    if (record.get("schema") != "bilqis.bamf.c15-requalification/v1"
            or not record.get("all_pass")
            or len(record.get("claims", ())) != len(required_claim_ids())
            or len(record.get("gates", ())) != 2):
        raise ValueError("invalid C15 requalification index")
    return record


def _executed_binding(claim_id: str, owner: str, index: int,
                      run: dict) -> EvidenceBinding:
    primary = owner.split("/")[0]
    test_ref = literal_test_ref(primary, claim_id)
    expected = expected_behavior(primary, claim_id)
    if (run.get("claim_id") != claim_id or run.get("owner_ref") != owner
            or run.get("primary_owner") != primary or run.get("test_ref") != test_ref
            or run.get("expected_behavior") != expected):
        raise ValueError(f"stale C15 requalification row: {claim_id}")
    receipt = ExecutionReceipt(**run["run_receipt"])
    state = ProofState.EXECUTED_PASS if receipt.disposition == "PASS" else ProofState.EXECUTED_FAIL
    return EvidenceBinding(
        normative_text=(requirement_texts()[claim_id] if index < len(_REQ_OWNERS)
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


def published_conformance_record() -> dict:
    requalification = _requalification_index()
    if requalification is not None:
        by_claim = {row["claim_id"]: row for row in requalification["claims"]}
        rows = []
        for index, claim_id in enumerate(required_claim_ids()):
            owner = (_REQ_OWNERS[index] if index < len(_REQ_OWNERS)
                     else _FIXTURE_OWNERS[index - len(_REQ_OWNERS)])
            evidence = _executed_binding(claim_id, owner, index, by_claim[claim_id])
            rows.append(ConformanceRow(
                claim_id, owner, "docs/architecture/BAMF_0_2.md#requirements-continuity",
                evidence.input_fixture,
                ProofState.EXECUTED_PASS if evidence.run_receipt.disposition == "PASS"
                else ProofState.EXECUTED_FAIL,
                evidence))
        gates_by_id = {gate["gate_id"]: gate for gate in requalification["gates"]}
        gates = tuple(FailureGate(
            gate_id, gates_by_id[gate_id]["test_ref"],
            ProofState.EXECUTED_PASS if gates_by_id[gate_id]["pass"]
            else ProofState.EXECUTED_FAIL,
            gates_by_id[gate_id]["observed"])
            for gate_id in ("GRADE_NEUTRAL_INVARIANCE", "NO_LEGACY_BAV_RUNTIME_NAMESPACE"))
        projection = ConformanceProjection(
            tuple(rows), gates, "READY_FOR_OWNER_MERGE", "NOT_CLAIMED")
        return {**projection.to_record(), "conformance_sha256": projection.digest()}

    rows = []
    for index, claim_id in enumerate(required_claim_ids()):
        owner = (_REQ_OWNERS[index] if index < len(_REQ_OWNERS)
                 else _FIXTURE_OWNERS[index - len(_REQ_OWNERS)])
        if claim_id == "F15":
            state = ProofState.REQUALIFICATION_REQUIRED
            test_ref = "bilqis_mlx/runtime/tests/correction/test_atlas_stale_replay.py"
        elif claim_id in _BLOCKED:
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
        FailureGate(
            "GRADE_NEUTRAL_INVARIANCE",
            "bilqis_mlx/learning/tests/teaching/test_c03_parent_acceptance.py",
            ProofState.CODE_PRESENT,
            "explicit grade-ID permutation witness present; fresh current-head run pending"),
        FailureGate(
            "NO_LEGACY_BAV_RUNTIME_NAMESPACE",
            "bilqis_mlx/runtime/delivery/tests/test_no_legacy_bav_namespace.py",
            ProofState.CODE_PRESENT,
            "runtime namespace refusal witness present; fresh current-head run pending"),
    )
    projection = ConformanceProjection(
        tuple(rows), gates, "IN_PROGRESS", "NOT_CLAIMED")
    return {**projection.to_record(), "conformance_sha256": projection.digest()}


def published_boundary_record() -> dict:
    """Public-safe C15.2 authority, graph, branch and privacy boundary."""
    graph = local_graph_proof()
    privacy_text, privacy_sha = privacy_clause()
    return {
        "schema": "bilqis.bamf.delivery-evidence-boundary/v1",
        "branch": "codex/bamf02-c-runtime",
        "source_head": C15_3_RECONCILIATION_HEAD,
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
            "active_reconciliation_sha": C15_3_RECONCILIATION_HEAD,
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
        "fresh_behavioral_proof": "C15_3_FACTORY_WITNESSES_64_OF_64_PASS_AT_16117BFB",
    }


def published_roadmap_record() -> dict:
    """Current public C15 leaf/upstream projection, generated from frozen receipts."""
    return {
        "schema": "bilqis.bamf.delivery-roadmap-projection/v2",
        "source_reviewed_unified": REVIEWED_UNIFIED,
        "historical_issue_book_sha256": ISSUE_BOOK_DIGEST,
        "historical_workstack_sha256": SOURCE_DIGEST,
        "software_delivery_status": "IN_PROGRESS",
        "student_mastery_status": "NOT_CLAIMED",
        "leaves": [
            {"issue": 537, "key": "C15.1a", "head_sha": C15_1A_HEAD,
             "status": "DEVELOPMENT_RECEIPT",
             "final_gate": "EGM_AND_ACCEPTED_C13_C14"},
            {"issue": 538, "key": "C15.1b", "head_sha": C15_1B_HEAD,
             "status": "DEVELOPMENT_RECEIPT",
             "final_gate": "EGM_AND_ACCEPTED_C13_C14"},
            {"issue": 539, "key": "C15.2", "head_sha": C15_2_HEAD,
             "status": "DEVELOPMENT_RECEIPT",
             "final_gate": "EGM_AND_ACCEPTED_C13_C14"},
            {"issue": 540, "key": "C15.3", "head_sha": C15_3_RECONCILIATION_HEAD,
             "status": "DEVELOPMENT_RECEIPT_FACTORY_PASS",
             "final_gate": "ACCEPTED_C14_AND_FINAL_REQUALIFICATION"},
        ],
        "egm_repair_head": C15_EGM_CANDIDATE,
        "upstream": [
            {"issue": 385, "key": "C13",
             "head_sha": "9e06ea557c910bae7ecd879fe83f4d50aed84eb9",
             "status": "ACCEPTED_RELEASE_SCOPED_INTEGRATION"},
            {"issue": 386, "key": "C14",
             "head_sha": "29101af83aaa592ab1ace59c68bfdba153c7fb53",
             "status": "REVIEW_CLEAN_PENDING_HUMAN_PR_CHAIN"},
        ],
    }
