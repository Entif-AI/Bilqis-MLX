"""Bounded C13.2 qualification runner over existing production-owner proofs."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time


SCHEMA = "bilqis.c13.qualification-receipt/v1"
_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class CommandReceipt:
    label: str
    argv: tuple[str, ...]
    required: bool
    returncode: int
    elapsed_ms: int
    stdout_sha256: str
    stderr_sha256: str
    max_rss_bytes: int
    stdout_tail: str
    stderr_tail: str

    @property
    def passed(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class QualificationReceipt:
    head_sha256: str
    base_sha256: str
    prerequisite_sha256: str
    host_machine: str
    host_memory_bytes: int | None
    python: str
    commands: tuple[CommandReceipt, ...]
    status: str
    schema_version: str = SCHEMA


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args), cwd=_ROOT, capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def _memory_bytes() -> int | None:
    if platform.system() != "Darwin":
        return None
    completed = subprocess.run(
        ("sysctl", "-n", "hw.memsize"), capture_output=True, text=True,
        check=False)
    if completed.returncode != 0:
        return None
    try:
        return int(completed.stdout.strip())
    except ValueError:
        return None


def _run(label: str, argv: tuple[str, ...], *, required: bool) -> CommandReceipt:
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    started = time.monotonic()
    completed = subprocess.run(argv, cwd=_ROOT, capture_output=True, check=False)
    elapsed_ms = round((time.monotonic() - started) * 1000)
    after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    # Darwin reports bytes; Linux reports KiB. Preserve one byte-valued contract.
    max_rss = int(after if platform.system() == "Darwin" else after * 1024)
    if max_rss < before:
        max_rss = int(before if platform.system() == "Darwin" else before * 1024)
    return CommandReceipt(
        label, argv, required, completed.returncode, elapsed_ms,
        _sha(completed.stdout), _sha(completed.stderr), max_rss,
        completed.stdout[-4000:].decode("utf-8", errors="replace"),
        completed.stderr[-4000:].decode("utf-8", errors="replace"),
    )


def _commands(base_ref: str) -> tuple[tuple[str, tuple[str, ...], bool], ...]:
    py = sys.executable
    return (
        (
            "c13-owner-ring",
            (
                py, "-B", "-m", "unittest", "-q",
                "tests.system.test_bamf_learning_path.BamfLearningPathFixtureTests.test_episode_fixture_is_deterministic_gold_blind_and_constructive",
                "tests.system.test_bamf_learning_path.BamfLearningPathFixtureTests.test_depth_changes_binding_without_exposing_selected_actor",
                "tests.system.test_bamf_learning_path.BamfLearningPathFixtureTests.test_preflight_writes_exact_seed_split_and_truthful_receipt",
                "tests.system.test_bamf_learning_path.BamfLearningPathFixtureTests.test_preflight_is_reproducible_and_bounded_to_64_steps",
                "tests.system.test_bamf_learning_path.BamfLearningPathFixtureTests.test_retained_run_tree_is_rejected",
                "tests.system.test_bamf_learning_path.BamfLearningPathFoundationTests.test_integrated_preflight_publishes_real_zero_update_disposable_foundation",
                "tests.system.test_bamf_learning_path.BamfLearningPathFoundationTests.test_integrated_receipt_names_real_candidate_behaviors_only_after_owner_attempts",
                "tests.system.test_bamf_learning_path.BamfLearningPathCandidateAccountingTests.test_owner_candidate_acceptance_must_advance_generation_and_optimizer",
                "tests.system.test_bamf_learning_path.BamfLearningPathCandidateAccountingTests.test_owner_candidate_rejection_and_hold_preserve_accepted_parent",
                "tests.system.test_bamf_learning_path.BamfLearningPathCandidateAccountingTests.test_candidate_loop_stops_at_first_rejection_after_acceptance",
                "tests.system.test_bamf_learning_path.BamfLearningPathEpisodeSourceTests.test_live_episode_provider_compiles_and_redraws_through_factory",
                "tests.system.test_bamf_learning_path.BamfLearningPathEpisodeSourceTests.test_episode_lowerer_is_gold_blind_and_resolves_binding_by_actor_identity",
                "tests.system.test_bamf_learning_path.BamfLearningPathEpisodeSourceTests.test_live_lowerer_registration_matches_exact_provider_digest",
            ),
            True,
        ),
        (
            "rollback-custody-guards",
            (
                py, "-B", "scripts/run_tests.py",
                "tests/system/test_bamf_learning_path.py",
                "bilqis_mlx/runtime/tests/operator/test_bamf_operator_session.py",
                "bilqis_mlx/runtime/tests/custody/bamf_bundle/test_cold_resume_continuation.py",
                "bilqis_mlx/runtime/tests/custody/bamf_bundle/test_codec.py",
                "bilqis_mlx/learning/_retention/tests/test_atlas_candidate.py",
            ),
            True,
        ),
        ("factory-architecture", (py, "-B", "scripts/check_factory_architecture.py"), True),
        ("semantic-boundaries", (py, "-B", "scripts/check_semantic_boundaries.py"), True),
        # Historical ABI is intentionally advisory unless an independent expected
        # digest is supplied by its owner; the result is still recorded verbatim.
        ("historical-abi", (py, "-B", "scripts/check_historical_abi.py"), False),
        (
            "error-control",
            (py, "-B", "scripts/error_control_plane.py", "--check", "--base-ref", base_ref),
            True,
        ),
        (
            "changed-code-smell",
            (
                py, "-B", "scripts/code_smell_audit.py", "--changed-from", base_ref,
                "--check-baseline", "docs/evidence/development/code_smell_baseline.json",
            ),
            True,
        ),
        ("diff-check", ("git", "diff", "--check", f"{base_ref}...HEAD"), True),
    )


def qualify_c13(
    *, base_ref: str, prerequisite_sha256: str,
) -> QualificationReceipt:
    if len(prerequisite_sha256) != 40:
        raise ValueError("BAMF_C13_2_PREREQUISITE_SHA_INVALID")
    head = _git("rev-parse", "HEAD")
    base = _git("rev-parse", base_ref)
    receipts = tuple(
        _run(label, argv, required=required)
        for label, argv, required in _commands(base_ref)
    )
    failed = tuple(item.label for item in receipts if item.required and not item.passed)
    return QualificationReceipt(
        head, base, prerequisite_sha256, platform.machine(), _memory_bytes(),
        sys.executable, receipts, "PASS" if not failed else "FAIL")


def _main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run bounded C13.2 owner/guard qualification")
    parser.add_argument("--base-ref", default="origin/codex/bamf-unified-base-20261028")
    parser.add_argument("--prerequisite-sha", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    receipt = qualify_c13(
        base_ref=args.base_ref, prerequisite_sha256=args.prerequisite_sha)
    target = Path(args.out).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(receipt), sort_keys=True, indent=2) + "\n")
    print(json.dumps({"receipt": str(target), "status": receipt.status}, sort_keys=True))
    return 0 if receipt.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = ("CommandReceipt", "QualificationReceipt", "qualify_c13")
