"""Cache source-local findings, never the final changed-file debt decision."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
from pathlib import Path
import subprocess

from .code_smell_rules import Finding, inspect_source
from .verification_ledger import VerificationLedger, fingerprint, source_fingerprint


def _valid_findings(payload, name: str) -> bool:
    if not isinstance(payload, list):
        return False
    return all(
        isinstance(item, dict)
        and set(item) == {"path", "line", "rule", "context"}
        and item["path"] == name
        and type(item["line"]) is int and item["line"] > 0
        and all(isinstance(item[k], str) for k in ("path", "rule", "context"))
        for item in payload
    )


class SourceInspection:
    def __init__(self, root: Path, ledger: VerificationLedger):
        self.root = root
        self.ledger = ledger
        algorithm = subprocess.run(
            ["git", "rev-parse", "--show-object-format"], cwd=root,
            capture_output=True, text=True, check=False,
        )
        self.algorithm = algorithm.stdout.strip() if algorithm.returncode == 0 else "sha256"
        self.checker = source_fingerprint((
            Path(__file__), Path(__file__).with_name("code_smell_rules.py"),
            Path(__file__).with_name("verification_ledger.py"),
            Path(__file__).parents[1] / "code_smell_audit.py",
        ))

    def current(self, name: str, path: Path) -> list[Finding]:
        raw = path.read_bytes()
        oid = hashlib.new(self.algorithm, f"blob {len(raw)}\0".encode() + raw).hexdigest()
        return self._inspect(name, oid, lambda: raw)

    def committed(self, name: str, oid: str) -> list[Finding]:
        return self._inspect(name, oid, lambda: subprocess.check_output(
            ["git", "--no-replace-objects", "cat-file", "blob", oid], cwd=self.root,
        ))

    def _inspect(self, name: str, oid: str, read) -> list[Finding]:
        key = fingerprint(self.checker, self.algorithm, name, oid)
        payload = self.ledger.lookup("code-smell", key, validate=lambda rows: _valid_findings(rows, name))
        if payload is not None:
            return [Finding(**item) for item in payload]
        source = read().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        findings = inspect_source(name, source)
        self.ledger.record("code-smell", key, [asdict(item) for item in findings])
        return findings
