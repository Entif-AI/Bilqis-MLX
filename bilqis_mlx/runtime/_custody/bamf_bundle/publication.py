"""Crash-idempotent, serialized B13.1 pointer publication and outbox recovery."""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path

from bilqis_mlx.data_plane import DataPlaneError, data_plane
from .codec import load_bamf_bundle, save_bamf_bundle, validate_bamf_bundle_custody
from .records import (
    BAMF_POINTER_SCHEMA, BamfBundleCandidate, CompleteStudent, canonical, invalid, sha,
)


def _require_run_root(run_dir: Path) -> None:
    if run_dir.is_symlink() or (run_dir.exists() and not run_dir.is_dir()): invalid(DataPlaneError.BUNDLE_ROOT_UNSAFE)
    run_dir.mkdir(parents=True, exist_ok=True)
    if run_dir.is_symlink() or not run_dir.is_dir(): invalid(DataPlaneError.BUNDLE_ROOT_UNSAFE)

def _require_bundle_root(run_dir: Path, *, create: bool) -> Path:
    root = run_dir / "bamf-bundles"
    if root.is_symlink() or (root.exists() and not root.is_dir()): invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    if create: root.mkdir(exist_ok=True)
    if root.is_symlink() or not root.is_dir(): invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    return root

@contextlib.contextmanager
def _pointer_lock(run_dir: Path):
    _require_run_root(run_dir)
    lock = run_dir / ".bamf-pointer.lock"
    if lock.is_symlink():
        invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock, flags, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            invalid("BAMF_POINTER_WRITER_ACTIVE")
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _read_pointer(path: Path) -> dict | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    try:
        pointer = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        invalid()
    bundle_value = pointer.get("bundle") if isinstance(pointer, dict) else None
    bundle = Path(bundle_value) if isinstance(bundle_value, str) else Path()
    expected = {"schema", "run_id", "generation", "parent_manifest_sha256",
                "bundle", "manifest_sha256"}
    if (not isinstance(pointer, dict) or set(pointer) != expected
            or pointer.get("schema") != BAMF_POINTER_SCHEMA
            or not isinstance(pointer.get("run_id"), str) or not pointer["run_id"]
            or type(pointer.get("generation")) is not int or bundle.is_absolute()
            or bundle_value != f"bamf-bundles/{pointer.get('manifest_sha256')}"
            or tuple(bundle.parts) != ("bamf-bundles", pointer.get("manifest_sha256"))
            or any(part in ("", ".", "..") for part in bundle.parts)):
        invalid()
    return pointer


def _live_bundle_manifest(run_dir: Path, pointer: dict) -> dict:
    root = _require_bundle_root(run_dir, create=False)
    bundle = root / pointer["manifest_sha256"]
    manifest = validate_bamf_bundle_custody(
        bundle, expected_manifest_sha256=pointer["manifest_sha256"])
    if (manifest["run_id"] != pointer["run_id"]
            or manifest["generation"] != pointer["generation"]
            or manifest["parent_manifest_sha256"] != pointer["parent_manifest_sha256"]):
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    return manifest


def _atomic_pointer(path: Path, pointer: dict) -> None:
    if path.is_symlink():
        invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    raw = canonical(pointer)
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


def _stage(run_dir: Path) -> Path:
    _require_run_root(run_dir)
    root = run_dir / ".bamf-staging"
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    root.mkdir(exist_ok=True)
    return root / ("generation-" + uuid.uuid4().hex)


def reconcile_bamf_outbox(run_dir: Path, student: CompleteStudent, *, publish_missing=True) -> bool:
    """Reconcile while the caller holds the generation pointer writer lock."""
    from bilqis_mlx.runtime import checkpoints
    return checkpoints._reconcile_delivery_outbox(
        Path(run_dir), {"run_id": student.run_id, "generation": student.generation,
                        "delivery_outbox": list(student.outbox)},
        publish_missing=publish_missing)


def record_bamf_rejection(run_dir: Path, student: CompleteStudent, evidence: dict) -> str:
    """Publish idempotent failure evidence without minting or mutating a generation."""
    if type(student) is not CompleteStudent or not isinstance(evidence, dict) or not evidence:
        invalid("BAMF_REJECTION_EVIDENCE_INVALID")
    from bilqis_mlx.runtime import checkpoint_outbox, checkpoints
    run_dir = Path(run_dir)
    pointer_path = run_dir / "bamf-state.json"
    with _pointer_lock(run_dir):
        pointer = _read_pointer(pointer_path)
        if (pointer is None or pointer["run_id"] != student.run_id
                or pointer["generation"] != student.generation):
            invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
        manifest = _live_bundle_manifest(run_dir, pointer)
        optimizer_step = manifest.get("optimizer", {}).get("step") if isinstance(manifest, dict) else None
        if type(optimizer_step) is not int or optimizer_step != manifest.get("tensors", {}).get("optimizer_step"):
            invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
        event = {
            "event": "BAMF_CANDIDATE_REJECTED",
            "generation": pointer["generation"],
            "student_manifest_sha256": pointer["manifest_sha256"],
            "optimizer_step": optimizer_step,
            "evidence": dict(evidence),
        }
        record = {"run_id": pointer["run_id"], "generation": pointer["generation"]}
        outbox = checkpoint_outbox.with_delivery_outbox(record, (event,))["delivery_outbox"]
        receipt = {
            "schema": "bilqis.mlx.bamf-rejection-receipt/v1",
            "run_id": student.run_id, "generation": student.generation,
            "student_manifest_sha256": pointer["manifest_sha256"], "event": outbox[0],
        }
        raw = canonical(receipt)
        digest = sha(raw)
        data_plane().put_object(digest, raw)
        checkpoints._reconcile_delivery_outbox(
            run_dir, {**record, "delivery_outbox": outbox})
        return digest


def _validate_parent_transition(run_dir: Path, pointer: dict | None, candidate: BamfBundleCandidate) -> None:
    if pointer is None:
        if candidate.generation != 0 or candidate.parent_manifest_sha256 is not None:
            invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
        return
    if (pointer["run_id"] != candidate.run_id
            or pointer["generation"] != candidate.generation - 1
            or pointer["manifest_sha256"] != candidate.parent_manifest_sha256):
        invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
    parent = load_bamf_bundle(
        run_dir / pointer["bundle"], expected_manifest_sha256=pointer["manifest_sha256"])
    if (parent.run_id != pointer["run_id"]
            or parent.generation != pointer["generation"]
            or parent.parent_manifest_sha256 != pointer["parent_manifest_sha256"]):
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    kind = ("MODEL_SWAP" if parent.topology.digest != candidate.topology.digest else
            "PARAMETER_EXTENSION" if parent.extents.digest != candidate.extents.digest else
            "RETAINED_CANDIDATE")
    parent_step = parent.retained_state.optimizer_step
    candidate_step = candidate.retained_state.optimizer_step
    if (candidate_step < parent_step or
            (kind == "RETAINED_CANDIDATE" and candidate_step <= parent_step)):
        invalid("BAMF_REJECTED_CANDIDATE_NOT_GENERATION")
    if candidate.transition.get("kind") != kind:
        invalid("BAMF_GENERATION_TRANSITION_INVALID")
    reconcile_bamf_outbox(run_dir, parent)


def publish_bamf_generation(run_dir: Path, candidate: BamfBundleCandidate, *,
                            reserve_gib: float = 100.0) -> dict:
    """Publish once; retries converge across staging, rename, pointer and outbox crashes."""
    run_dir = Path(run_dir)
    stage = _stage(run_dir)
    try:
        manifest = save_bamf_bundle(candidate, stage, reserve_gib=reserve_gib)
        digest = manifest["manifest_sha256"]
        target = _require_bundle_root(run_dir, create=True) / digest
        pointer_path = run_dir / "bamf-state.json"
        with _pointer_lock(run_dir):
            current = _read_pointer(pointer_path)
            if current is not None and current["generation"] == candidate.generation:
                if (current["run_id"] != candidate.run_id
                        or current["manifest_sha256"] != digest
                        or current["parent_manifest_sha256"] != candidate.parent_manifest_sha256):
                    invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
                shutil.rmtree(stage)
                student = load_bamf_bundle(
                    run_dir / current["bundle"], expected_manifest_sha256=digest)
                reconcile_bamf_outbox(run_dir, student)
                return current
            _validate_parent_transition(run_dir, current, candidate)
            if target.exists() or target.is_symlink():
                if target.is_symlink() or not target.is_dir():
                    invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
                load_bamf_bundle(target, expected_manifest_sha256=digest)
                shutil.rmtree(stage)
            else:
                stage.rename(target)
                directory = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            pointer = {
                "schema": BAMF_POINTER_SCHEMA, "run_id": candidate.run_id,
                "generation": candidate.generation,
                "parent_manifest_sha256": candidate.parent_manifest_sha256,
                "bundle": str(target.relative_to(run_dir)), "manifest_sha256": digest,
            }
            _atomic_pointer(pointer_path, pointer)
            student = load_bamf_bundle(target, expected_manifest_sha256=digest)
            reconcile_bamf_outbox(run_dir, student)
            return pointer
    except BaseException:
        if stage.exists() and stage.is_dir() and not stage.is_symlink():
            shutil.rmtree(stage)
        raise


def _load_generation_locked(pointer_path: Path) -> tuple[CompleteStudent, dict]:
    pointer = _read_pointer(pointer_path)
    if pointer is None:
        invalid(DataPlaneError.BUNDLE_ROOT_UNSAFE)
    _live_bundle_manifest(pointer_path.parent, pointer)
    student = load_bamf_bundle(
        pointer_path.parent / "bamf-bundles" / pointer["manifest_sha256"],
        expected_manifest_sha256=pointer["manifest_sha256"])
    if (student.run_id != pointer["run_id"] or student.generation != pointer["generation"]
            or student.parent_manifest_sha256 != pointer["parent_manifest_sha256"]):
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    return student, pointer


def load_bamf_generation_authority(pointer_path: Path) -> tuple[CompleteStudent, str]:
    """Read current accepted B13 authority without mutating delivery state."""
    pointer_path = Path(pointer_path)
    with _pointer_lock(pointer_path.parent):
        student, pointer = _load_generation_locked(pointer_path)
        return student, pointer["manifest_sha256"]


def load_bamf_generation(pointer_path: Path, *, publish_missing_outbox: bool = True) -> CompleteStudent:
    pointer_path = Path(pointer_path)
    with _pointer_lock(pointer_path.parent):
        student, _ = _load_generation_locked(pointer_path)
        reconcile_bamf_outbox(
            pointer_path.parent, student, publish_missing=publish_missing_outbox)
        return student
