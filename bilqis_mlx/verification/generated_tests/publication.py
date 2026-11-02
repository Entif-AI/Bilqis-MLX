"""Explicit immutable test-release regeneration and atomic publication."""
from __future__ import annotations
from bilqis_mlx.integer_curriculum import (IntegerScope, _partition,
                                 generate_integer_curriculum)
from bilqis_mlx.pedagogical_parity import _source_stack, build_plan
from pathlib import Path
import os
import shutil
import tempfile
from .contracts import FAMILIES, SCHEMA, _dependency_state, _hash, _json, _object_hash, select_families
from .cases import _suite
from .storage import _read_release


def status(parity: dict, folder: Path, *, selector="all") -> dict:
    scope = IntegerScope.from_environment(parity)
    manifest, suites = _read_release(Path(folder))
    selected = select_families(selector)
    stale = [name for name in selected
             if name not in suites or
             suites[name]["dependency_state"] != _dependency_state(
                 next(f for f in FAMILIES if f.name == name), scope, parity)]
    return {"selector":selector, "integer_max":scope.maximum,
            "selected":list(selected), "stale":stale,
            "release_sha256":manifest["release_sha256"] if manifest else None}


def regenerate(parity: dict, legacy_root: Path, folder: Path, *,
               selector: str, seed: int = 20261015, count: int = 40):
    """Create a whole new release, publish its pointer in one atomic replace."""
    scope = IntegerScope.from_environment(parity)
    selected = set(select_families(selector))
    folder = Path(folder)
    old_manifest, old_suites = _read_release(folder)
    sampled = generate_integer_curriculum(parity, legacy_root, seed=seed,
                                          count=count, maximum=scope.maximum)
    _, arithmetic, _, _, graph, _ = _source_stack(legacy_root)
    suites = dict(old_suites)
    for family in FAMILIES:
        if family.name in selected:
            suites[family.name] = _suite(family, sampled, arithmetic,
                                         graph, scope, parity, seed, count)
    bytes_by_family = {name:_json(value) for name,value in suites.items()}
    manifest = {"schema":SCHEMA, "source_sha256":parity["source_sha256"],
                "graph_sha256":parity["graph_sha256"],
                "integer_max":scope.maximum,
                "suites":{name:{"artifact":"suites/"+name+".json",
                                "sha256":_hash(blob),
                                "dependencies":value["dependencies"],
                                "dependency_state":value["dependency_state"]}
                          for name,(value,blob) in
                          ((n,(suites[n],bytes_by_family[n])) for n in sorted(suites))}}
    manifest["release_sha256"] = _object_hash(manifest)
    release = folder / "releases" / manifest["release_sha256"]
    if (old_manifest is not None and
            old_manifest["release_sha256"] == manifest["release_sha256"]):
        return old_manifest
    (folder / "releases").mkdir(parents=True, exist_ok=True)
    if not release.exists():
        temp = Path(tempfile.mkdtemp(prefix=".staged-", dir=folder / "releases"))
        try:
            (temp / "suites").mkdir()
            for name, blob in bytes_by_family.items():
                (temp / "suites" / (name + ".json")).write_bytes(blob)
            (temp / "manifest.json").write_bytes(_json(manifest))
            temp.rename(release)
        finally:
            if temp.exists():
                shutil.rmtree(temp)
    else:
        actual = (release / "manifest.json").read_bytes()
        if actual != _json(manifest):
            raise ValueError("SEMANTIC_TEST_INTEGRITY_RELEASE_ID_COLLISION")
    pointer = {"release":manifest["release_sha256"],
               "manifest_sha256":_hash(_json(manifest))}
    fd, scratch = tempfile.mkstemp(prefix=".current-", dir=folder)
    try:
        with os.fdopen(fd,"wb") as output:
            output.write(_json(pointer))
            output.flush()
            os.fsync(output.fileno())
        os.replace(scratch, folder / "current.json")
    finally:
        if os.path.exists(scratch):
            os.unlink(scratch)
    return manifest
