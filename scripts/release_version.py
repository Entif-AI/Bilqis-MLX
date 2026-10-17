"""Verify the release's semver, changelog, Git tag, and commit-message form.

No network writes, neural updates, or automatic tag creation occur here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import tomllib


ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
CONVENTIONAL = re.compile(
    r"^(feat|fix|docs|test|build|ci|perf|refactor|chore|revert)(\([a-z0-9][a-z0-9-]*\))?!?: .{3,}$"
)


def conventional(subject: str) -> bool:
    return bool(CONVENTIONAL.fullmatch(subject.strip()))


def changelog_section(changelog: str, version: str) -> str:
    pattern = re.compile(r"^## \[" + re.escape(version) + r"\] - \d{4}-\d{2}-\d{2}\s*$", re.M)
    match = pattern.search(changelog)
    if not match:
        raise ValueError("RELEASE_CHANGELOG_VERSION_MISSING")
    rest = changelog[match.end():]
    next_heading = re.search(r"^## \[", rest, re.M)
    content = (rest[:next_heading.start()] if next_heading else rest).strip()
    if not content or not content.startswith("### "):
        raise ValueError("RELEASE_CHANGELOG_NOTES_EMPTY")
    return content


def version_contract(root: Path, *, require_tag: bool = False) -> dict:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    if not VERSION.fullmatch(version) or package.get("version") != version:
        raise ValueError("RELEASE_SEMVER_OR_MANIFEST_MISMATCH")
    notes = changelog_section((root / "CHANGELOG.md").read_text(encoding="utf-8"), version)
    tag = "v" + version
    if require_tag:
        result = subprocess.run(["git", "tag", "--points-at", "HEAD"],
                                cwd=root, capture_output=True, text=True, check=True)
        if tag not in result.stdout.splitlines():
            raise ValueError("RELEASE_TAG_NOT_AT_HEAD")
    return {"version": version, "tag": tag, "notes": notes}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-tag", action="store_true")
    parser.add_argument("--notes", action="store_true")
    parser.add_argument("--validate-subject", type=str)
    args = parser.parse_args(argv)
    if args.validate_subject is not None:
        if not conventional(args.validate_subject):
            raise ValueError("RELEASE_COMMIT_NOT_CONVENTIONAL")
        print("CONVENTIONAL_COMMIT_OK")
        return 0
    status = version_contract(ROOT, require_tag=args.require_tag)
    if args.notes:
        print(status["notes"])
    else:
        print(json.dumps({"version": status["version"], "tag": status["tag"],
                          "notes_present": True, "tag_at_head": args.require_tag}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
