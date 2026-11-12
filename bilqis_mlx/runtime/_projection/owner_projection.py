"""C10.1 projections derived only from authenticated production owner custody."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.semantics.domains import contract_digest

from .akasha_outbox import AkashaEvent, AkashaEventKind, append_outbox_batch, _invalid


def _accepted_generation(root: Path):
    from bilqis_mlx.runtime.bamf_bundle.feature.acceptance import (
        accepted_binding_for_manifest,
        accepted_generation,
    )

    pointer, student = accepted_generation(root / "bamf-state.json")
    binding = accepted_binding_for_manifest(
        root,
        pointer["manifest_sha256"],
        student,
        expected_acceptance_sha256=pointer["acceptance_sha256"],
    )
    return pointer, student, binding


def _event(kind, subject_id, source_receipt_sha256, payload):
    """Owner facts without source clocks retain explicit unknown-time semantics."""
    return AkashaEvent.from_payload(
        kind=kind,
        subject_id=subject_id,
        source_receipt_sha256=source_receipt_sha256,
        payload=payload,
        source_time=None,
        effective_time=None,
        observed_at=None,
        recorded_at=None,
    )


def _factory_release_event(student, binding):
    from bilqis_mlx.runtime.bamf_bundle.factory_release.admission import (
        ParsedFactoryReleaseAdmissionBinding,
    )

    if not isinstance(binding, ParsedFactoryReleaseAdmissionBinding):
        return None
    transition = dict(student.transition)
    return _event(
        AkashaEventKind.FACTORY_RELEASE,
        "factory-release:" + binding.factory_release_sha256,
        binding.digest,
        {
            "run_id": student.run_id,
            "generation": student.generation,
            "owner_event_type": "BAMF_FACTORY_RELEASE_ADOPTION_COMMITTED",
            "predecessor_factory_release_sha256":
                binding.predecessor_factory_release_sha256,
            "factory_release_sha256": binding.factory_release_sha256,
            "transition_sha256": binding.transition_sha256,
            "admission_receipt_sha256": binding.digest,
        },
    )


def _bank_allocation_event(student, binding):
    from bilqis_mlx.runtime.bamf_bundle.atlas_admission import ParsedAtlasAdmissionBinding

    if (not isinstance(binding, ParsedAtlasAdmissionBinding)
            or dict(student.transition).get("kind") != "PARAMETER_EXTENSION"):
        return None
    return _event(
        AkashaEventKind.BANK_ALLOCATION,
        "feature-allocation:" + binding.feature_sha256,
        binding.digest,
        {
            "run_id": student.run_id,
            "generation": student.generation,
            "transition_kind": "PARAMETER_EXTENSION",
            "feature_sha256": binding.feature_sha256,
            "factory_release_sha256": binding.factory_release_sha256,
            "admission_receipt_sha256": binding.digest,
        },
    )


def _motif_event(student, binding):
    from bilqis_mlx.runtime.bamf_bundle.motif.transition import (
        is_motif_allocation_transition,
        validate_motif_allocation_transition,
    )
    from bilqis_mlx.runtime.bamf_bundle.records import canonical, sha

    transition = dict(student.transition)
    if not is_motif_allocation_transition(transition):
        return None
    validate_motif_allocation_transition(transition)
    return _event(
        AkashaEventKind.MOTIF_CANDIDATE,
        "motif-candidate:" + transition["motif_candidate_sha256"],
        binding.digest,
        {
            "run_id": student.run_id,
            "generation": student.generation,
            "motif_candidate_sha256": transition["motif_candidate_sha256"],
            "approved_context_sha256": transition["approved_context_sha256"],
            "candidate_allocation_sha256": transition["candidate_allocation_sha256"],
            "transition_sha256": sha(canonical(transition)),
            "added_pages": transition["added_pages"],
            "admission_receipt_sha256": binding.digest,
        },
    )


def _plasticity_event(root: Path, student, binding):
    if student.generation == 0 or student.parent_manifest_sha256 is None:
        return None
    from bilqis_mlx.runtime.bamf_bundle.codec import load_bamf_bundle

    parent = load_bamf_bundle(
        root / "bamf-bundles" / student.parent_manifest_sha256,
        expected_manifest_sha256=student.parent_manifest_sha256,
    )
    parent_policy = parent.retained_state.policy.to_record()
    policy = student.retained_state.policy.to_record()
    if policy == parent_policy:
        return None
    return _event(
        AkashaEventKind.PLASTICITY_EPOCH,
        f"plasticity:{student.run_id}:{student.generation}",
        binding.digest,
        {
            "run_id": student.run_id,
            "generation": student.generation,
            "optimizer_step": student.retained_state.optimizer_step,
            "mode": student.retained_state.policy.mode,
            "parent_policy_sha256": contract_digest(parent_policy),
            "policy_sha256": contract_digest(policy),
            "admission_receipt_sha256": binding.digest,
        },
    )


def events_from_accepted_bamf_generation(run_dir: Path) -> tuple[AkashaEvent, ...]:
    """Project the current accepted B13 generation without minting owner authority."""
    root = Path(run_dir)
    _pointer, student, binding = _accepted_generation(root)
    events = (
        _factory_release_event(student, binding),
        _bank_allocation_event(student, binding),
        _motif_event(student, binding),
        _plasticity_event(root, student, binding),
    )
    return tuple(event for event in events if event is not None)


def append_accepted_bamf_generation(path: Path, run_dir: Path) -> int:
    events = events_from_accepted_bamf_generation(Path(run_dir))
    return append_outbox_batch(Path(path), tuple((event, None) for event in events))


def event_from_public_package_export(
    package,
    published_path: Path,
    clearance_receipt,
    selection,
    source_frontier,
    authority_registry,
) -> AkashaEvent:
    """Project one actual A12-authorized C12 package publication."""
    from bilqis_mlx.runtime.cognitive_package.records import (
        CognitivePackage,
        _require_public_export_authorized,
    )
    from bilqis_mlx.semantics.atlas_release_audit import (
        ExportClearanceReceipt,
        validate_export_clearance_context,
    )

    if type(package) is not CognitivePackage or type(clearance_receipt) is not ExportClearanceReceipt:
        _invalid("BAMF_C10_PACKAGE_EXPORT_ARGUMENT_INVALID")
    _require_public_export_authorized(package)
    artifact_digests = tuple(sorted(artifact.digest for artifact in package.artifacts))
    clearance_sha256 = validate_export_clearance_context(
        clearance_receipt,
        selection,
        source_frontier,
        artifact_digests,
        authority_registry,
    )
    path = Path(published_path)
    expected = package.canonical_json.encode("utf-8")
    if (path.is_symlink() or not path.is_file()
            or path.name != package.digest + ".json"
            or path.read_bytes() != expected
            or package.binding.semantic_release != clearance_receipt.semantic_release
            or package.rights.clearance_digest != clearance_sha256):
        _invalid("BAMF_C10_PACKAGE_EXPORT_PUBLICATION_DRIFT")
    return _event(
        AkashaEventKind.PACKAGE_EXPORT,
        "package:" + package.digest,
        clearance_sha256,
        {
            "package_digest": package.digest,
            "generation_id": package.generation_id,
            "semantic_release": clearance_receipt.semantic_release,
            "source_owner": clearance_receipt.source_owner,
            "clearance_sha256": clearance_sha256,
            "rights_epoch": clearance_receipt.rights_epoch,
            "correction_generation": clearance_receipt.correction_generation,
        },
    )


def append_public_package_export(
    path: Path,
    package,
    published_path: Path,
    clearance_receipt,
    selection,
    source_frontier,
    authority_registry,
) -> int:
    event = event_from_public_package_export(
        package,
        published_path,
        clearance_receipt,
        selection,
        source_frontier,
        authority_registry,
    )
    return int(append_outbox_batch(Path(path), ((event, None),)))


__all__ = (
    "append_accepted_bamf_generation",
    "append_public_package_export",
    "event_from_public_package_export",
    "events_from_accepted_bamf_generation",
)
