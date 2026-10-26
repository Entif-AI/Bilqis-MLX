#!/usr/bin/env python3
"""Validate and query the issue #150 factory micro-spec workstack."""

from __future__ import annotations

import argparse
from graphlib import CycleError, TopologicalSorter
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable


SCHEMA = "bilqis.factory-workstack/v1"
DEFAULT_MANIFEST = Path("docs/tasks/0003_FACTORY_CLOSURE_WORKSTACK.json")
SPEC_ID = re.compile(r"^SPEC-(\d{4})$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_TRACKS = frozenset(
    {
        "control",
        "guards",
        "v2-contract",
        "legacy-decoupling",
        "scheduler-policy",
        "compatibility-quarantine",
        "provider-custody",
        "prepared-successor",
        "proof-closeout",
    }
)
REQUIRED_ENTRY_KEYS = frozenset(
    {
        "spec_id",
        "path",
        "spec_sha256",
        "title",
        "track",
        "depends_on",
        "wave",
        "verification_tier",
        "issue_number",
        "issue_sha256",
    }
)


class WorkstackError(ValueError):
    """Raised when the workstack violates its deterministic contract."""


def _entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    leaves = manifest.get("leaves")
    if not isinstance(leaves, list) or not leaves:
        raise WorkstackError("FACTORY_WORKSTACK_LEAVES_INVALID")
    if not all(isinstance(entry, dict) for entry in leaves):
        raise WorkstackError("FACTORY_WORKSTACK_ENTRY_INVALID")
    return leaves


def validate_manifest(
    manifest: dict[str, Any],
    *,
    root: Path | None = None,
    execution_ready: bool = False,
) -> tuple[str, ...]:
    """Validate shape, identities, files, and DAG; return topological order."""

    if manifest.get("schema") != SCHEMA:
        raise WorkstackError("FACTORY_WORKSTACK_SCHEMA_INVALID")
    if manifest.get("parent_issue") != 150:
        raise WorkstackError("FACTORY_WORKSTACK_PARENT_INVALID")

    leaves = _entries(manifest)
    ids: set[str] = set()
    paths: set[str] = set()
    issues: set[int] = set()
    graph: dict[str, set[str]] = {}

    for entry in sorted(leaves, key=lambda item: item.get("spec_id", "")):
        if set(entry) != REQUIRED_ENTRY_KEYS:
            raise WorkstackError("FACTORY_WORKSTACK_ENTRY_KEYS_INVALID")
        spec_id = entry["spec_id"]
        match = SPEC_ID.fullmatch(spec_id) if isinstance(spec_id, str) else None
        if match is None:
            raise WorkstackError("FACTORY_WORKSTACK_SPEC_ID_INVALID")
        if spec_id in ids:
            raise WorkstackError(f"FACTORY_WORKSTACK_DUPLICATE_SPEC:{spec_id}")
        ids.add(spec_id)

        path = entry["path"]
        expected_prefix = f"docs/specifications/{match.group(1)}_"
        if not isinstance(path, str) or not path.startswith(expected_prefix) or not path.endswith(".md"):
            raise WorkstackError(f"FACTORY_WORKSTACK_SPEC_PATH_INVALID:{spec_id}")
        if path in paths:
            raise WorkstackError(f"FACTORY_WORKSTACK_DUPLICATE_PATH:{path}")
        paths.add(path)

        spec_sha256 = entry["spec_sha256"]
        if not isinstance(spec_sha256, str) or SHA256.fullmatch(spec_sha256) is None:
            raise WorkstackError(f"FACTORY_WORKSTACK_SPEC_HASH_INVALID:{spec_id}")

        for key in ("title", "wave", "verification_tier"):
            if not isinstance(entry[key], str) or not entry[key].strip():
                raise WorkstackError(f"FACTORY_WORKSTACK_FIELD_INVALID:{spec_id}:{key}")
        if entry["track"] not in ALLOWED_TRACKS:
            raise WorkstackError(f"FACTORY_WORKSTACK_TRACK_INVALID:{spec_id}")

        graph[spec_id] = _validated_dependencies(entry, spec_id)

        _validate_issue_identity(entry, spec_id, issues, execution_ready)

    for spec_id, dependencies in graph.items():
        missing = sorted(dependencies - ids)
        if missing:
            raise WorkstackError(
                f"FACTORY_WORKSTACK_MISSING_DEPENDENCY:{spec_id}:{','.join(missing)}"
            )

    sorter = TopologicalSorter(graph)
    try:
        order = tuple(sorter.static_order())
    except CycleError as exc:
        raise WorkstackError("FACTORY_WORKSTACK_CYCLE") from exc

    _validate_spec_files(root, leaves)

    return order


def ready_specs(
    manifest: dict[str, Any],
    *,
    done: Iterable[str] = (),
    blocked: Iterable[str] = (),
) -> tuple[str, ...]:
    """Return manifest-order leaves whose dependencies are all done."""

    validate_manifest(manifest)
    leaves = _entries(manifest)
    all_ids = {entry["spec_id"] for entry in leaves}
    done_set = set(done)
    blocked_set = set(blocked)
    unknown = sorted((done_set | blocked_set) - all_ids)
    if unknown:
        raise WorkstackError(f"FACTORY_WORKSTACK_STATE_UNKNOWN:{','.join(unknown)}")
    overlap = sorted(done_set & blocked_set)
    if overlap:
        raise WorkstackError(f"FACTORY_WORKSTACK_STATE_CONFLICT:{','.join(overlap)}")

    return tuple(sorted(
        entry["spec_id"]
        for entry in leaves
        if entry["spec_id"] not in done_set
        and entry["spec_id"] not in blocked_set
        and set(entry["depends_on"]).issubset(done_set)
    ))


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkstackError("FACTORY_WORKSTACK_MANIFEST_UNREADABLE") from exc
    if not isinstance(payload, dict):
        raise WorkstackError("FACTORY_WORKSTACK_MANIFEST_INVALID")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--execution-ready", action="store_true")
    parser.add_argument("--done", action="append", default=[])
    parser.add_argument("--blocked", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    try:
        manifest = _load(manifest_path)
        order = validate_manifest(manifest, root=root, execution_ready=args.execution_ready)
        ready = ready_specs(manifest, done=args.done, blocked=args.blocked)
    except WorkstackError as exc:
        print(str(exc))
        return 1
    print(f"FACTORY_WORKSTACK_OK leaves={len(order)}")
    print("READY=" + ",".join(ready))
    return 0


def _validate_issue_identity(entry, spec_id, issues, execution_ready):
    """Validate issue identity and uniqueness after each leaf shape."""
    issue_number = entry["issue_number"]
    issue_sha256 = entry["issue_sha256"]
    if issue_number is not None:
        if not isinstance(issue_number, int) or isinstance(issue_number, bool) or issue_number <= 0:
            raise WorkstackError(f"FACTORY_WORKSTACK_ISSUE_INVALID:{spec_id}")
        if issue_number in issues:
            raise WorkstackError(f"FACTORY_WORKSTACK_DUPLICATE_ISSUE:{issue_number}")
        issues.add(issue_number)
        if not isinstance(issue_sha256, str) or SHA256.fullmatch(issue_sha256) is None:
            raise WorkstackError(f"FACTORY_WORKSTACK_ISSUE_HASH_INVALID:{spec_id}")
    elif execution_ready:
        raise WorkstackError(f"FACTORY_WORKSTACK_ISSUE_MISSING:{spec_id}")
    elif issue_sha256 is not None:
        raise WorkstackError(f"FACTORY_WORKSTACK_ISSUE_HASH_WITHOUT_ISSUE:{spec_id}")


def _validate_spec_files(root, leaves):
    """Check pinned spec bytes and file identity without changing the manifest."""
    if root is not None:
        root = root.resolve()
        for entry in leaves:
            path = root / entry["path"]
            if not path.is_file():
                raise WorkstackError(f"FACTORY_WORKSTACK_SPEC_FILE_MISSING:{entry['spec_id']}")
            content = path.read_bytes()
            actual_hash = hashlib.sha256(content).hexdigest()
            if actual_hash != entry["spec_sha256"]:
                raise WorkstackError(f"FACTORY_WORKSTACK_SPEC_HASH_MISMATCH:{entry['spec_id']}")
            first_line = content.decode("utf-8").splitlines()[0]
            if not first_line.startswith(f"# {entry['spec_id']}:"):
                raise WorkstackError(f"FACTORY_WORKSTACK_SPEC_FILE_ID_MISMATCH:{entry['spec_id']}")


def _validated_dependencies(entry, spec_id):
    dependencies = entry["depends_on"]
    if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
        raise WorkstackError(f"FACTORY_WORKSTACK_DEPENDENCIES_INVALID:{spec_id}")
    if len(dependencies) != len(set(dependencies)):
        raise WorkstackError(f"FACTORY_WORKSTACK_DUPLICATE_DEPENDENCY:{spec_id}")
    if spec_id in dependencies:
        raise WorkstackError(f"FACTORY_WORKSTACK_SELF_DEPENDENCY:{spec_id}")

    return set(dependencies)


if __name__ == "__main__":
    sys.exit(main())
