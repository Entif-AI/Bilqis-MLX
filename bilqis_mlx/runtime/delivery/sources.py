"""Repository-authoritative inputs for BAMF delivery publication."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess

from .contracts import require
from .conformance import AuthorityIdentity


ROOT = Path(__file__).resolve().parents[3]
TASKS = ROOT / "docs" / "tasks" / "bamf-0.2"
ARCHITECTURE = ROOT / "docs" / "architecture" / "BAMF_0_2.md"
ISSUE_BOOK = TASKS / "ISSUE_BOOK.md"
WORKSTACK = TASKS / "workstack.json"
REGISTRY = TASKS / "children" / "registry.json"

# Physical test locations move as large owner modules are split. The workstack
# keeps the original logical owner surface for provenance; C15 binds each primary
# owner to the current executable test surface below. This is intentionally small
# and explicit so a future structural move fails closed instead of silently
# falling back to the generic runner.
_OWNER_TEST_REFS = (
    ("A01", "bilqis_mlx/semantics/tests/test_atlas_projection.py"),
    ("A03", "bilqis_mlx/semantics/tests/core/test_frame_schema.py"),
    ("A05", "bilqis_mlx/semantics/tests/test_frame_compiler.py"),
    ("A10", "bilqis_mlx/source_adapters/tests/test_evidence_frames.py"),
    ("A11", "bilqis_mlx/factory/tests/semantic_contrast/test_semantic_contrasts.py"),
    ("A13", "bilqis_mlx/semantics/tests/test_context_eligibility.py"),
    ("B01", "bilqis_mlx/runtime/tests/model/test_model_topology_v2.py"),
    ("B05", "bilqis_mlx/runtime/tests/depth/test_block_attnres.py"),
    ("B06", "bilqis_mlx/runtime/tests/model/test_atlas_refinement.py"),
    ("B07", "bilqis_mlx/learning/tests/test_atlas_engram_allocation.py"),
    ("B12", "bilqis_mlx/runtime/tests/model/optimization/test_atlas_optimizer.py"),
    ("B13", "bilqis_mlx/runtime/tests/custody/bamf_bundle/test_cold_resume_continuation.py"),
    ("B14", "bilqis_mlx/runtime/tests/model/attention/cache/test_atlas_cache_codec.py"),
    ("C01", "scripts/check_bamf_workstack.py"),
    ("C02", "bilqis_mlx/runtime/tests/batch/test_atlas_training_adapter.py"),
    ("C03", "bilqis_mlx/learning/tests/teaching/test_bamf_teacher.py"),
    ("C05", "bilqis_mlx/runtime/tests/capability/test_bamf_capability_retention.py"),
    ("C06", "bilqis_mlx/learning/_salience/tests/test_atlas_salience.py"),
    ("C08", "bilqis_mlx/runtime/tests/model/test_atlas_resources.py"),
    ("C09", "bilqis_mlx/runtime/tests/test_atlas_revalidation.py"),
)

_REQ = re.compile(r"BAMF-REQ-(\d{3})(?:/(\d{3}))?")
_PATH = re.compile(r"(?:bilqis_mlx|scripts|configs|tests)/[A-Za-z0-9_./-]+(?:\.py|\.json)")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_digest(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def workstack_items() -> tuple[dict, ...]:
    return tuple(_json(WORKSTACK)["items"])


def item_by_key(key: str) -> dict:
    return next(item for item in workstack_items() if item["key"] == key)


def child_by_key(key: str) -> dict:
    return next(item for item in _json(REGISTRY)["entries"] if item["key"] == key)


def authority_identity(owner_key: str) -> AuthorityIdentity:
    item = item_by_key(owner_key)
    issue_path = TASKS / "issues" / f"{owner_key}.md"
    require(file_digest(issue_path) == item["body_sha256"],
            "PUBLICATION_ISSUE_MIRROR_DIGEST")
    return AuthorityIdentity.from_authorities(
        source=WORKSTACK.read_bytes(), contract=ARCHITECTURE.read_bytes(),
        issue=issue_path.read_bytes())


def requirement_texts() -> dict[str, str]:
    """Expand the public continuity table into exact source-derived requirement text."""
    result: dict[str, str] = {}
    for line in ARCHITECTURE.read_text(encoding="utf-8").splitlines():
        match = _REQ.search(line)
        if not match or not line.startswith("| BAMF-REQ-"):
            continue
        first, second = match.groups()
        ids = (first,) if second is None else tuple(
            f"{number:03d}" for number in range(int(first), int(second) + 1))
        for number in ids:
            result[f"BAMF-REQ-{number}"] = line.strip()
    require(tuple(sorted(result)) == tuple(f"BAMF-REQ-{n:03d}" for n in range(1, 25)),
            "PUBLICATION_REQUIREMENT_TEXTS")
    return result


def fixture_source_text(claim_id: str, owner_key: str) -> str:
    """Return an exact public source line for a protected Fxx fixture obligation."""
    issue_path = TASKS / "issues" / f"{owner_key}.md"
    lines = issue_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        if claim_id in line and ("fixture" in line.lower() or "Predecessor trace" in line):
            return line.strip()
    for line in ISSUE_BOOK.read_text(encoding="utf-8").splitlines():
        if claim_id in line and "fixture" in line.lower():
            return line.strip()
    require(False, "PUBLICATION_FIXTURE_SOURCE_TEXT")
    return ""


def literal_test_ref(owner_key: str, claim_id: str) -> str:
    """Choose an existing literal test/config path from the source-owned work packet."""
    owner_ref = next((ref for key, ref in _OWNER_TEST_REFS if key == owner_key), None)
    if owner_ref is not None:
        require((ROOT / owner_ref).is_file(), "PUBLICATION_OWNER_TEST_REF")
        return owner_ref
    candidates = []
    for item in workstack_items():
        if item["key"] == owner_key or claim_id in item.get("tests", ""):
            candidates.extend(_PATH.findall(item.get("tests", "")))
    # The work packets spell commands as ``scripts/run_tests.py <test-path>``.
    # The executable fixture is the concrete test/config path, not the runner
    # wrapper itself. Prefer that source-owned fixture so execution receipts bind
    # the behavior being proved rather than a generic launcher.
    ordered = [candidate for candidate in candidates if candidate != "scripts/run_tests.py"]
    ordered += [candidate for candidate in candidates if candidate == "scripts/run_tests.py"]
    for candidate in ordered:
        if (ROOT / candidate).is_file():
            return candidate
    return f"BLOCKED_SOURCE_OWNER:{owner_key}:{claim_id}"


def expected_behavior(owner_key: str, claim_id: str) -> str:
    """Use independently authored acceptance text, never a generated template."""
    items = workstack_items()
    preferred = [item for item in items if claim_id in item.get("tests", "")]
    if not preferred:
        preferred = [item for item in items if item["key"] == owner_key]
    require(bool(preferred), "PUBLICATION_EXPECTED_BEHAVIOR_OWNER")
    text = preferred[0]["tests"].strip()
    return text.split("\n\n", 1)[0].strip()


@dataclass(frozen=True)
class LocalGraphProof:
    owner_count: int
    child_count: int
    node_count: int
    held_keys: tuple[str, ...]
    mirror_mismatches: tuple[str, ...]
    unknown_dependencies: tuple[str, ...]
    cycles: tuple[str, ...]

    @property
    def status(self) -> str:
        return "valid" if not (self.mirror_mismatches or self.unknown_dependencies
                                or self.cycles) else "invalid"


def local_graph_proof() -> LocalGraphProof:
    owners = workstack_items()
    children = tuple(_json(REGISTRY)["entries"])
    records = tuple((item, TASKS / "issues" / f"{item['key']}.md") for item in owners)
    records += tuple((item, TASKS / "children" / f"{item['key']}.md") for item in children)
    mismatches = tuple(item["key"] for item, path in records
                       if file_digest(path) != item["body_sha256"])
    entries = {item["key"]: item for item in (*owners, *children)}
    unknown = []
    cycles = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visiting:
            cycles.append(key)
            return
        if key in visited:
            return
        visiting.add(key)
        for dep in entries[key].get("deps", []):
            if dep not in entries:
                unknown.append(f"{key}->{dep}")
            else:
                visit(dep)
        visiting.remove(key)
        visited.add(key)

    for key in entries:
        visit(key)
    held = tuple(sorted(item["key"] for item in children
                        if item.get("resolution") == "held"))
    return LocalGraphProof(len(owners), len(children), len(entries), held,
                           tuple(sorted(mismatches)), tuple(sorted(unknown)),
                           tuple(sorted(set(cycles))))


def privacy_clause() -> tuple[str, str]:
    line = next(line.strip() for line in ARCHITECTURE.read_text(encoding="utf-8").splitlines()
                if "PRIVATE_REAL data stays outside public worktrees" in line)
    return line, sha256_bytes(line.encode())


def validate_executed_pass(row: object) -> bool:
    """Validate one PASS row against repository-owned authority and evidence sources."""
    from .conformance import ConformanceRow
    require(type(row) is ConformanceRow, "PUBLICATION_PASS_ROW_TYPE")
    evidence = row.evidence
    primary = row.owner_ref.split("/")[0]
    item = item_by_key(primary)
    normative = (requirement_texts()[row.claim_id]
                 if row.claim_id.startswith("BAMF-REQ-")
                 else fixture_source_text(row.claim_id, primary))
    fixture = literal_test_ref(primary, row.claim_id)
    require(not fixture.startswith("BLOCKED_SOURCE_OWNER:"),
            "PUBLICATION_PASS_FIXTURE_MISSING")
    require(evidence.normative_text == normative, "PUBLICATION_PASS_NORMATIVE")
    require(evidence.owner_issue == item["number"], "PUBLICATION_PASS_OWNER")
    require(evidence.contract_path ==
            "docs/architecture/BAMF_0_2.md#requirements-continuity",
            "PUBLICATION_PASS_CONTRACT")
    require(evidence.input_fixture == fixture, "PUBLICATION_PASS_FIXTURE")
    require(evidence.expected_behavior == expected_behavior(primary, row.claim_id),
            "PUBLICATION_PASS_EXPECTED")
    require(evidence.authority_identity == authority_identity(primary),
            "PUBLICATION_PASS_AUTHORITY")
    require(evidence.complete_for_pass(), "PUBLICATION_PASS_RECEIPT")
    require(evidence.run_receipt is not None
            and evidence.run_receipt.candidate_sha == evidence.owner_commit,
            "PUBLICATION_PASS_CANDIDATE")
    receipt_path = evidence.run_receipt.receipt_ref
    try:
        completed = subprocess.run(
            ["git", "show", f"{evidence.receipt_commit}:{receipt_path}"], cwd=ROOT,
            text=True, capture_output=True, check=False)
        require(completed.returncode == 0, "PUBLICATION_PASS_RECEIPT_COMMIT_FILE")
        receipt_record = json.loads(completed.stdout)
    except json.JSONDecodeError:
        require(False, "PUBLICATION_PASS_RECEIPT_FILE")
        raise AssertionError("unreachable")
    require(receipt_record == {
        "schema": evidence.run_receipt.schema,
        "receipt_ref": evidence.run_receipt.receipt_ref,
        "candidate_sha": evidence.run_receipt.candidate_sha,
        "fixture_sha256": evidence.run_receipt.fixture_sha256,
        "expected_sha256": evidence.run_receipt.expected_sha256,
        "observed_sha256": evidence.run_receipt.observed_sha256,
        "runner_sha256": evidence.run_receipt.runner_sha256,
        "disposition": evidence.run_receipt.disposition,
    }, "PUBLICATION_PASS_RECEIPT_FILE")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", evidence.owner_commit,
         evidence.receipt_commit], cwd=ROOT, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, check=False)
    require(ancestry.returncode == 0, "PUBLICATION_PASS_RECEIPT_ANCESTRY")
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{evidence.owner_commit}^{{commit}}"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False)
    require(completed.returncode == 0, "PUBLICATION_PASS_COMMIT")
    return True
