"""Read-only inspection of retired pre-v2 training evidence."""
from __future__ import annotations

import json
from pathlib import Path

from ..data_plane import verify_file_digest
from ..errors import ErrorBus, SCHOOL
from ..runtime.mlx_checkpoint import SCHEMA as BUNDLE_SCHEMA, _read_catalog


def inspect_historical_run(run_dir, receipt):
    """Verify recorded identities/checksums without loading a model or optimizer."""
    if (receipt.get("schema") != "bilqis.mlx.human-grade-a-trainer/v1" or
            receipt.get("factory_admission_v2") is not None):
        ErrorBus.Raise(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason="HUMAN_TRAINER_RESUME_SOURCE_OR_POLICY_DRIFT")
    school = receipt.get("school") or {}
    student = school.get("current_student") or {}
    filename = receipt.get("model_bundle")
    if (not isinstance(receipt.get("run_id"), str) or not receipt["run_id"] or
            type(receipt.get("generation")) is not int or receipt["generation"] < 0 or
            not isinstance(filename, str) or student.get("filename") != filename or
            type(student.get("optimizer_step")) is not int or student["optimizer_step"] < 0 or
            student.get("model_and_native_adamw") is not True):
        ErrorBus.Raise(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason="HUMAN_TRAINER_RESUME_MODEL_ADAMW_OR_SEMANTIC_DRIFT")
    root = Path(run_dir)
    relative = Path(filename)
    if relative.parent != Path("bundles"):
        ErrorBus.Raise(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason="HUMAN_TRAINER_BUNDLE_PATH_ESCAPES_RUN")
    directory = root / relative
    if directory.is_symlink() or directory.resolve(strict=True).parent != (root / "bundles").resolve(strict=True):
        ErrorBus.Raise(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason="HUMAN_TRAINER_BUNDLE_PATH_ESCAPES_RUN")
    manifest_file = directory / "manifest.json"
    blob = directory / "model-and-own-adamw.safetensors"
    if manifest_file.is_symlink() or blob.is_symlink():
        ErrorBus.Raise(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason="HUMAN_TRAINER_BUNDLE_PATH_ESCAPES_RUN")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("schema") != BUNDLE_SCHEMA:
        ErrorBus.Raise(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason="MLX_BUNDLE_SCHEMA_DRIFT")
    if not verify_file_digest(blob, manifest.get("safetensors_sha256")):
        ErrorBus.Raise(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason="MLX_BUNDLE_TENSOR_FILE_CORRUPTED")
    if (manifest.get("safetensors_sha256") != student.get("sha256") or
            manifest.get("optimizer_step") != student["optimizer_step"]):
        ErrorBus.Raise(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason="HUMAN_TRAINER_RESUME_MODEL_ADAMW_OR_SEMANTIC_DRIFT")
    if manifest.get("semantic_catalog") is not None:
        _read_catalog(directory, manifest["semantic_catalog"])
    if receipt.get("factory_admission") is not None:
        from ..runtime.admission import _verified_legacy_upgrade_release
        _verified_legacy_upgrade_release(root, receipt)
    return {
        "runtime_schema": receipt["schema"], "bundle_schema": manifest["schema"],
        "run_id": receipt["run_id"], "generation": receipt["generation"],
        "student_sha256": student["sha256"], "optimizer_step": student["optimizer_step"],
        "curriculum_mode": receipt.get("curriculum_mode"),
        "course_digest": school.get("course_digest"),
        "semantic_graph_sha256": receipt.get("semantic_graph_sha256"),
        "source_digest": manifest.get("source_digest"),
        "payload_checksum": "VERIFIED", "tensor_contents": "NOT_INSPECTED",
        "recorded_state": json.loads(json.dumps(receipt)),
    }
