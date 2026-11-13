#!/usr/bin/env python3
"""Execute and materialize the current-head C15 conformance receipt set.

This is a software-delivery witness. It runs repository-owned tests only; it
does not start the persistent BAMF learner or authorize neural optimization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from bilqis_mlx.runtime.delivery.conformance import ExecutionReceipt, required_claim_ids
from bilqis_mlx.runtime.delivery.publication import _FIXTURE_OWNERS, _REQ_OWNERS
from bilqis_mlx.runtime.delivery.sources import expected_behavior, literal_test_ref

OUT_ROOT = ROOT / "docs/evidence/bamf/delivery/runs"
_TOTALS = re.compile(
    r"TEST_TOTALS total=(\d+) passed=(\d+) failed=(\d+) skipped=(\d+) errors=(\d+)"
)

GATES = {
    "GRADE_NEUTRAL_INVARIANCE":
        "bilqis_mlx/learning/tests/teaching/test_c03_parent_acceptance.py",
    "NO_LEGACY_" + "BA" + "V_RUNTIME_NAMESPACE":
        "bilqis_mlx/runtime/delivery/tests/test_no_legacy_" + "ba" + "v_namespace.py",
}


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _claim_owner(index: int) -> str:
    return (_REQ_OWNERS[index] if index < len(_REQ_OWNERS)
            else _FIXTURE_OWNERS[index - len(_REQ_OWNERS)])


def claim_plan() -> tuple[dict, ...]:
    rows = []
    for index, claim_id in enumerate(required_claim_ids()):
        owner_ref = _claim_owner(index)
        primary = owner_ref.split("/")[0]
        test_ref = literal_test_ref(primary, claim_id)
        if test_ref.startswith("BLOCKED_SOURCE_OWNER:"):
            raise RuntimeError(f"{claim_id}: no current executable owner test surface")
        rows.append({
            "claim_id": claim_id,
            "owner_ref": owner_ref,
            "primary_owner": primary,
            "test_ref": test_ref,
            "expected_behavior": expected_behavior(primary, claim_id),
        })
    return tuple(rows)


def _command(python: str, test_ref: str) -> tuple[str, ...]:
    if test_ref == "scripts/check_bamf_workstack.py":
        return (python, "-B", test_ref, "docs/tasks/bamf-0.2/workstack.json")
    return (python, "-B", "scripts/run_tests.py", test_ref)


def _observed(test_ref: str, completed: subprocess.CompletedProcess[str]) -> str:
    combined = completed.stdout + completed.stderr
    if test_ref == "scripts/check_bamf_workstack.py":
        try:
            record = json.loads(completed.stdout)
            return (
                f"returncode={completed.returncode};status={record.get('status')};"
                f"child_count={record.get('child_count')};"
                f"order={len(record.get('order', []))};"
                f"held_keys={record.get('dependency_resolution', {}).get('held_keys', [])}"
            )
        except json.JSONDecodeError:
            return f"returncode={completed.returncode};workstack_output_unparseable"
    matches = _TOTALS.findall(combined)
    if not matches:
        return f"returncode={completed.returncode};TEST_TOTALS=missing"
    total, passed, failed, skipped, errors = matches[-1]
    return (
        f"returncode={completed.returncode};total={total};passed={passed};"
        f"failed={failed};skipped={skipped};errors={errors}"
    )


def _passed(test_ref: str, completed: subprocess.CompletedProcess[str], observed: str) -> bool:
    if completed.returncode != 0:
        return False
    if test_ref == "scripts/check_bamf_workstack.py":
        return ";status=valid;" in observed and "held_keys=[]" in observed
    match = re.search(
        r"total=(\d+);passed=(\d+);failed=(\d+);skipped=(\d+);errors=(\d+)", observed)
    return bool(match and match.group(1) == match.group(2)
                and match.group(3) == "0" and match.group(4) == "0"
                and match.group(5) == "0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable,
                        help="Existing compatible interpreter; packages are never installed by this script.")
    parser.add_argument("--candidate-sha", help="Exact tested commit; defaults to HEAD.")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--list", action="store_true", help="Print the deterministic execution plan only.")
    args = parser.parse_args()

    rows = claim_plan()
    surfaces = tuple(dict.fromkeys(row["test_ref"] for row in rows))
    if args.list:
        print(json.dumps({"claims": len(rows), "surfaces": list(surfaces), "gates": GATES}, indent=2))
        return 0

    candidate = args.candidate_sha or _git("rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", candidate):
        raise SystemExit("candidate SHA must be an exact 40-hex commit")
    if _git("rev-parse", "HEAD") != candidate:
        raise SystemExit("candidate SHA must equal current HEAD")
    if _git("status", "--porcelain"):
        raise SystemExit("C15 requalification requires a clean candidate worktree")
    subprocess.run(["git", "cat-file", "-e", f"{candidate}^{{commit}}"], cwd=ROOT, check=True)

    execution = {}
    all_surfaces = tuple(dict.fromkeys((*surfaces, *GATES.values())))
    for test_ref in all_surfaces:
        command = _command(args.python, test_ref)
        completed = subprocess.run(
            command, cwd=ROOT, text=True, capture_output=True,
            timeout=args.timeout_seconds, check=False)
        observed = _observed(test_ref, completed)
        execution[test_ref] = {
            "argv": list(command),
            "runner": " ".join(command),
            "returncode": completed.returncode,
            "observed": observed,
            "stdout_sha256": _sha(completed.stdout),
            "stderr_sha256": _sha(completed.stderr),
            "pass": _passed(test_ref, completed, observed),
        }
        print(f"{test_ref}: {observed}")

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    claims = []
    for row in rows:
        run = execution[row["test_ref"]]
        receipt_ref = f"docs/evidence/bamf/delivery/runs/{row['claim_id'].lower()}.json"
        receipt = ExecutionReceipt.from_execution(
            receipt_ref=receipt_ref, candidate_sha=candidate,
            fixture=row["test_ref"], expected=row["expected_behavior"],
            observed=run["observed"], runner=run["runner"],
            disposition="PASS" if run["pass"] else "FAIL")
        record = {
            "schema": receipt.schema,
            "receipt_ref": receipt.receipt_ref,
            "candidate_sha": receipt.candidate_sha,
            "fixture_sha256": receipt.fixture_sha256,
            "expected_sha256": receipt.expected_sha256,
            "observed_sha256": receipt.observed_sha256,
            "runner_sha256": receipt.runner_sha256,
            "disposition": receipt.disposition,
        }
        (ROOT / receipt_ref).write_text(json.dumps(record, indent=2) + "\n")
        claims.append({**row, "observed_output": run["observed"],
                       "runner_environment": run["runner"],
                       "run_receipt": record})

    gates = []
    for gate_id, test_ref in GATES.items():
        run = execution[test_ref]
        gates.append({"gate_id": gate_id, "test_ref": test_ref,
                      "observed": run["observed"], "pass": run["pass"]})
    index = {
        "schema": "bilqis.bamf.c15-requalification/v1",
        "candidate_sha": candidate,
        "python": args.python,
        "claims": claims,
        "gates": gates,
        "all_pass": all(row["run_receipt"]["disposition"] == "PASS" for row in claims)
                    and all(gate["pass"] for gate in gates),
    }
    (OUT_ROOT / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"candidate_sha": candidate, "claims": len(claims),
                      "surfaces": len(surfaces), "all_pass": index["all_pass"]}, sort_keys=True))
    return 0 if index["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
