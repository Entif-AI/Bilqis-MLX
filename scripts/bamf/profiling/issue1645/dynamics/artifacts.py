"""Admission of exact research evidence bytes; no authority from file names."""
from dataclasses import dataclass, field
from hashlib import file_digest
import json
from pathlib import Path
import stat

from scripts.bamf.profiling.issue1645.reservation import CAPABILITIES, require

FILES = ("update.safetensors", "protected.safetensors")
LEGACY_SCHEMA = "bilqis.research.diagnostic-artifact-index/v1"


def identity(path):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode), f"nonregular artifact: {path.name}")
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def sha256_file(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


@dataclass
class ArtifactGuard:
    """Read-only pins, checked again after consumption."""
    admitted: dict = field(default_factory=dict)

    def admit(self, path, expected):
        path = Path(path)
        require(not path.parent.is_symlink(), f"symlink artifact directory: {path.parent.name}")
        require(isinstance(expected, str) and len(expected) == 64,
                f"missing artifact digest: {path.name}")
        before = identity(path)
        require(sha256_file(path) == expected, f"artifact digest mismatch: {path.name}")
        require(identity(path) == before, f"artifact changed during admission: {path.name}")
        self.admitted[path] = before

    def require_current(self):
        for path, before in self.admitted.items():
            require(not path.parent.is_symlink() and identity(path) == before,
                    f"artifact changed during consumption: {path.name}")


def add_legacy_arguments(parser):
    parser.add_argument("--legacy-artifact-index", type=Path)
    parser.add_argument("--legacy-artifact-index-sha256")


def reference_basis(reference):
    receipts = reference["capabilities"]
    require(bool(receipts), "empty capability result")
    bases = [{name: tuple(leaf["shape"]) for name, leaf in item["leaves"].items()}
             for item in receipts.values()]
    require(bool(bases[0]) and all(basis == bases[0] for basis in bases),
            "result parent basis mismatch")
    return bases[0]


def admit_reference(root, expected, legacy_index=None, legacy_digest=None):
    """Only new result-bound hashes or separately pinned historical audit bytes."""
    root = Path(root)
    require(not root.is_symlink(), "symlink evidence root")
    require((legacy_index is None) == (legacy_digest is None), "legacy index flags must be paired")
    guard = ArtifactGuard()
    path = root / "result.json"
    guard.admit(path, expected)
    reference = json.loads(path.read_text())
    receipts = reference["capabilities"]
    require(set(receipts) == set(CAPABILITIES), "incomplete diagnostic capability set")
    has_map = ["artifact_sha256" in item for item in receipts.values()]
    if all(has_map):
        require(legacy_index is None, "legacy index forbidden for result-bound artifacts")
        artifacts = {cap: item["artifact_sha256"] for cap, item in receipts.items()}
    else:
        require(not any(has_map), "mixed artifact receipt format")
        require(legacy_index is not None, "independently pinned legacy artifact index required")
        guard.admit(legacy_index, legacy_digest)
        index = json.loads(Path(legacy_index).read_text())
        require(index.get("schema") == LEGACY_SCHEMA
                and index.get("source_result_sha256") == expected
                and index.get("manifest_sha256") == reference["manifest_sha256"],
                "legacy artifact index source mismatch")
        artifacts = index["artifacts"]
    require(set(artifacts) == set(receipts), "artifact capability map mismatch")
    for cap, entries in artifacts.items():
        require(isinstance(entries, dict) and set(entries) == set(FILES), "artifact file map mismatch")
        for name, digest in entries.items():
            guard.admit(root / cap / name, digest)
    from safetensors import safe_open
    basis = reference_basis(reference)
    for cap in CAPABILITIES:
        for name in FILES:
            with safe_open(str(root / cap / name), framework="numpy") as tensors:
                require_full_basis(tensors, basis, update=(name == FILES[0]))
    guard.require_current()
    return reference, guard


def require_full_basis(tensors, basis, *, update=False):
    """Check the full saved coordinate basis, including masks and epsilon variants."""
    if update:
        from scripts.bamf.profiling.issue1645.frozen_displacement import (
            OUTPUT_LEAVES, EPSILON_CANDIDATES,
        )
        expected = {f"{kind}/{name}": shape for name, shape in basis.items()
                    for kind in ("raw", "clipped", "delta", "old_moment", "decay")}
        expected.update({f"eps{eps}/{name}": shape for name, shape in basis.items()
                         if name in OUTPUT_LEAVES for eps in EPSILON_CANDIDATES})
        masks = {f"mask/{name}" for name in basis}
        require(set(tensors.keys()) == set(expected) | masks, "update basis mismatch")
        for name, shape in basis.items():
            actual = tuple(tensors.get_slice(f"mask/{name}").get_shape())
            require(actual in ((), shape[:1]), "update mask shape mismatch")
    else:
        expected = basis
        require(set(tensors.keys()) == set(expected), "probe basis mismatch")
    for name, shape in expected.items():
        require(tuple(tensors.get_slice(name).get_shape()) == tuple(shape), "parameter shape mismatch")
