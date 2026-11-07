"""Historical acceptance verification for B13 feature-lineage replay."""
from __future__ import annotations

import json
from pathlib import Path

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import (
    ACCEPTANCE_SCHEMA, AcceptedCandidateBinding, candidate_identity_digest,
)

from .codec import load_bamf_bundle
from .publication import ACCEPTANCE_DIR, _pointer_lock, _read_pointer
from .records import (
    ACCEPTANCE_BOUND_BAMF_BUNDLE_SCHEMA, BamfGenerationManifest, invalid, sha,
)
from ._feature_receipt import is_digest


def accepted_generation(pointer_path: Path):
    """Read the published accepted generation under the custody pointer lock."""
    pointer_path = Path(pointer_path)
    with _pointer_lock(pointer_path.parent):
        pointer = _read_pointer(pointer_path)
        if pointer is None:
            invalid("BAMF_FEATURE_POINTER_MISSING")
        student = load_bamf_bundle(
            pointer_path.parent / "bamf-bundles" / pointer["manifest_sha256"],
            expected_manifest_sha256=pointer["manifest_sha256"])
        if (student.run_id != pointer["run_id"]
                or student.generation != pointer["generation"]
                or student.parent_manifest_sha256 != pointer["parent_manifest_sha256"]):
            invalid("BAMF_FEATURE_POINTER_DRIFT")
    return pointer, student


def accepted_binding_for_manifest(
        run_dir: Path, manifest_sha256: str, student, *,
        expected_acceptance_sha256: str) -> AcceptedCandidateBinding:
    """Authenticate one immutable generation's retained-acceptance evidence."""
    path = run_dir / ACCEPTANCE_DIR / f"{manifest_sha256}.json"
    if path.is_symlink() or not path.is_file():
        invalid("BAMF_GENERATION_ACCEPTANCE_MISSING")
    try:
        binding = AcceptedCandidateBinding.from_record(json.loads(path.read_bytes()))
    except (UnicodeDecodeError, json.JSONDecodeError, BilqisError):
        invalid("BAMF_GENERATION_ACCEPTANCE_INVALID")
    if (binding.digest != expected_acceptance_sha256
            or binding.schema_version != ACCEPTANCE_SCHEMA
            or binding.run_id != student.run_id
            or binding.generation != student.generation
            or binding.feature_sha256 != student.extents.factor_map_digest
            or binding.optimizer_step != student.retained_state.optimizer_step
            or binding.candidate_identity_sha256
            != candidate_identity_digest(student.retained_state)
            or binding.step_proof_sha256 != tuple(
                proof.digest for proof in student.retained_state.step_proofs)):
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    if student.generation > 0:
        parent_sha = student.parent_manifest_sha256
        if parent_sha is None:
            invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
        parent = load_bamf_bundle(
            run_dir / "bamf-bundles" / parent_sha,
            expected_manifest_sha256=parent_sha)
        if (parent.generation + 1 != student.generation
                or parent.run_id != student.run_id
                or binding.parent_candidate_identity_sha256
                != candidate_identity_digest(parent.retained_state)):
            invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    return binding


def parent_acceptance_from_manifest(run_dir: Path, manifest_sha256: str) -> str:
    """Read the immutable child-manifest binding to its accepted parent receipt."""
    path = run_dir / "bamf-bundles" / manifest_sha256 / "manifest.json"
    if path.is_symlink() or not path.is_file():
        invalid("BAMF_GENERATION_ACCEPTANCE_MISSING")
    raw = path.read_bytes()
    if sha(raw) != manifest_sha256:
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    try:
        manifest = BamfGenerationManifest.from_record(json.loads(raw)).to_record()
    except (UnicodeDecodeError, json.JSONDecodeError, BilqisError):
        invalid("BAMF_GENERATION_ACCEPTANCE_INVALID")
    parent_acceptance = manifest.get("parent_acceptance_sha256")
    if (manifest.get("schema") != ACCEPTANCE_BOUND_BAMF_BUNDLE_SCHEMA
            or not is_digest(parent_acceptance)):
        invalid("BAMF_GENERATION_ACCEPTANCE_MISSING")
    return parent_acceptance
