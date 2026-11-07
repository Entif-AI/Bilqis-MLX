from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.check_legacy_trainer_authority import (
    AUTHORITY_PATH,
    CANONICAL_BRANCH,
    CANONICAL_RUN,
    CANONICAL_STATE,
    CANONICAL_WORKTREE,
    validate_static,
)


def authority() -> dict:
    return {
        "schema": "bilqis.bamf.legacy-trainer-authority/v1",
        "version": "1.0.0",
        "effective_date": "2026-11-07",
        "purpose": "latest legacy trainer adaptation and compatibility oracle",
        "source_branch": CANONICAL_BRANCH,
        "source_worktree": CANONICAL_WORKTREE,
        "source_run": CANONICAL_RUN,
        "source_state": CANONICAL_STATE,
        "operator_preflight": "python3 -B scripts/check_legacy_trainer_authority.py --live",
        "historical_non_authoritative_runs": [
            {
                "name": "Prometheus",
                "run": "runs/codex-0001-prometheus",
                "disposition": "historical evidence only; never the latest legacy-trainer adaptation source",
            }
        ],
    }


class LegacyTrainerAuthorityTests(unittest.TestCase):
    def make_root(self) -> Path:
        root = Path(tempfile.mkdtemp())
        (root / AUTHORITY_PATH.parent).mkdir(parents=True)
        (root / AUTHORITY_PATH).write_text(json.dumps(authority()))
        (root / "AGENTS.md").write_text(
            f"BAMF02:LEGACY-TRAINER-AUTHORITY:20261107\nlatest legacy trainer: {CANONICAL_RUN}\n"
        )
        readme = root / "docs/tasks/bamf-0.2/README.md"
        readme.parent.mkdir(parents=True, exist_ok=True)
        readme.write_text(f"latest legacy trainer: {CANONICAL_RUN}\n")
        (root / "docs/evidence/bamf").mkdir(parents=True)
        return root

    def test_clean_authority_passes(self) -> None:
        root = self.make_root()
        self.assertEqual(validate_static(root), [])

    def test_stale_prometheus_run_is_rejected_on_current_bamf_surface(self) -> None:
        root = self.make_root()
        receipt = root / "docs/evidence/bamf/receipt.md"
        receipt.write_text("legacy source: runs/codex-0001-prometheus\n")
        self.assertTrue(any("LEGACY_TRAINER_STALE_RUN_REFERENCE" in p for p in validate_static(root)))

    def test_legacy_trainer_worklog_must_name_canonical_run(self) -> None:
        root = self.make_root()
        receipt = root / "docs/evidence/bamf/receipt.md"
        receipt.write_text("Adapt this issue against the latest legacy trainer.\n")
        self.assertTrue(any("LEGACY_TRAINER_SOURCE_OMITTED" in p for p in validate_static(root)))

    def test_prometheus_cannot_be_presented_as_current_training_baseline(self) -> None:
        root = self.make_root()
        receipt = root / "docs/evidence/bamf/receipt.md"
        receipt.write_text("Use the Prometheus training run as the baseline for this adapter.\n")
        self.assertTrue(any("LEGACY_TRAINER_PROMETHEUS_AMBIGUITY" in p for p in validate_static(root)))

    def test_explicit_historical_prometheus_evidence_is_allowed(self) -> None:
        root = self.make_root()
        receipt = root / "docs/evidence/bamf/receipt.md"
        receipt.write_text("Historical Prometheus training evidence is non-authoritative for adaptation.\n")
        self.assertEqual(validate_static(root), [])

    def test_explicit_not_prometheus_correction_is_allowed(self) -> None:
        root = self.make_root()
        receipt = root / "docs/evidence/bamf/receipt.md"
        receipt.write_text(f"Use {CANONICAL_RUN}, not the Prometheus training run.\n")
        self.assertEqual(validate_static(root), [])


if __name__ == "__main__":
    unittest.main()
