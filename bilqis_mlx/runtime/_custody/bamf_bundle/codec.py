"""Content-addressed B13.1 bundle codec and atomic generation pointer."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

import bilqis_mlx.runtime.mlx_checkpoint as _mlx_checkpoint
from bilqis_mlx.data_plane import DataPlaneError, data_plane
from .records import (
    BAMF_BUNDLE_SCHEMA, BAMF_POINTER_SCHEMA, SIDECARS, BamfBundleCandidate,
    BamfGenerationManifest, CompleteStudent, canonical, invalid, sha,
    sidecar_records, validate_sidecars,
)


def _write_file(path: Path, raw: bytes) -> str:
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def save_bamf_bundle(candidate: BamfBundleCandidate, destination: Path, *,
                     reserve_gib: float = 100.0) -> dict:
    """Write a complete immutable v2 generation without changing a live pointer."""
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
    records = sidecar_records(candidate)
    destination.mkdir(parents=True)
    tensor = _mlx_checkpoint.save_bamf_state_payload(
        destination / "bamf-state.safetensors", candidate.topology, candidate.extents,
        candidate.optimizer, optimizer_step=candidate.optimizer_step,
        reserve_gib=reserve_gib)
    bindings = {}
    plane = data_plane()
    for name, record in records.items():
        raw = canonical(record)
        digest = sha(raw)
        plane.put_object(digest, raw)
        filename = SIDECARS[name]
        bindings[name] = {"filename": filename,
                          "sha256": _write_file(destination / filename, raw),
                          "object_sha256": digest}
    hp = candidate.optimizer_hyperparameters
    manifest = BamfGenerationManifest(
        candidate.generation, candidate.parent_manifest_sha256,
        candidate.topology.to_record(), candidate.extents.to_record(),
        candidate.provenance.to_record(), tensor,
        {"schema": candidate.optimizer.schema_version, "step": candidate.optimizer_step,
         "hyperparameters": asdict(hp)}, bindings).to_record()
    raw = canonical(manifest)
    digest = _write_file(destination / "manifest.json", raw)
    directory = os.open(destination, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    load_bamf_bundle(destination, expected_manifest_sha256=digest)
    return {**manifest, "manifest_sha256": digest}


def _read_sidecar(root: Path, binding: dict):
    if (not isinstance(binding, dict)
            or set(binding) != {"filename", "sha256", "object_sha256"}
            or not isinstance(binding.get("filename"), str)
            or Path(binding["filename"]).name != binding["filename"]):
        invalid()
    path = root / binding["filename"]
    if path.is_symlink() or not path.is_file():
        invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    raw = path.read_bytes()
    if sha(raw) != binding["sha256"] or binding["sha256"] != binding["object_sha256"]:
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    if data_plane().get_object(binding["object_sha256"]) != raw:
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    return json.loads(raw)


def load_bamf_bundle(root: Path, *, expected_manifest_sha256: str | None = None) -> CompleteStudent:
    """Cold-validate identity sidecars before loading any neural tensor bytes."""
    from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, STATE_SCHEMA
    from bilqis_mlx.runtime.model_topology_v2 import (
        GenerationExtents, GenerationProvenance, ModelTopologySpecV2,
    )
    root = Path(root)
    manifest_path = root / "manifest.json"
    if root.is_symlink() or not root.is_dir() or manifest_path.is_symlink() or not manifest_path.is_file():
        invalid(DataPlaneError.BUNDLE_ROOT_UNSAFE)
    raw = manifest_path.read_bytes()
    if expected_manifest_sha256 is not None and sha(raw) != expected_manifest_sha256:
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    manifest = BamfGenerationManifest.from_record(json.loads(raw)).to_record()
    if (set(manifest.get("sidecars", {})) != set(SIDECARS)
            or not isinstance(manifest.get("optimizer"), dict)
            or set(manifest["optimizer"]) != {"schema", "step", "hyperparameters"}
            or manifest["optimizer"]["schema"] != STATE_SCHEMA
            or manifest["optimizer"]["step"] != manifest.get("tensors", {}).get("optimizer_step")):
        invalid()
    spec = ModelTopologySpecV2.from_record(manifest["topology"])
    extents = GenerationExtents.from_record(manifest["extents"])
    provenance = GenerationProvenance.from_record(manifest["provenance"])
    records = {name: _read_sidecar(root, manifest["sidecars"][name]) for name in SIDECARS}
    policy = validate_sidecars(extents, provenance, records)
    hp_record = dict(manifest["optimizer"]["hyperparameters"])
    hp_record["betas"] = tuple(hp_record.get("betas", ()))
    hp = AdamWHyperparameters(**hp_record)
    numerical = _mlx_checkpoint.load_bamf_state_payload(
        root / manifest["tensors"]["filename"], manifest["tensors"], spec, extents)
    return CompleteStudent(
        manifest["generation"], manifest["parent_manifest_sha256"], spec, extents,
        numerical, hp, manifest["optimizer"]["step"],
        provenance, records["semantic_abi"], records["motif_allocation"], policy,
        records["compiler_features"], records["correction_frontier"],
        records["teacher_state"], records["evaluation_contract"], tuple(records["outbox"]))


def _atomic_pointer(path: Path, pointer: dict) -> None:
    raw = canonical(pointer)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".bamf-pointer-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def publish_bamf_generation(run_dir: Path, candidate: BamfBundleCandidate, *,
                            reserve_gib: float = 100.0) -> dict:
    """Publish one verified generation pointer after immutable bundle fsync."""
    run_dir = Path(run_dir)
    pointer_path = run_dir / "bamf-state.json"
    if pointer_path.exists():
        current = json.loads(pointer_path.read_bytes())
        if (current.get("schema") != BAMF_POINTER_SCHEMA
                or current.get("generation") != candidate.generation - 1
                or current.get("manifest_sha256") != candidate.parent_manifest_sha256):
            invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
    elif candidate.generation != 0 or candidate.parent_manifest_sha256 is not None:
        invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
    stage = run_dir / ".bamf-staging" / f"{candidate.generation:07d}"
    manifest = save_bamf_bundle(candidate, stage, reserve_gib=reserve_gib)
    digest = manifest["manifest_sha256"]
    target = run_dir / "bamf-bundles" / digest
    target.parent.mkdir(exist_ok=True)
    if target.exists() or target.is_symlink():
        invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
    stage.rename(target)
    directory = os.open(target.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    pointer = {"schema": BAMF_POINTER_SCHEMA, "generation": candidate.generation,
               "parent_manifest_sha256": candidate.parent_manifest_sha256,
               "bundle": str(target.relative_to(run_dir)), "manifest_sha256": digest}
    _atomic_pointer(pointer_path, pointer)
    return pointer


def load_bamf_generation(pointer_path: Path) -> CompleteStudent:
    pointer_path = Path(pointer_path)
    pointer = json.loads(pointer_path.read_bytes())
    bundle = Path(pointer.get("bundle", "")) if isinstance(pointer, dict) else Path()
    if (not isinstance(pointer, dict) or pointer.get("schema") != BAMF_POINTER_SCHEMA
            or type(pointer.get("generation")) is not int or bundle.is_absolute()
            or set(pointer) != {"schema", "generation", "parent_manifest_sha256",
                                "bundle", "manifest_sha256"}
            or not bundle.parts or bundle.parts[0] != "bamf-bundles"
            or any(part in ("", ".", "..") for part in bundle.parts)):
        invalid()
    student = load_bamf_bundle(
        pointer_path.parent / bundle,
        expected_manifest_sha256=pointer.get("manifest_sha256"))
    if (student.generation != pointer["generation"]
            or student.parent_manifest_sha256 != pointer["parent_manifest_sha256"]):
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    return student
