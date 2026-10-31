#!/usr/bin/env python3
"""Content-addressed and differential verification policy for the Ithkuil/SKOS bundle."""
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


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

POLICY_SENSITIVE_PATHS = frozenset({
    "scripts/skos_test_policy.py",
    "scripts/run_tests.py",
    ".github/workflows/quality.yml",
    ".github/workflows/semantic-profile-full.yml",
    "package.json",
})

CROSS_CUTTING_SKOS_MODULES = frozenset({
    "build",
    "builder",
    "canonical",
    "configuration",
    "conformance",
    "corpus",
    "coverage",
    "coverage_domains",
    "determinism",
    "identity",
    "ledger",
    "ledger_model",
    "no_omission",
    "preflight",
    "preflight_io",
    "preflight_manifest",
    "preflight_rules",
    "publication",
    "resolver",
    "shacl",
    "shapes",
    "source",
    "source_public",
    "source_types",
})

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


def _is_bundle_path(path: str) -> bool:
    return (
        path.startswith("lib/ithkuil/")
        or path.startswith("skills/ithkuil-ingestion/")
        or path in {
            "scripts/package_ithkuil_skill.py",
            "scripts/run_tests.py",
            "scripts/skos_test_policy.py",
        }
    )


def semantic_test_files(root: Path) -> tuple[str, ...]:
    return tuple(
        test.relative_to(root).as_posix()
        for test in sorted((root / "lib/ithkuil/tests").glob("test_skos_*.py"))
    )


def _fixture_owners(root: Path, changed: str) -> tuple[str, ...]:
    fixture = Path(changed)
    needles = {
        fixture.name,
        fixture.relative_to("lib/ithkuil/tests").as_posix()
        if changed.startswith("lib/ithkuil/tests/") else fixture.name,
    }
    owners = []
    for test_path in semantic_test_files(root):
        text = (root / test_path).read_text(errors="replace")
        if any(needle in text for needle in needles):
            owners.append(test_path)
    return tuple(owners)


def _direct_owner(root: Path, changed: str) -> str | None:
    path = Path(changed)
    if changed.startswith("lib/ithkuil/src/skos/") and path.suffix == ".py":
        candidate = root / "lib/ithkuil/tests" / f"test_skos_{path.stem}.py"
        return candidate.relative_to(root).as_posix() if candidate.exists() else None
    if changed.startswith("lib/ithkuil/src/") and path.suffix == ".py":
        candidate = root / "lib/ithkuil/tests" / f"test_{path.stem}.py"
        return candidate.relative_to(root).as_posix() if candidate.exists() else None
    return None


def _module_name(root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imported_modules(root: Path, path: Path) -> frozenset[str]:
    try:
        tree = ast.parse(path.read_text(errors="replace"), filename=str(path))
    except (OSError, SyntaxError):
        return frozenset()
    current = _module_name(root, path)
    package = current if path.name == "__init__.py" else current.rpartition(".")[0]
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        if node.level:
            relative_name = "." * node.level + module
            try:
                base = importlib.util.resolve_name(relative_name, package)
            except (ImportError, ValueError):
                base = ""
        else:
            base = module
        if base:
            imported.add(base)
        for alias in node.names:
            if alias.name != "*" and base:
                imported.add(f"{base}.{alias.name}")
    return frozenset(imported)


def _impact_import_graph(root: Path) -> dict[str, frozenset[str]]:
    graph: dict[str, frozenset[str]] = {}
    for relative_root in (Path("lib/ithkuil/src"), Path("lib/ithkuil/tests")):
        search_root = root / relative_root
        for path in sorted(search_root.rglob("*.py")):
            graph[_module_name(root, path)] = _imported_modules(root, path)
    return graph


def _depends_on(
    graph: dict[str, frozenset[str]], starts: frozenset[str], target: str,
) -> bool:
    pending = list(starts)
    seen = set()
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        seen.add(module)
        if module == target or module.startswith(target + "."):
            return True
        pending.extend(dep for dep in graph.get(module, ()) if dep not in seen)
    return False


def _transitive_owners(root: Path, changed: str) -> tuple[str, ...]:
    path = root / changed
    if path.suffix != ".py" or not path.exists():
        return ()
    target = _module_name(root, path)
    graph = _impact_import_graph(root)
    owners = []
    for test_path in semantic_test_files(root):
        test = root / test_path
        if _depends_on(graph, _imported_modules(root, test), target):
            owners.append(test_path)
    return tuple(owners)


def classify_changes(root: Path, changed_paths: tuple[str, ...]) -> TestPlan:
    relevant = tuple(sorted({
        path for path in changed_paths
        if _is_bundle_path(path) or path in POLICY_SENSITIVE_PATHS or path == str(RECEIPT_PATH)
    }))
    if not relevant:
        return TestPlan("SKIP", reason="NO_SEMANTIC_PROFILE_CHANGES")
    if any(path in POLICY_SENSITIVE_PATHS for path in relevant):
        return TestPlan("FULL", reason="TEST_POLICY_CHANGED")
    bundle_changes = tuple(path for path in relevant if _is_bundle_path(path))
    if not bundle_changes and str(RECEIPT_PATH) in relevant:
        return TestPlan("FULL", reason="RECEIPT_ONLY_CHANGED")
    if any(path.startswith("lib/ithkuil/_data/") for path in bundle_changes):
        return TestPlan("FULL", reason="CANONICAL_CORPUS_CHANGED")
    if any(
        path.startswith("skills/ithkuil-ingestion/")
        or path == "scripts/package_ithkuil_skill.py"
        or path in {
            "lib/ithkuil/ingestion_contract.json",
            "lib/ithkuil/requirements-extraction.txt",
            "lib/ithkuil/requirements-falkor.txt",
            "lib/ithkuil/requirements-semantic.txt",
        }
        for path in bundle_changes
    ):
        return TestPlan("FULL", reason="INGESTION_OR_PACKAGE_CONTRACT_CHANGED")

    selected: set[str] = set()
    needs_canaries = False
    for changed in bundle_changes:
        path = Path(changed)
        if changed.startswith("lib/ithkuil/src/skos/"):
            if path.suffix in {".json", ".ttl"}:
                return TestPlan("FULL", reason="SHARED_SKOS_CONFIGURATION_CHANGED")
            if path.stem in CROSS_CUTTING_SKOS_MODULES:
                return TestPlan("FULL", reason=f"CROSS_CUTTING_MODULE_CHANGED:{path.stem}")
            owners = set(_transitive_owners(root, changed))
            direct = _direct_owner(root, changed)
            if direct:
                owners.add(direct)
            if not owners:
                return TestPlan("FULL", reason=f"UNKNOWN_SKOS_OWNER:{changed}")
            selected.update(owners)
            needs_canaries = True
            continue
        if changed.startswith("lib/ithkuil/src/"):
            owners = set(_transitive_owners(root, changed))
            direct = _direct_owner(root, changed)
            if direct:
                owners.add(direct)
            if not owners:
                return TestPlan("FULL", reason=f"UNKNOWN_ITHKUIL_OWNER:{changed}")
            selected.update(owners)
            needs_canaries = True
            continue
        if changed.startswith("lib/ithkuil/tests/fixtures/"):
            owners = _fixture_owners(root, changed)
            if not owners:
                return TestPlan("FULL", reason=f"UNOWNED_FIXTURE:{changed}")
            selected.update(owners)
            needs_canaries = True
            continue
        if changed.startswith("lib/ithkuil/tests/test_skos_") and path.suffix == ".py":
            selected.add(changed)
            continue
        if changed.startswith("lib/ithkuil/tests/") and path.suffix == ".py":
            owners = _transitive_owners(root, changed)
            if not owners:
                return TestPlan("FULL", reason=f"UNOWNED_TEST_SUPPORT:{changed}")
            selected.update(owners)
            continue
        return TestPlan("FULL", reason=f"UNCLASSIFIED_SEMANTIC_CHANGE:{changed}")

    if needs_canaries:
        selected.update(test for test in CANARY_TESTS if (root / test).exists())
    return TestPlan("DIFF", tuple(sorted(selected)), "IMPACT_CLOSURE_PLUS_CANARIES")


def _git_lines(root: Path, *args: str) -> tuple[str, ...]:
    proc = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or "git command failed")
    return tuple(line.strip() for line in proc.stdout.splitlines() if line.strip())


def changed_paths(root: Path, base_ref: str | None) -> tuple[str, ...]:
    paths = set()
    if base_ref:
        try:
            paths.update(_git_lines(root, "diff", "--name-only", base_ref, "HEAD"))
        except RuntimeError:
            return ()
    try:
        paths.update(_git_lines(root, "diff", "--name-only"))
        paths.update(_git_lines(root, "diff", "--cached", "--name-only"))
        paths.update(_git_lines(root, "ls-files", "--others", "--exclude-standard"))
    except RuntimeError:
        return ()
    return tuple(sorted(paths))


def plan_for_changes(
    root: Path, changed: tuple[str, ...], *, force_full: bool = False,
) -> TestPlan:
    status = bundle_status(root)
    if force_full:
        return TestPlan("FULL", reason="FORCED_EXHAUSTIVE", sha256=status.sha256)
    classification = classify_changes(root, changed)
    if classification.action == "SKIP":
        return TestPlan(
            "SKIP", reason=classification.reason, sha256=status.sha256)
    bundle_changed = any(_is_bundle_path(path) for path in changed)
    receipt_changed = str(RECEIPT_PATH) in changed
    if (bundle_changed or receipt_changed) and not status.verified:
        return TestPlan(
            "ERROR",
            reason=f"SEMANTIC_RECEIPT_NOT_CURRENT:{status.reason}",
            sha256=status.sha256,
        )
    return TestPlan(
        classification.action,
        classification.tests,
        classification.reason,
        status.sha256,
    )


def plan(
    root: Path, *, base_ref: str | None = None, force_full: bool = False,
) -> TestPlan:
    changed = changed_paths(root, base_ref)
    if base_ref and not changed:
        try:
            _git_lines(root, "rev-parse", "--verify", base_ref)
        except RuntimeError:
            status = bundle_status(root)
            return TestPlan("FULL", reason="BASE_REF_UNAVAILABLE", sha256=status.sha256)
    return plan_for_changes(root, changed, force_full=force_full)


def full_test_shards(root: Path, shard_count: int) -> tuple[tuple[str, ...], ...]:
    if shard_count < 1:
        raise ValueError("shard_count must be at least 1")
    tests = semantic_test_files(root)
    buckets: list[list[str]] = [[] for _ in range(shard_count)]
    weights = [0 for _ in range(shard_count)]
    weighted = sorted(
        [((root / test).stat().st_size, test) for test in tests],
        key=lambda item: (-item[0], item[1]),
    )
    for size, test in weighted:
        shard = min(range(shard_count), key=lambda index: (weights[index], index))
        buckets[shard].append(test)
        weights[shard] += size
    return tuple(tuple(sorted(bucket)) for bucket in buckets)


def shard_manifest(root: Path, shard_count: int) -> tuple[dict, ...]:
    manifest = []
    for index, tests in enumerate(full_test_shards(root, shard_count)):
        manifest.append({
            "index": index,
            "tests": list(tests),
            "test_count": len(tests),
            "source_bytes": sum((root / test).stat().st_size for test in tests),
        })
    return tuple(manifest)


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


def _emit(plan_value: TestPlan, *, github_output: Path | None = None) -> None:
    sha = plan_value.sha256 or ""
    print(
        f"SKOS_TEST_PLAN {plan_value.action} {plan_value.reason}"
        + (f" {sha}" if sha else ""))
    if plan_value.tests:
        print("SKOS_TESTS " + " ".join(plan_value.tests))
    if plan_value.action == "ERROR":
        print(
            "SKOS_RECEIPT_REFRESH_REQUIRED: run "
            "python3 -B scripts/skos_test_policy.py write-receipt "
            "--release-commit HEAD --evidence '<proof context>'"
        )
    if github_output is not None:
        with github_output.open("a") as stream:
            stream.write(f"action={plan_value.action}\n")
            stream.write(f"sha256={sha}\n")
            stream.write(f"reason={plan_value.reason}\n")


def _run_tests(root: Path, tests: tuple[str, ...]) -> int:
    if not tests:
        return 0
    return subprocess.run(
        [sys.executable, "-B", "scripts/run_tests.py", *tests],
        cwd=root,
        check=False,
    ).returncode


def _run_plan(
    root: Path,
    plan_value: TestPlan,
    *,
    full_shard_index: int | None = None,
    full_shard_count: int = DEFAULT_FULL_SHARD_COUNT,
) -> int:
    if plan_value.action == "ERROR":
        _emit(plan_value)
        return 2
    if plan_value.action == "SKIP":
        _emit(plan_value)
        return 0
    if plan_value.action == "DIFF":
        if full_shard_index is not None:
            print("DIFF_PLAN_DOES_NOT_ACCEPT_FULL_SHARD")
            return 2
        return _run_tests(root, plan_value.tests)
    if full_shard_index is not None:
        shards = full_test_shards(root, full_shard_count)
        if not 0 <= full_shard_index < len(shards):
            print("FULL_SHARD_INDEX_OUT_OF_RANGE")
            return 2
        tests = shards[full_shard_index]
        print(
            f"SKOS_FULL_SHARD {full_shard_index + 1}/{full_shard_count} "
            f"tests={len(tests)}"
        )
        return _run_tests(root, tests)
    return _run_tests(root, semantic_test_files(root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "plan", "run"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--base-ref")
        sub.add_argument("--force-full", action="store_true")
        if command == "plan":
            sub.add_argument("--github-output", type=Path)
        if command == "run":
            sub.add_argument("--full-shard-index", type=int)
            sub.add_argument(
                "--full-shard-count", type=int, default=DEFAULT_FULL_SHARD_COUNT)
    shards = subparsers.add_parser("shards")
    shards.add_argument("--shard-count", type=int, default=DEFAULT_FULL_SHARD_COUNT)
    write = subparsers.add_parser("write-receipt")
    write.add_argument("--release-commit", required=True)
    write.add_argument("--evidence", required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]

    if args.command == "write-receipt":
        print(json.dumps(write_receipt(
            root, release_commit=args.release_commit, evidence=args.evidence),
            sort_keys=True))
        return 0
    if args.command == "shards":
        print(json.dumps(shard_manifest(root, args.shard_count), sort_keys=True, indent=2))
        return 0
    if args.command == "status":
        status = bundle_status(root)
        print(json.dumps(status.__dict__, sort_keys=True))
        return 0 if status.verified else 1
    plan_value = plan(
        root,
        base_ref=args.base_ref or None,
        force_full=args.force_full,
    )
    if args.command == "plan":
        _emit(plan_value, github_output=args.github_output)
        return 2 if plan_value.action == "ERROR" else 0
    return _run_plan(
        root,
        plan_value,
        full_shard_index=args.full_shard_index,
        full_shard_count=args.full_shard_count,
    )


if __name__ == "__main__":
    raise SystemExit(main())
