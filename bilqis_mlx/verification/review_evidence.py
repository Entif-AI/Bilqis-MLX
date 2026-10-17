"""Read-only verification of independently pinned curriculum claim receipts.

The expected manifest hash is supplied by the reviewer/operator, outside the
proposal. It attests reviewed claim support; hashing source bytes alone cannot
establish that support. This module verifies the attestation's exact inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

SCHEMA = "bilqis.review-evidence/v1"

VERIFIER_FILES = (
    "cli.py", "curriculum.py", "curriculum_compiler.py", "grade_transition.py",
    "next_grade_review.py", "school.py", "semantics/core.py", "semantics/functions.py",
    "verification/cases.py", "verification/expressions.py",
    "verification/review_evidence.py", "verification/curriculum.py",
)


def verifier_digest() -> str:
    """Bind attestations to the source-only checks that consume them.

    Source-specific adapter implementations belong in the receipt's artifacts.
    The independently supplied manifest fingerprint governs both bindings.
    """
    root = Path(__file__).resolve().parents[1]
    payload = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
               for name in VERIFIER_FILES}
    return hashlib.sha256(json.dumps(payload, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _read_artifact(root: Path, name: str) -> bytes:
    """Only regular files inside the explicitly supplied artifact root qualify."""
    if not _text(name):
        raise ValueError("UNSAFE_PATH")
    relative = PurePosixPath(name)
    if relative.is_absolute() or any(part in ("..", ".") for part in name.split("/")):
        raise ValueError("UNSAFE_PATH")
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("UNSAFE_PATH")
    if not path.is_file():
        raise ValueError("ARTIFACT_MISSING")
    return path.read_bytes()


@dataclass(frozen=True)
class EvidenceContext:
    manifest: Path
    expected_sha256: str
    artifact_root: Path

    def inspect(self, *, grade: str, parent_release: str, semantic_release: str,
                subject_sha256: str) -> "EvidenceInventory":
        """Re-read manifest and source artifacts at every assessment."""
        if not _sha(self.expected_sha256):
            return EvidenceInventory({}, ("REVIEW_EVIDENCE_TRUST_ROOT_MISSING",))
        try:
            if self.manifest.is_symlink():
                raise ValueError("UNSAFE_PATH")
            raw = self.manifest.read_bytes()
            if hashlib.sha256(raw).hexdigest() != self.expected_sha256:
                return EvidenceInventory({}, ("REVIEW_EVIDENCE_MANIFEST_DRIFT",))
            data = json.loads(raw)
        except (OSError, ValueError, UnicodeError):
            return EvidenceInventory({}, ("REVIEW_EVIDENCE_MANIFEST_UNREADABLE",))
        if not isinstance(data, dict) or data.get("schema") != SCHEMA:
            return EvidenceInventory({}, ("REVIEW_EVIDENCE_SCHEMA_INVALID",))
        try:
            if data.get("verifier_sha256") != verifier_digest():
                return EvidenceInventory({}, ("REVIEW_EVIDENCE_VERIFIER_DRIFT",))
        except OSError:
            return EvidenceInventory({}, ("REVIEW_EVIDENCE_VERIFIER_UNREADABLE",))
        for field, expected in (("grade", grade), ("parent_release", parent_release),
                                ("semantic_release", semantic_release),
                                ("subject_sha256", subject_sha256)):
            if not _text(expected) or data.get(field) != expected:
                return EvidenceInventory({}, ("REVIEW_EVIDENCE_SCOPE_MISMATCH:" + field,))
        receipts = data.get("receipts")
        if not isinstance(receipts, list) or not receipts:
            return EvidenceInventory({}, ("REVIEW_EVIDENCE_RECEIPTS_MISSING",))
        verified, errors, seen, fingerprints, receipt_errors = {}, [], set(), {}, {}
        for receipt in receipts:
            identity = receipt.get("id") if isinstance(receipt, dict) else None
            if (not _text(identity) or not identity.startswith("receipt:") or
                    identity in seen):
                errors.append("REVIEW_EVIDENCE_RECEIPT_IDENTITY_INVALID")
                continue
            seen.add(identity)
            problems = []
            claims = receipt.get("claims")
            if (receipt.get("qualification") != "INDEPENDENTLY_QUALIFIED" or
                    not _text(receipt.get("producer")) or
                    not _text(receipt.get("reviewer")) or
                    receipt["producer"] == receipt["reviewer"] or
                    not isinstance(claims, list) or not claims or
                    not all(_text(claim) for claim in claims)):
                receipt_errors[identity] = ("REVIEW_EVIDENCE_UNQUALIFIED:" + identity,)
                continue
            artifacts = receipt.get("artifacts")
            if not isinstance(artifacts, list) or not artifacts:
                receipt_errors[identity] = ("REVIEW_EVIDENCE_ARTIFACTS_MISSING:" + identity,)
                continue
            valid = True
            for artifact in artifacts:
                try:
                    if (not isinstance(artifact, dict) or
                            not _sha(artifact.get("sha256")) or
                            not _text(artifact.get("revision")) or
                            not _text(artifact.get("source"))):
                        raise ValueError("ARTIFACT_INVALID")
                    content = _read_artifact(Path(self.artifact_root), artifact.get("path"))
                    if hashlib.sha256(content).hexdigest() != artifact["sha256"]:
                        raise ValueError("ARTIFACT_DRIFT")
                except (OSError, ValueError) as exc:
                    code = str(exc) if isinstance(exc, ValueError) else "ARTIFACT_UNREADABLE"
                    problems.append("REVIEW_EVIDENCE_" + code + ":" + identity)
                    valid = False
            if valid:
                verified[identity] = frozenset(claims)
                fingerprints[identity] = hashlib.sha256(json.dumps(
                    receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            else:
                receipt_errors[identity] = tuple(problems)
        scope = {key: data[key] for key in ("grade", "parent_release", "semantic_release",
                                          "subject_sha256", "verifier_sha256")}
        return EvidenceInventory(verified, tuple(dict.fromkeys(errors)), self.expected_sha256,
                                 fingerprints, receipt_errors, scope)


@dataclass(frozen=True)
class EvidenceInventory:
    receipts: dict[str, frozenset[str]]
    blockers: tuple[str, ...]
    manifest_sha256: str | None = None
    fingerprints: dict[str, str] | None = None
    receipt_errors: dict[str, tuple[str, ...]] | None = None
    scope: dict | None = None

    def supports(self, references, claim: str) -> bool:
        return (isinstance(references, list) and bool(references) and
                all(isinstance(ref, str) and claim in self.receipts.get(ref, ())
                    for ref in references))

    def problems_for(self, references) -> tuple[str, ...]:
        return tuple(problem for ref in references if isinstance(ref, str)
                     for problem in (self.receipt_errors or {}).get(ref, ()))

    def digest_for(self, references) -> str | None:
        """A later phase's added evidence cannot rewrite earlier review scope."""
        if not references or not all(isinstance(ref, str) and ref in self.receipts for ref in references):
            return None
        payload = {"scope": self.scope, "receipts": {
            ref: (self.fingerprints or {})[ref] for ref in sorted(set(references))}}
        return hashlib.sha256(json.dumps(payload, sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()
