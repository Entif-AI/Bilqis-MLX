"""C12 bridge from authoritative screening into B12/B13 package-import custody."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.runtime.bamf_bundle import BamfBundleCandidate
from bilqis_mlx.runtime.bamf_bundle.admission import (
    accept_and_publish, bind_accepted_execution_cache,
)
from bilqis_mlx.runtime.bamf_bundle.package_import_transition import (
    _issue_package_import_transition,
)
from bilqis_mlx.semantics.atlas_release_audit import ExportClearanceReceipt

from .contracts import SourceRights, require
from .delta import ScreenedDeltaCandidate
from .receiver import _load_current_generation, _receiver_tensors


def _artifact_digests(package):
    return tuple(sorted(artifact.digest for artifact in package.artifacts))


def _verify_export_clearance(
        package, parent, receipt, atlas_selection, source_frontier,
        source_context, run_dir):
    require(type(receipt) is ExportClearanceReceipt, "A12 export clearance required")
    run_dir = Path(run_dir)
    source_context.require_accepted_runtime(run_dir)
    authority = source_context.source_authority()
    cache = bind_accepted_execution_cache(run_dir)
    digests = _artifact_digests(package)
    clearance = authority._validate_export_clearance_context(
        cache, receipt, atlas_selection, source_frontier, digests)
    expected = SourceRights(
        receipt.source_owner, clearance, receipt.export_artifact_digests,
        receipt.revoked_artifact_digests, receipt.revocation_lineage)
    require(package.rights == expected, "package source rights do not match current A12 clearance")
    require(package.binding.semantic_release == receipt.semantic_release,
            "package semantic release differs from A12 clearance")
    correction = parent.correction_frontier
    require(correction.get("rights_epoch") == receipt.rights_epoch
            and correction.get("correction_generation") == receipt.correction_generation,
            "receiver rights frontier differs from A12 clearance")
    return clearance


def _require_exact_parent(screened, pointer, parent):
    candidate = screened.candidate
    require(candidate.parent_generation == pointer["manifest_sha256"],
            "screened import parent is stale")
    require(candidate.parent_tensors == _receiver_tensors(parent),
            "screened import parent tensors drifted")


def _successor(parent, pointer, screened, transaction, clearance):
    decision = screened.decision
    package = screened.candidate.package
    transition = _issue_package_import_transition(
        package_sha256=package.digest,
        screened_candidate_sha256=screened.candidate.generation_digest,
        reset_policy_sha256=transaction.reset_policy_sha256,
        c05_evidence_sha256=decision.evidence_sha256,
        c05_policy_sha256=decision.policy_sha256,
        source_clearance_sha256=clearance)
    event = {
        "event": "BAMF_PACKAGE_IMPORT_ACCEPTED",
        "origin": "PACKAGE_IMPORT",
        "receiver_generation": parent.generation,
        "receiver_manifest_sha256": pointer["manifest_sha256"],
        "package_sha256": package.digest,
        "screened_candidate_sha256": screened.candidate.generation_digest,
        "reset_policy_sha256": transaction.reset_policy_sha256,
        "c05_evidence_sha256": decision.evidence_sha256,
        "c05_policy_sha256": decision.policy_sha256,
        "source_clearance_sha256": clearance,
        "optimizer_step": transaction.candidate.optimizer_step,
    }
    return BamfBundleCandidate(
        parent.run_id, parent.generation + 1, pointer["manifest_sha256"],
        parent.implementation_sha256, parent.topology, parent.extents,
        transaction.candidate, parent.optimizer_hyperparameters, parent.provenance,
        parent.semantic_abi, parent.compiler_features, parent.correction_frontier,
        parent.teacher_state, parent.evaluation_contract, transition, (event,))


def publish_screened_delta_import(
        screened, run_dir, *, export_clearance, atlas_selection, source_frontier,
        source_context, reserve_gib: float = 100.0,
):
    """Publish only an owner-issued, C05-eligible, A12-cleared exact-parent import."""
    require(type(screened) is ScreenedDeltaCandidate, "issued screened delta candidate required")
    screened.__post_init__()
    require(screened.decision.accepted, "C05 rejected package import")
    pointer, parent = _load_current_generation(Path(run_dir))
    _require_exact_parent(screened, pointer, parent)
    clearance = _verify_export_clearance(
        screened.candidate.package, parent, export_clearance, atlas_selection,
        source_frontier, source_context, run_dir)
    transaction = screened.transaction
    successor = _successor(parent, pointer, screened, transaction, clearance)
    return accept_and_publish(
        Path(run_dir), successor, transaction.candidate,
        decision=screened.decision,
        feature_sha256=successor.extents.factor_map_digest,
        reserve_gib=reserve_gib)
