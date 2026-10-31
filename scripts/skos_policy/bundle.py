"""Content identity and trusted-receipt checks for the Ithkuil/SKOS test bundle."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


RECEIPT_SCHEMA = "bilqis.skos-test-bundle/v1"
RECEIPT_PATH = Path("docs/evidence/development/skos_test_bundle_v1.json")
DEFAULT_FULL_SHARD_COUNT = 8

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

CANARY_TESTS = (
    "lib/ithkuil/tests/test_skos_canonical.py",
    "lib/ithkuil/tests/test_skos_identity.py",
    "lib/ithkuil/tests/test_skos_shapes.py",
)

IGNORED_NAMES = frozenset({"__pycache__", ".DS_Store"})


@dataclass(frozen=True)
class BundleStatus:
    verified: bool
    sha256: str
    expected_sha256: str | None
    file_count: int
    expected_file_count: int | None
    byte_count: int
    expected_byte_count: int | None
    reason: str


@dataclass(frozen=True)
class TestPlan:
    action: str
    tests: tuple[str, ...] = ()
    reason: str = ""
    sha256: str | None = None


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
        return BundleStatus(
            False, actual, None, file_count, None, byte_count, None,
            "RECEIPT_MISSING")
    try:
        receipt = json.loads(receipt_path.read_text())
    except (OSError, json.JSONDecodeError):
        return BundleStatus(
            False, actual, None, file_count, None, byte_count, None,
            "RECEIPT_INVALID")
    expected_sha = receipt.get("sha256")
    expected_files = receipt.get("file_count")
    expected_bytes = receipt.get("byte_count")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        reason = "RECEIPT_SCHEMA_MISMATCH"
    elif expected_sha != actual:
        reason = "BUNDLE_DIGEST_CHANGED"
    elif expected_files != file_count:
        reason = "BUNDLE_FILE_COUNT_CHANGED"
    elif expected_bytes != byte_count:
        reason = "BUNDLE_BYTE_COUNT_CHANGED"
    else:
        reason = "VERIFIED_BUNDLE_CURRENT"
    return BundleStatus(
        reason == "VERIFIED_BUNDLE_CURRENT",
        actual,
        expected_sha,
        file_count,
        expected_files,
        byte_count,
        expected_bytes,
        reason,
    )


def is_bundle_path(path: str) -> bool:
    return (
        path.startswith("lib/ithkuil/")
        or path.startswith("skills/ithkuil-ingestion/")
        or path == "scripts/package_ithkuil_skill.py"
    )


def semantic_test_files(root: Path) -> tuple[str, ...]:
    return tuple(
        test.relative_to(root).as_posix()
        for test in sorted((root / "lib/ithkuil/tests").rglob("test_skos_*.py"))
    )
