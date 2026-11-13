"""Deterministic public-safe C15.1b delivery publication."""
from __future__ import annotations

from bilqis_mlx.runtime.delivery import (
    CommitReceipt, ComponentReceipt, EgmReceipt, EgmStatus, IssueReceipt,
    OperatorCommandReceipt, ProofReceipt, ProofState, ReceiptStatus,
    integrate_delivery_receipts, seal_manifest,
)

from .conformance import ConformanceProjection, ConformanceRow, required_claim_ids

PINNED_EGM = "b3a35956759bf7f024af2ff061b2e0b44b438e4c"
C15_1A_HEAD = "4759336facf7a3482254b32c8647013ae447f074"


def _component_receipts() -> tuple[ComponentReceipt, ...]:
    rows = (
        ComponentReceipt("B14", 375, "dd63880fdfde9d01eccbbff876e39828dbded3f6",
                         ReceiptStatus.ACCEPTED, "issue:375#issuecomment-6800933565"),
        ComponentReceipt("C11", 384, "ce09a0c1887069385b903ac10a4d576d22d04881",
                         ReceiptStatus.ACCEPTED, "issue:384#issuecomment-6840426430"),
        ComponentReceipt("C12", 381, "516725b6170f258ad86b0c5d4ca050907238e59d",
                         ReceiptStatus.ACCEPTED, "issue:381#issuecomment-6754534350"),
        ComponentReceipt("C13", 385, "1150f7d8ca65b564906150c266c3b261ccb3b030",
                         ReceiptStatus.PROVISIONAL, "issue:528#issuecomment-6837301659"),
        ComponentReceipt("C14", 386, "77006d2370a16e0bfb4ca1a10cc516a6e4d011f8",
                         ReceiptStatus.PROVISIONAL, "issue:532#issuecomment-6856445395"),
        ComponentReceipt("C16", 382, "c672c62113108695a2a60cd0eb0d7f19d085f838",
                         ReceiptStatus.ACCEPTED, "issue:382#issuecomment-6832648874"),
        ComponentReceipt("architecture", 387,
                         "264d46cf51635f42e48befe09401588f833d1312e3f6f6e995d02246f08d1d5c",
                         ReceiptStatus.ACCEPTED, "docs/architecture/BAMF_0_2.md"),
        ComponentReceipt("codec", 375,
                         "1265200be9bac5b97a3aecd0e82127af1dd4d98ca86da6829ea0ce0e9b69c000",
                         ReceiptStatus.ACCEPTED,
                         "bilqis_mlx/runtime/_model/cache/atlas_cache_codec.py"),
        ComponentReceipt("compiler", 357,
                         "acafc03e20353d55bd02c4a0d70ab3d7b36c1558632932b0d75b1cf9399de3a1",
                         ReceiptStatus.ACCEPTED,
                         "bilqis_mlx/runtime/_custody/bamf_bundle/vocabulary/compiler_binding.py"),
        ComponentReceipt("delivery-tests", 538, C15_1A_HEAD,
                         ReceiptStatus.PROVISIONAL,
                         "bilqis_mlx/runtime/delivery/tests"),
        ComponentReceipt("factory-head", 358, "0b9b6d8589e7cea1fcd03aeac270b2488736d2a2",
                         ReceiptStatus.ACCEPTED, "git:bilqis_mlx/factory"),
        ComponentReceipt("issue-book", 341,
                         "21a82b966c52ad13480b7021e9163efaacc7f6f70c9c4eac5d7277f05d355425",
                         ReceiptStatus.ACCEPTED, "docs/tasks/bamf-0.2/ISSUE_BOOK.md"),
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
        ComponentReceipt("workstack", 341,
                         "e028a9018c39c87f372082900e49bf00576211f490d9eb84a3eb14ab28614057",
                         ReceiptStatus.ACCEPTED, "docs/tasks/bamf-0.2/workstack.json"),
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
        IssueReceipt(385, "C13", "OPEN", ReceiptStatus.PROVISIONAL,
                     "1150f7d8ca65b564906150c266c3b261ccb3b030",
                     "issue:528#issuecomment-6837301659"),
        IssueReceipt(386, "C14", "OPEN", ReceiptStatus.PROVISIONAL,
                     "77006d2370a16e0bfb4ca1a10cc516a6e4d011f8",
                     "issue:532#issuecomment-6856445395"),
        IssueReceipt(537, "C15.1a", "OPEN", ReceiptStatus.PROVISIONAL,
                     C15_1A_HEAD, "issue:537#issuecomment-6856503488"),
        IssueReceipt(538, "C15.1b", "OPEN", ReceiptStatus.PROVISIONAL,
                     C15_1A_HEAD, "issue:538"),
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
        ProofReceipt("c13.integrated-learning", ProofState.BLOCKED,
                     "bilqis.c13.episode-binding-generator/v1", "bilqis.c13.acceptance/v1",
                     "issue:528#issuecomment-6837301659",
                     "source authority landed later; disposable candidate/rollback/cold-resume not yet accepted"),
        ProofReceipt("c14.training-program", ProofState.BLOCKED,
                     "bilqis.bamf.developmental-program/v1", "bilqis.bamf.training-program-proof/v1",
                     "issue:532#issuecomment-6856445395",
                     "C14.1a review-clean; remaining C14 leaves and C13 receipt pending"),
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
    egm = tuple(EgmReceipt(name, EgmStatus.PENDING, C15_1A_HEAD,
                           "EGM_PENDING:C15.1a-C15.2")
                for name in ("codebase-details", "implementation-readiness"))
    manifest = integrate_delivery_receipts(
        components=_component_receipts(), issues=_issue_receipts(),
        commits=_commit_receipts(), proofs=_proof_receipts(), egm=egm,
        operator_commands=_commands())
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
_BLOCKED = {
    "BAMF-REQ-015", "BAMF-REQ-016", "BAMF-REQ-017", "BAMF-REQ-019",
    "BAMF-REQ-023", "BAMF-REQ-024", "F05", "F12", "F16", "F20",
}


def published_conformance_record() -> dict:
    rows = []
    for index, claim_id in enumerate(required_claim_ids()):
        owner = _REQ_OWNERS[index] if index < 24 else _FIXTURE_OWNERS[index - 24]
        if claim_id == "F15":
            state = ProofState.REQUALIFICATION_REQUIRED
            test_ref = "bilqis_mlx/runtime/tests/correction/test_atlas_stale_replay.py"
        elif claim_id in _BLOCKED:
            state = ProofState.BLOCKED
            test_ref = "blocked:C13/C14 accepted integrated witness"
        else:
            state = ProofState.CODE_PRESENT
            test_ref = f"docs/tasks/bamf-0.2/workstack.json:{owner}.tests"
        rows.append(ConformanceRow(
            claim_id, owner, "docs/architecture/BAMF_0_2.md#requirements-continuity",
            test_ref, state))
    projection = ConformanceProjection(
        tuple(rows), "IN_PROGRESS", "NOT_CLAIMED")
    return {**projection.to_record(), "conformance_sha256": projection.digest()}
