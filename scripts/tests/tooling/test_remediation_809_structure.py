"""Regression coverage for the remediation #809 structural verifier."""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _verifier_module():
    root = Path(__file__).resolve().parents[3]
    path = root / "scripts" / "remediation_809" / "verify_structure.py"
    spec = importlib.util.spec_from_file_location("remediation_809_verify_structure", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_removed_legacy_limit_path_does_not_crash_verifier(monkeypatch, tmp_path):
    verifier = _verifier_module()
    monkeypatch.setattr(verifier, "ROOT", tmp_path)
    monkeypatch.setattr(verifier, "LIMITS", (("removed.py", 239),))
    monkeypatch.setattr(verifier, "DIRECTORIES", ())
    monkeypatch.setattr(verifier.subprocess, "run", lambda *_args, **_kwargs: None)

    assert verifier.main() == 0
