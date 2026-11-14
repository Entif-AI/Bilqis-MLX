"""B13 publication-side outbox and rejection evidence helpers."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

from bilqis_mlx.data_plane import DataPlaneError, data_plane

from ..records import CompleteStudent, canonical, invalid, sha
from .storage import _fsync_directory, _live_bundle_manifest, _pointer_lock, _read_pointer


REJECTION_RECEIPT_DIR = "bamf-rejections"


def _write_portable_rejection_receipt(run_dir: Path, digest: str, raw: bytes) -> None:
    """Persist one immutable rejection receipt inside portable run custody."""
    root = Path(run_dir) / REJECTION_RECEIPT_DIR
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    existed = root.exists()
    root.mkdir(exist_ok=True)
    if not existed:
        _fsync_directory(root)
        _fsync_directory(root.parent)
    target = root / f"{digest}.json"
    if target.is_symlink():
        invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    if target.exists():
        if not target.is_file() or target.read_bytes() != raw:
            invalid("BAMF_REJECTION_RECEIPT_DRIFT")
        return
    fd, temporary = tempfile.mkstemp(prefix=".bamf-rejection-", dir=root)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        _fsync_directory(root)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _portable_c03_rejection_evidence(student: CompleteStudent, pointer: dict,
                                     evidence: dict) -> dict:
    """Copy source-issued C03 visit authority into supported rejection evidence."""
    if evidence.get("schema") != "bilqis.bamf.c16.3-rejection/v2":
        return dict(evidence)
    from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
    from bilqis_mlx.learning.teacher_visit_identity import (
        TeacherVisitIdentity, require_teacher_visit_receipt,
        teacher_visit_receipt_record, validate_teacher_visit_receipt_record,
    )

    state = student.teacher_state
    identity = TeacherVisitIdentity.from_record(evidence.get("teacher_visit"))
    expected_receipt = evidence.get("teacher_visit_receipt")
    if (evidence.get("visit_id") != identity.visit_id
            or evidence.get("capability") != identity.capability_id
            or evidence.get("selected_policy_key") != identity.policy_key
            or identity.run_identity_sha256 != student.run_identity.digest
            or identity.run_seed != student.run_identity.run_seed
            or identity.generation != student.generation
            or identity.accepted_manifest_sha256 != pointer["manifest_sha256"]
            or identity.student_sha256 != candidate_identity_digest(student.retained_state)
            or identity.selection_seed != state.get("next_seed")
            or identity.cursor != state.get("cursor")):
        invalid("BAMF_REJECTION_VISIT_DRIFT")
    require_teacher_visit_receipt(identity)
    validate_teacher_visit_receipt_record(identity, expected_receipt)
    return {
        **evidence,
        "teacher_visit": identity.to_record(),
        "teacher_visit_receipt": teacher_visit_receipt_record(identity),
    }


def reconcile_bamf_outbox(
        run_dir: Path, student: CompleteStudent, *, publish_missing=True) -> bool:
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
        evidence = _portable_c03_rejection_evidence(student, pointer, evidence)
        authority = {
            "schema": "bilqis.mlx.bamf-rejection-authority/v1",
            "run_id": student.run_id,
            "generation": student.generation,
            "student_manifest_sha256": pointer["manifest_sha256"],
            "optimizer_step": optimizer_step,
            "evidence": dict(evidence),
        }
        authority_raw = canonical(authority)
        authority_sha256 = sha(authority_raw)
        data_plane().put_object(authority_sha256, authority_raw)
        event = {
            "event": "BAMF_CANDIDATE_REJECTED",
            "generation": pointer["generation"],
            "student_manifest_sha256": pointer["manifest_sha256"],
            "optimizer_step": optimizer_step,
            "evidence": dict(evidence),
            "rejection_authority_sha256": authority_sha256,
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
        _write_portable_rejection_receipt(run_dir, digest, raw)
        checkpoints._reconcile_delivery_outbox(
            run_dir, {**record, "delivery_outbox": outbox})
        return digest
