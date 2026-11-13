#!/usr/bin/env python3
"""Regenerate the deterministic public-safe C15 delivery projection."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from bilqis_mlx.runtime.delivery.publication import (
    published_boundary_record,
    published_conformance_record,
    published_manifest_record,
    published_roadmap_record,
)

OUT = ROOT / "docs/evidence/bamf/delivery"


def _write(name: str, value: dict) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown(manifest: dict, conformance: dict) -> str:
    lines = [
        "# BAMF-0.2 delivery conformance projection — 13 November 2026",
        "",
        "Issue: #539 (`C15.2`), integrated by #540 (`C15.3`).",
        "",
        f"- Manifest digest: `{manifest['manifest_sha256']}`",
        f"- Conformance digest: `{conformance['conformance_sha256']}`",
        f"- Software delivery: **{conformance['software_delivery_status']}**",
        f"- Student full-atlas mastery: **{conformance['student_mastery_status']}**",
        "",
        "## Global refusal gates",
        "",
        "| Gate | State | Witness | Observation |",
        "| --- | --- | --- | --- |",
    ]
    for gate in conformance["failure_gates"]:
        lines.append(
            f"| {_cell(gate['gate_id'])} | {_cell(gate['state'])} | "
            f"`{_cell(gate['test_ref'])}` | {_cell(gate['observed'])} |")
    lines += [
        "",
        "## Requirement and negative-fixture matrix",
        "",
        "| Claim | Source-derived obligation | Owner issue | State | Literal fixture / blocker | Observed | Run receipt | Reviewer |",
        "| --- | --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in conformance["rows"]:
        evidence = row["evidence"]
        receipt = evidence["run_receipt"]
        receipt_ref = "none" if receipt is None else f"`{receipt['receipt_ref']}`"
        lines.append(
            f"| {_cell(row['claim_id'])} | {_cell(evidence['normative_text'])} | "
            f"#{evidence['owner_issue']} | {_cell(row['state'])} | "
            f"`{_cell(row['test_ref'])}` | {_cell(evidence['observed_output'])} | "
            f"{receipt_ref} | {_cell(evidence['reviewer_decision'])} |")
    lines += [
        "",
        "Every row binds a repository-derived authority identity over the current workstack bytes, architecture bytes, and direct owner issue-mirror bytes. Requirement wording comes from the public continuity table; negative-fixture wording comes from the public owner/issue-book fixture contract. Expected behavior comes from independently authored workstack acceptance text.",
        "",
        "`EXECUTED_PASS` requires a structured `bilqis.bamf.execution-receipt/v2` whose candidate, fixture, expected, observed and runner digests recompute from literal evidence. The tested candidate commit and the later attestation commit are distinct identities: the receipt binds `candidate_sha` to the tested implementation, while `receipt_commit` identifies a descendant Git tree that actually contains the immutable receipt blob. Authority-byte drift forces `REQUALIFICATION_REQUIRED`; explicit failure gates take precedence. `READY_FOR_OWNER_MERGE`/`DELIVERED` remains impossible until all 44 rows and both refusal gates are `EXECUTED_PASS`.",
        "",
        "Protected `PRIVATE_REAL` evidence remains outside public artifacts. Full-atlas student mastery is not claimed by software-delivery closure.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    manifest = published_manifest_record()
    conformance = published_conformance_record()
    boundary = published_boundary_record()
    roadmap = published_roadmap_record()
    OUT.mkdir(parents=True, exist_ok=True)
    _write("manifest.json", manifest)
    _write("conformance.json", conformance)
    _write("c15-2-evidence-boundary.json", boundary)
    _write("roadmap-projection.json", roadmap)
    (OUT / "conformance.md").write_text(_markdown(manifest, conformance))
    print(json.dumps({
        "manifest_sha256": manifest["manifest_sha256"],
        "conformance_sha256": conformance["conformance_sha256"],
        "software_delivery_status": conformance["software_delivery_status"],
        "student_mastery_status": conformance["student_mastery_status"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
