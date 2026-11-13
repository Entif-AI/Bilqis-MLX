"""C15 component, issue, commit, proof, command and EGM publication receipts."""
from __future__ import annotations

from .codec import seal_manifest
from .conformance import load_conformance_record
from .contracts import (
    CommitReceipt,
    ComponentReceipt,
    EgmReceipt,
    EgmStatus,
    IssueReceipt,
    OperatorCommandReceipt,
    ProofReceipt,
    ProofState,
    ReceiptStatus,
)
from .integration import integrate_delivery_receipts
from .publication_conformance import published_conformance_record
from .publication_state import (
    C15_1A_HEAD,
    C15_1B_HEAD,
    C15_2_HEAD,
    C15_EGM_CANDIDATE,
    C15_EGM_REPORT_HEAD,
    C15_FINAL_CANDIDATE,
    C15_REQUALIFICATION_RECEIPT_COMMIT,
    ISSUE_BOOK_DIGEST,
    REVIEWED_UNIFIED,
    SOURCE_DIGEST,
)


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
        ComponentReceipt("C14", 386, "d81c1ae5ab951bfbefb5d72e9dc04f9f746bc9b1",
                         ReceiptStatus.ACCEPTED, "issue:386#issuecomment-6865294741"),
        ComponentReceipt("C16", 382, "c672c62113108695a2a60cd0eb0d7f19d085f838",
                         ReceiptStatus.ACCEPTED, "issue:382#issuecomment-6832648874"),
        ComponentReceipt("architecture", 540, C15_FINAL_CANDIDATE,
                         ReceiptStatus.ACCEPTED,
                         f"git:{C15_FINAL_CANDIDATE}:docs/architecture/BAMF_0_2.md"),
        ComponentReceipt("codec", 375,
                         "1265200be9bac5b97a3aecd0e82127af1dd4d98ca86da6829ea0ce0e9b69c000",
                         ReceiptStatus.ACCEPTED,
                         "bilqis_mlx/runtime/_model/cache/atlas_cache_codec.py"),
        ComponentReceipt("compiler", 357,
                         "acafc03e20353d55bd02c4a0d70ab3d7b36c1558632932b0d75b1cf9399de3a1",
                         ReceiptStatus.ACCEPTED,
                         "bilqis_mlx/runtime/_custody/bamf_bundle/vocabulary/compiler_binding.py"),
        ComponentReceipt("delivery-tests", 539, C15_FINAL_CANDIDATE,
                         ReceiptStatus.ACCEPTED,
                         f"git:{C15_FINAL_CANDIDATE}:bilqis_mlx/runtime/delivery/tests"),
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
                     "dd63880fdfde9d01eccbbff876e39828dbded3f6", "issue:375#issuecomment-6800933565"),
        IssueReceipt(381, "C12", "CLOSED", ReceiptStatus.ACCEPTED,
                     "516725b6170f258ad86b0c5d4ca050907238e59d", "issue:381#issuecomment-6754534350"),
        IssueReceipt(382, "C16", "CLOSED", ReceiptStatus.ACCEPTED,
                     "c672c62113108695a2a60cd0eb0d7f19d085f838", "issue:382#issuecomment-6832648874"),
        IssueReceipt(384, "C11", "CLOSED", ReceiptStatus.ACCEPTED,
                     "ce09a0c1887069385b903ac10a4d576d22d04881", "issue:384#issuecomment-6840426430"),
        IssueReceipt(385, "C13", "CLOSED", ReceiptStatus.ACCEPTED,
                     "9e06ea557c910bae7ecd879fe83f4d50aed84eb9", "pull:1042"),
        IssueReceipt(386, "C14", "CLOSED", ReceiptStatus.ACCEPTED,
                     REVIEWED_UNIFIED, "issue:386#issuecomment-6865294741"),
        IssueReceipt(537, "C15.1a", "OPEN", ReceiptStatus.PROVISIONAL,
                     C15_1A_HEAD, "issue:537#issuecomment-6856503488"),
        IssueReceipt(538, "C15.1b", "OPEN", ReceiptStatus.PROVISIONAL,
                     C15_1B_HEAD, "issue:538#issuecomment-6856845206"),
        IssueReceipt(539, "C15.2", "OPEN", ReceiptStatus.PROVISIONAL,
                     C15_2_HEAD, "issue:539#issuecomment-6857007014"),
        IssueReceipt(540, "C15.3", "OPEN", ReceiptStatus.PROVISIONAL,
                     C15_FINAL_CANDIDATE, "docs/evidence/bamf/delivery/runs/index.json"),
    )
    return tuple(sorted(rows, key=lambda item: item.issue))


def _commit_receipts() -> tuple[CommitReceipt, ...]:
    rows = (
        CommitReceipt("0ae919779e1de44f5c7c96e911b3f61780099e21", 384, "C11 accepted integration"),
        CommitReceipt("5166aca71f01f09cfb4e533d61dc41e53a987726", 375, "B14 accepted integration"),
        CommitReceipt("516725b6170f258ad86b0c5d4ca050907238e59d", 381, "C12 accepted integration"),
        CommitReceipt(C15_1A_HEAD, 537, "C15.1a development checkpoint"),
        CommitReceipt(C15_1B_HEAD, 538, "C15.1b development checkpoint"),
        CommitReceipt(C15_2_HEAD, 539, "C15.2 development checkpoint"),
        CommitReceipt(C15_FINAL_CANDIDATE, 540, "C15 final tested candidate"),
        CommitReceipt(C15_REQUALIFICATION_RECEIPT_COMMIT, 540,
                      "C15 immutable requalification receipt custody"),
        CommitReceipt("4b486268825f07330c4bd8147ca2439a36be5fee", 385,
                      "C13 accepted release-scoped handoff"),
        CommitReceipt("d81c1ae5ab951bfbefb5d72e9dc04f9f746bc9b1", 386,
                      "C14 accepted continuing-development program"),
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
        ProofReceipt("c14.training-program", ProofState.EXECUTED_PASS,
                     "bilqis.bamf.developmental-program/v1", "bilqis.bamf.training-program-proof/v1",
                     "issue:386#issuecomment-6865294741",
                     "all C14 BAMF-0.2 descendants integrated through PR #1048; fresh parent acceptance 18/18 PASS on reviewed unified de84266ba3db79b6545ff484f3268a99ea8872f6"),
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
        OperatorCommandReceipt("cold-resume",
            ("npm", "run", "train", "--", "--human-run", "--resume", "--run-dir",
             "<accepted-bamf-run>"), ProofState.EXECUTED_PASS,
            "bilqis_mlx/presentation/operator_cli/tests/bamf_lifecycle/test_bamf_resume.py",
            "issue:384#issuecomment-6840426430"),
        OperatorCommandReceipt("owner-start",
            ("npm", "run", "train", "--", "--human-run", "--resume", "--run-dir",
             "/absolute/path/to/bamf-run", "--minutes", "90", "--reserve-gib", "100",
             "--max-visits", "1"), ProofState.EXECUTED_PASS,
            "bilqis_mlx/presentation/operator_cli/tests/bamf_lifecycle/test_bamf_resume.py",
            "docs/operations/BAMF_0_2_RUNBOOK.md"),
        OperatorCommandReceipt("preflight",
            ("npm", "run", "train", "--", "--dry-run", "--model-topology",
             "configs/models/bamf-0.2.json", "--atlas-release-manifest", "<manifest.json>",
             "--run-dir", "<new-bamf-run>"), ProofState.EXECUTED_PASS,
            "bilqis_mlx/presentation/operator_cli/tests/test_bamf_preflight.py",
            "issue:384#issuecomment-6840426430"),
        OperatorCommandReceipt("read-only-status",
            ("npm", "run", "dashboard", "--", "--run-dir", "/absolute/path/to/run",
             "--once", "--atlas-details"), ProofState.EXECUTED_PASS,
            "bilqis_mlx/presentation/tests/test_operator_dashboard_events.py",
            "docs/operations/BAMF_0_2_RUNBOOK.md"),
    )
    return tuple(sorted(rows, key=lambda item: item.command_id))


def published_manifest_record() -> dict:
    """Return the receipt-composed, content-addressed C15 delivery manifest."""
    egm = tuple(EgmReceipt(
        name, EgmStatus.PASS, C15_EGM_CANDIDATE,
        f"git:{C15_EGM_REPORT_HEAD}:docs/evidence/bamf/delivery/egm-c15-537-539-20261113.md")
        for name in ("codebase-details", "implementation-readiness"))
    conformance = load_conformance_record(published_conformance_record())
    manifest = integrate_delivery_receipts(
        components=_component_receipts(), issues=_issue_receipts(),
        commits=_commit_receipts(), proofs=_proof_receipts(), egm=egm,
        operator_commands=_commands(), conformance=conformance)
    return seal_manifest(manifest)
