"""Integrity-checked generated-test release reads."""
from __future__ import annotations
from pathlib import Path
import json
from .contracts import FAMILIES, SCHEMA, _hash


_UNSAFE_RELEASE = "SEMANTIC_TEST_INTEGRITY_UNSAFE_RELEASE"


def _read_release(folder: Path):
    pointer = folder / "current.json"
    if not pointer.exists():
        return None, {}
    if pointer.is_symlink():
        raise ValueError("SEMANTIC_TEST_INTEGRITY_UNSAFE_POINTER")
    current = json.loads(pointer.read_bytes())
    name = current["release"]
    if (not isinstance(name, str) or len(name) != 64 or
            any(c not in "0123456789abcdef" for c in name)):
        raise ValueError(_UNSAFE_RELEASE)
    release = folder / "releases" / name
    if release.is_symlink() or not release.is_dir():
        raise ValueError(_UNSAFE_RELEASE)
    manifest_path = release / "manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("SEMANTIC_TEST_INTEGRITY_MANIFEST_SYMLINK")
    raw = manifest_path.read_bytes()
    if _hash(raw) != current["manifest_sha256"]:
        raise ValueError("SEMANTIC_TEST_INTEGRITY_MANIFEST_HASH")
    manifest = json.loads(raw)
    if manifest["release_sha256"] != name or manifest["schema"] != SCHEMA:
        raise ValueError("SEMANTIC_TEST_INTEGRITY_MANIFEST_CONTRACT")
    suites = {}
    for family, info in manifest["suites"].items():
        if family not in {f.name for f in FAMILIES} or info["artifact"] != "suites/"+family+".json":
            raise ValueError("SEMANTIC_TEST_INTEGRITY_SUITE_PATH")
        file = release / info["artifact"]
        if file.is_symlink():
            raise ValueError("SEMANTIC_TEST_INTEGRITY_SUITE_SYMLINK")
        content = file.read_bytes()
        if _hash(content) != info["sha256"]:
            raise ValueError("SEMANTIC_TEST_INTEGRITY_SUITE_HASH:"+family)
        value = json.loads(content)
        if value["family"] != family or value["schema"] != SCHEMA:
            raise ValueError("SEMANTIC_TEST_INTEGRITY_SUITE_SCHEMA")
        suites[family] = value
    return manifest, suites
