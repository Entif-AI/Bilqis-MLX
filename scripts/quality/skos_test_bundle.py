"""Content-addressed bundle identity and verification receipt ownership."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


RECEIPT_SCHEMA = "bilqis.skos-test-bundle/v1"
RECEIPT_PATH = Path("docs/evidence/development/skos_test_bundle_v1.json")

BUNDLE_PATHS = (
    Path("lib/ithkuil/src"),
    Path("lib/ithkuil/_data"),
    Path("lib/ithkuil/tests"),
    Path("lib/ithkuil/ingestion_contract.json"),
    Path("lib/ithkuil/requirements-extraction.txt"),
    Path("lib/ithkuil/requirements-falkor.txt"),
    Path("lib/ithkuil/requirements-semantic.txt"),
    Path("scripts/package_ithkuil_skill.py"),
    Path("skills/ithkuil-ingestion"),
)

IGNORED_NAMES = frozenset({"__pycache__", ".DS_Store"})


@dataclass(frozen=True)
class BundleStatus:
    verified: bool
    sha256: str
    expected_sha256: str | None
    file_count: int
    byte_count: int
    reason: str


def _files_under(root: Path, relative: Path) -> tuple[Path, ...]:
    path = root / relative
    if not path.exists():
        return ()
    if path.is_file():
        return (path,)
    return tuple(sorted(
        candidate for candidate in path.rglob("*")
        if candidate.is_file()
        and not any(part in IGNORED_NAMES for part in candidate.relative_to(root).parts)
        and candidate.suffix != ".pyc"
    ))


def bundle_files(root: Path) -> tuple[Path, ...]:
    files = []
    for relative in BUNDLE_PATHS:
        files.extend(_files_under(root, relative))
    return tuple(sorted(set(files)))


def bundle_fingerprint(root: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    files = bundle_files(root)
    byte_count = 0
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        payload = path.read_bytes()
        byte_count += len(payload)
        digest.update(relative)
        digest.update(b"\0")
        digest.update(str(len(payload)).encode("ascii"))
        digest.update(b"\0")
        digest.update(payload)
        digest.update(b"\0")
    return digest.hexdigest(), len(files), byte_count


def bundle_status(root: Path, receipt_path: Path | None = None) -> BundleStatus:
    receipt_path = receipt_path or root / RECEIPT_PATH
    actual, file_count, byte_count = bundle_fingerprint(root)
    if not receipt_path.exists():
        return BundleStatus(False, actual, None, file_count, byte_count, "RECEIPT_MISSING")
    try:
        receipt = json.loads(receipt_path.read_text())
    except (OSError, json.JSONDecodeError):
        return BundleStatus(False, actual, None, file_count, byte_count, "RECEIPT_INVALID")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        return BundleStatus(
            False, actual, receipt.get("sha256"), file_count, byte_count,
            "RECEIPT_SCHEMA_MISMATCH")
    expected = receipt.get("sha256")
    verified = expected == actual
    return BundleStatus(
        verified, actual, expected, file_count, byte_count,
        "VERIFIED_BUNDLE_UNCHANGED" if verified else "BUNDLE_DIGEST_CHANGED")


def write_receipt(root: Path, *, release_commit: str, evidence: str) -> dict:
    digest, file_count, byte_count = bundle_fingerprint(root)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "sha256": digest,
        "file_count": file_count,
        "byte_count": byte_count,
        "release_commit": release_commit,
        "evidence": evidence,
    }
    path = root / RECEIPT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    return receipt
