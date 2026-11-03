"""Content-addressed B13.1 immutable bundle codec."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

import bilqis_mlx.runtime.mlx_checkpoint as _mlx_checkpoint
from bilqis_mlx.data_plane import DataPlaneError, data_plane
from bilqis_mlx.runtime.disk import assert_headroom
from .records import (
    SIDECARS, BamfBundleCandidate, BamfGenerationManifest, CompleteStudent,
    canonical, invalid, sha, sidecar_records, validate_sidecars,
)


def _write_file(path: Path, raw: bytes) -> str:
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def save_bamf_bundle(candidate: BamfBundleCandidate, destination: Path, *,
                     reserve_gib: float = 100.0) -> dict:
    """Write and read back one immutable v2 generation without publishing it."""
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
    records = sidecar_records(candidate)
    destination.mkdir(parents=True)
    retained = candidate.retained_state
    tensor = _mlx_checkpoint.save_bamf_state_payload(
        destination / "bamf-state.safetensors", candidate.topology, candidate.extents,
        retained.optimizer, optimizer_step=retained.optimizer_step,
        reserve_gib=reserve_gib)
    plane = data_plane()
    try:
        local_tensor = destination / tensor["filename"]
        object_path = plane.file_object_destination(tensor["sha256"])
        if not plane.owns_file_object(tensor["sha256"]):
            assert_headroom(
                object_path, required_bytes=local_tensor.stat().st_size,
                reserve_gib=reserve_gib)
        plane.adopt_file_object(local_tensor, tensor["sha256"])
        local_tensor.unlink()
        tensor = {**tensor, "object_sha256": tensor["sha256"]}
    except ValueError:
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    bindings = {}
    for name, record in records.items():
        raw = canonical(record)
        digest = sha(raw)
        plane.put_object(digest, raw)
        filename = SIDECARS[name]
        bindings[name] = {
            "filename": filename, "sha256": _write_file(destination / filename, raw),
            "object_sha256": digest,
        }
    hp = candidate.optimizer_hyperparameters
    manifest = BamfGenerationManifest(
        candidate.run_id, candidate.generation, candidate.parent_manifest_sha256,
        candidate.implementation_sha256, candidate.topology.to_record(),
        candidate.extents.to_record(), candidate.provenance.to_record(), tensor,
        {"schema": retained.optimizer.schema_version, "step": retained.optimizer_step,
         "hyperparameters": asdict(hp)}, candidate.transition, bindings).to_record()
    raw = canonical(manifest)
    digest = _write_file(destination / "manifest.json", raw)
    plane.put_node(digest, raw, candidate.generation, candidate.parent_manifest_sha256)
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
    try:
        if data_plane().get_object(binding["object_sha256"]) != raw:
            invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    except ValueError:
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    return json.loads(raw)


def validate_bamf_bundle_custody(
        root: Path, *, expected_manifest_sha256: str | None = None) -> dict:
    """Verify local immutable bundle bytes without constructing MLX tensor state."""
    root = Path(root)
    manifest_path = root / "manifest.json"
    if root.is_symlink() or not root.is_dir() or manifest_path.is_symlink() or not manifest_path.is_file():
        invalid(DataPlaneError.BUNDLE_ROOT_UNSAFE)
    raw = manifest_path.read_bytes()
    digest = sha(raw)
    if expected_manifest_sha256 is not None and digest != expected_manifest_sha256:
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    try:
        if data_plane().get_node(digest) != raw:
            invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
        manifest = BamfGenerationManifest.from_record(json.loads(raw)).to_record()
    except (ValueError, json.JSONDecodeError, KeyError, TypeError):
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    if (set(manifest.get("sidecars", {})) != set(SIDECARS)
            or set(manifest["optimizer"]) != {"schema", "step", "hyperparameters"}
            or manifest["optimizer"]["step"] != manifest.get("tensors", {}).get("optimizer_step")):
        invalid()
    for name in SIDECARS:
        _read_sidecar(root, manifest["sidecars"][name])
    tensor = manifest.get("tensors", {})
    legacy_keys = {"schema", "filename", "sha256", "optimizer_step",
                   "tensor_count", "uncompressed_bytes"}
    current_keys = legacy_keys | {"object_sha256"}
    if (not isinstance(tensor, dict) or set(tensor) not in (legacy_keys, current_keys)
            or Path(tensor.get("filename", "")).name != tensor.get("filename")):
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    if "object_sha256" in tensor:
        if tensor["object_sha256"] != tensor.get("sha256"):
            invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
        try:
            data_plane().require_file_object(tensor["object_sha256"])
        except ValueError:
            invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    else:
        tensor_path = root / tensor["filename"]
        if (tensor_path.is_symlink() or not tensor_path.is_file()
                or not _mlx_checkpoint.verify_file_digest(tensor_path, tensor.get("sha256"))):
            invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    return manifest


def _tensor_read_path(root: Path, binding: dict) -> tuple[Path, dict]:
    if "object_sha256" not in binding:
        return root / binding["filename"], binding
    try:
        path = data_plane().require_file_object(binding["object_sha256"])
    except ValueError:
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    return path, {key: value for key, value in binding.items()
                  if key != "object_sha256"} | {"filename": path.name}


def load_bamf_bundle(root: Path, *, expected_manifest_sha256: str | None = None) -> CompleteStudent:
    """Validate manifest and all sidecars before constructing B12 optimizer state."""
    from bilqis_mlx.learning.atlas_candidate import CandidateState
    from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, STATE_SCHEMA
    from bilqis_mlx.runtime.checkpoint_outbox import ordinary_outbox_lineage
    from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, GenerationProvenance, ModelTopologySpecV2
    root = Path(root)
    manifest = validate_bamf_bundle_custody(
        root, expected_manifest_sha256=expected_manifest_sha256)
    if manifest["optimizer"]["schema"] != STATE_SCHEMA:
        invalid()
    spec = ModelTopologySpecV2.from_record(manifest["topology"])
    extents = GenerationExtents.from_record(manifest["extents"])
    provenance = GenerationProvenance.from_record(manifest["provenance"])
    records = {name: _read_sidecar(root, manifest["sidecars"][name]) for name in SIDECARS}
    motif, policy = validate_sidecars(extents, provenance, records)
    lineage = {"run_id": manifest["run_id"], "generation": manifest["generation"]}
    if not records["outbox"] or not ordinary_outbox_lineage(lineage, list(records["outbox"])):
        invalid("BAMF_OUTBOX_LINEAGE_INVALID")
    hp_record = dict(manifest["optimizer"]["hyperparameters"])
    hp_record["betas"] = tuple(hp_record.get("betas", ()))
    hp = AdamWHyperparameters(**hp_record)
    tensor_path, tensor_binding = _tensor_read_path(root, manifest["tensors"])
    numerical = _mlx_checkpoint.load_bamf_state_payload(
        tensor_path, tensor_binding, spec, extents)
    retained = CandidateState(numerical, policy, motif, manifest["optimizer"]["step"])
    return CompleteStudent(
        manifest["run_id"], manifest["generation"], manifest["parent_manifest_sha256"],
        manifest["implementation_sha256"], spec, extents, retained, hp, provenance,
        records["semantic_abi"], records["compiler_features"],
        records["correction_frontier"], records["teacher_state"],
        records["evaluation_contract"], manifest["transition"], tuple(records["outbox"]))
