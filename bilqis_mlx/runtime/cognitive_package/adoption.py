"""C12 accepted package import through A12, C05, B12 and B13 owners."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import mlx.core as mx
import numpy as np

from bilqis_mlx.learning.atlas_package_import import (
    IMPORT_ORIGIN, ImportResetSlice, begin_package_import,
)
from bilqis_mlx.runtime.atlas_revalidation import SourceAuthorityRegistry
from bilqis_mlx.runtime.bamf_bundle import BamfBundleCandidate, publish_bamf_generation
from bilqis_mlx.runtime.bamf_bundle import publication
from bilqis_mlx.runtime.bamf_bundle.records import _issue_package_import_candidate
from bilqis_mlx.runtime.capability_retention import DecisionStatus
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_release_audit import (
    ExportClearanceReceipt, validate_export_clearance_context,
)
from bilqis_mlx.semantics.context_eligibility import SourceFrontier
from bilqis_mlx.semantics.domains import contract_digest

from .contracts import require
from .delta import ScreenedDeltaCandidate, _all_delta_slices


LINEAGE_SCHEMA = "bilqis.c12.package-import-lineage/v1"


@dataclass(frozen=True)
class PackageImportOutcome:
    status: str
    parent_manifest_sha256: str
    package_sha256: str
    reset_policy_sha256: str | None
    c05_decision_sha256: str
    a12_clearance_sha256: str
    published_manifest_sha256: str | None = None


def _artifact_digests(package):
    return tuple(sorted(artifact.digest for artifact in package.artifacts))


def _verify_clearance(screened, clearance, selection, frontier, registry):
    package = screened.candidate.package
    require(type(clearance) is ExportClearanceReceipt,
            "authoritative A12 export clearance required")
    require(type(selection) is AtlasArtifactSelection,
            "authoritative A12 release selection required")
    require(type(frontier) is SourceFrontier, "live source frontier required")
    require(type(registry) is SourceAuthorityRegistry,
            "trusted source authority registry required")
    registry.verify_detached(
        clearance.source_owner, clearance.dependency(),
        clearance.signature_hex, clearance.signing_bytes())
    artifacts = _artifact_digests(package)
    validate_export_clearance_context(clearance, selection, frontier, artifacts)
    rights = package.rights
    require(rights.authority_id == clearance.source_owner
            and rights.clearance_digest == clearance.clearance_sha256
            and rights.public_artifact_digests == clearance.export_artifact_digests
            and rights.revoked_artifact_digests == clearance.revoked_artifact_digests
            and rights.revocation_lineage == clearance.revocation_lineage,
            "package source rights do not project current A12 authority")
    return clearance.clearance_sha256


def _current_receiver(screened, run_dir):
    run_dir = Path(run_dir)
    with publication._pointer_lock(run_dir):
        pointer = publication._read_pointer(run_dir / "bamf-state.json")
        require(pointer is not None, "receiver generation pointer missing")
        publication._live_bundle_manifest(run_dir, pointer)
        student = publication.load_bamf_bundle(
            run_dir / pointer["bundle"],
            expected_manifest_sha256=pointer["manifest_sha256"])
        require(pointer["manifest_sha256"] == screened.candidate.parent_generation,
                "screened package parent is stale")
        require(student.run_id == pointer["run_id"]
                and student.generation == pointer["generation"],
                "receiver generation pointer drift")
        return pointer, student


def _reset_slices(screened):
    return tuple(sorted(
        ImportResetSlice(item.parameter_name, item.start, item.stop)
        for item in _all_delta_slices(screened.candidate.package)))


def _imported_parameters(screened, student):
    tensors = {item.parameter_name: item for item in screened.candidate.tensors}
    require(set(tensors) == set(student.retained_state.optimizer.parameters),
            "screened package tensor set drifted from receiver")
    return {
        name: mx.array(np.frombuffer(tensors[name].values_fp32, dtype="<f4")
                       .reshape(tensors[name].shape), dtype=mx.float32)
        for name in sorted(tensors)
    }


def _bundle_candidate(screened, pointer, student, transaction, clearance_sha256):
    decision = screened.decision
    decision_sha256 = contract_digest(decision)
    lineage = {
        "schema": LINEAGE_SCHEMA,
        "origin": IMPORT_ORIGIN,
        "parent_manifest_sha256": pointer["manifest_sha256"],
        "package_sha256": screened.candidate.package.digest,
        "reset_policy_sha256": transaction.reset_policy_sha256,
        "c05_decision_sha256": decision_sha256,
        "c05_evidence_sha256": decision.evidence_sha256,
        "c05_policy_sha256": decision.policy_sha256,
        "a12_clearance_sha256": clearance_sha256,
        "prior_evaluation_contract_sha256": student.evaluation_contract["contract_sha256"],
    }
    evaluation = {
        **dict(student.evaluation_contract),
        "contract_sha256": contract_digest(lineage),
        "package_import": lineage,
    }
    event = {
        "event": "BAMF_PACKAGE_IMPORT_ACCEPTED",
        "parent_manifest_sha256": pointer["manifest_sha256"],
        "package_sha256": screened.candidate.package.digest,
        "reset_policy_sha256": transaction.reset_policy_sha256,
        "c05_decision_sha256": decision_sha256,
        "a12_clearance_sha256": clearance_sha256,
        "optimizer_step": transaction.retained.optimizer_step,
    }
    base = BamfBundleCandidate(
        student.run_id, student.generation + 1, pointer["manifest_sha256"],
        student.implementation_sha256, student.topology, student.extents,
        transaction.retained, student.optimizer_hyperparameters, student.provenance,
        student.semantic_abi, student.compiler_features, student.correction_frontier,
        student.teacher_state, evaluation,
        {"schema": "bilqis.mlx.bamf-generation-transition/v1",
         "kind": "PACKAGE_IMPORT", "invalidate_derived_caches": True},
        (event,),
    )
    return _issue_package_import_candidate(
        base, package_sha256=screened.candidate.package.digest,
        reset_policy_sha256=transaction.reset_policy_sha256,
        acceptance_sha256=decision_sha256, clearance_sha256=clearance_sha256)


def adopt_screened_delta(
        screened, run_dir, *, clearance_receipt, selection, source_frontier,
        authority_registry, reserve_gib: float = 100.0) -> PackageImportOutcome:
    """Publish only an owner-screened, owner-cleared package import generation."""
    require(type(screened) is ScreenedDeltaCandidate, "sealed C05 screen required")
    screened.__post_init__()
    clearance_sha256 = _verify_clearance(
        screened, clearance_receipt, selection, source_frontier, authority_registry)
    decision_sha256 = contract_digest(screened.decision)
    if screened.decision.status is DecisionStatus.REJECT:
        return PackageImportOutcome(
            "REJECTED", screened.candidate.parent_generation,
            screened.candidate.package.digest, None, decision_sha256, clearance_sha256)
    require(screened.decision.status is DecisionStatus.ELIGIBLE,
            "unsupported C05 screening decision")
    pointer, student = _current_receiver(screened, run_dir)
    transaction = begin_package_import(
        student.retained_state, _imported_parameters(screened, student),
        _reset_slices(screened), parent_manifest_sha256=pointer["manifest_sha256"],
        package_sha256=screened.candidate.package.digest)
    candidate = _bundle_candidate(
        screened, pointer, student, transaction, clearance_sha256)
    published = publish_bamf_generation(run_dir, candidate, reserve_gib=reserve_gib)
    return PackageImportOutcome(
        "PUBLISHED", pointer["manifest_sha256"], screened.candidate.package.digest,
        transaction.reset_policy_sha256, decision_sha256, clearance_sha256,
        published["manifest_sha256"])

