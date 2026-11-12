"""C10.1 projections derived only from authenticated production owner custody."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bilqis_mlx.semantics.domains import contract_digest

from .akasha_outbox import AkashaEvent, AkashaEventKind, _invalid
from .akasha_outbox.events import _from_owner_payload


_ACCEPTED_SOURCE_ISSUER = object()


@dataclass(frozen=True, init=False)
class _AcceptedGenerationProjectionSource:
    root: Path
    student: object
    binding: object
    parent: object | None
    parent_binding: object | None
    _issuance: object

    def __init__(self, *args, **kwargs):
        _invalid("BAMF_C10_ACCEPTED_OWNER_SOURCE_REQUIRED")


def _issue_accepted_source(root, student, binding, parent, parent_binding):
    source = object.__new__(_AcceptedGenerationProjectionSource)
    for name, value in (
            ("root", root), ("student", student), ("binding", binding),
            ("parent", parent), ("parent_binding", parent_binding),
            ("_issuance", _ACCEPTED_SOURCE_ISSUER)):
        object.__setattr__(source, name, value)
    return source


def _require_accepted_source(source):
    if (type(source) is not _AcceptedGenerationProjectionSource
            or source._issuance is not _ACCEPTED_SOURCE_ISSUER):
        _invalid("BAMF_C10_ACCEPTED_OWNER_SOURCE_REQUIRED")
    return source


def _accepted_generation(root: Path):
    from bilqis_mlx.runtime.bamf_bundle.feature.acceptance import (
        accepted_binding_for_manifest,
        accepted_generation,
        parent_acceptance_anchor_from_manifest,
    )
    from bilqis_mlx.runtime.bamf_bundle.codec import load_bamf_bundle

    pointer, student = accepted_generation(root / "bamf-state.json")
    binding = accepted_binding_for_manifest(
        root,
        pointer["manifest_sha256"],
        student,
        expected_acceptance_sha256=pointer["acceptance_sha256"],
    )
    parent = None
    parent_binding = None
    if student.parent_manifest_sha256 is not None:
        parent = load_bamf_bundle(
            root / "bamf-bundles" / student.parent_manifest_sha256,
            expected_manifest_sha256=student.parent_manifest_sha256,
        )
        parent_acceptance_sha256 = parent_acceptance_anchor_from_manifest(
            root, pointer["manifest_sha256"])
        if parent_acceptance_sha256 is not None:
            parent_binding = accepted_binding_for_manifest(
                root,
                student.parent_manifest_sha256,
                parent,
                expected_acceptance_sha256=parent_acceptance_sha256,
            )
    return _issue_accepted_source(root, student, binding, parent, parent_binding)


def _event(kind, subject_id, source_receipt_sha256, payload):
    """Owner facts without source clocks retain explicit unknown-time semantics."""
    return _from_owner_payload(
        kind=kind,
        subject_id=subject_id,
        source_receipt_sha256=source_receipt_sha256,
        payload=payload,
        source_time=None,
        effective_time=None,
        observed_at=None,
        recorded_at=None,
    )


def _factory_release_event(source):
    from bilqis_mlx.runtime.bamf_bundle.factory_release.admission import (
        ParsedFactoryReleaseAdmissionBinding,
    )

    source = _require_accepted_source(source)
    student, binding = source.student, source.binding
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


def _bank_allocation_event(source):
    from bilqis_mlx.runtime.bamf_bundle.atlas_admission import ParsedAtlasAdmissionBinding

    source = _require_accepted_source(source)
    student, binding = source.student, source.binding
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


def _motif_event(source):
    from bilqis_mlx.learning.atlas_acceptance import MOTIF_CLOSURE_ACCEPTANCE_SCHEMA
    from bilqis_mlx.runtime.bamf_bundle.motif.transition import (
        is_motif_allocation_transition,
        validate_motif_allocation_transition,
    )
    from bilqis_mlx.runtime.bamf_bundle.records import canonical, sha

    source = _require_accepted_source(source)
    student, binding = source.student, source.binding
    transition = dict(student.transition)
    if (getattr(binding, "schema_version", None) != MOTIF_CLOSURE_ACCEPTANCE_SCHEMA
            or not is_motif_allocation_transition(transition)):
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


def _plasticity_event(source):
    source = _require_accepted_source(source)
    student, binding = source.student, source.binding
    parent, parent_binding = source.parent, source.parent_binding
    if parent_binding is None or parent is None:
        return None
    parent_policy_sha256 = contract_digest(parent.retained_state.policy.to_record())
    policy_sha256 = contract_digest(student.retained_state.policy.to_record())
    if policy_sha256 == parent_policy_sha256:
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
            "parent_policy_sha256": parent_policy_sha256,
            "policy_sha256": policy_sha256,
            "parent_acceptance_receipt_sha256": parent_binding.digest,
            "admission_receipt_sha256": binding.digest,
        },
    )


def events_from_accepted_bamf_generation(run_dir: Path) -> tuple[AkashaEvent, ...]:
    """Project the current accepted B13 generation without minting owner authority."""
    root = Path(run_dir)
    source = _accepted_generation(root)
    events = (
        _factory_release_event(source),
        _bank_allocation_event(source),
        _motif_event(source),
        _plasticity_event(source),
    )
    return tuple(event for event in events if event is not None)


def _project_owner_events(events, domain):
    from .bamf_projection import BamfProjectionEvent, ProjectionDomainContract, project_generation_outbox
    if not isinstance(domain, ProjectionDomainContract):
        _invalid("BAMF_C10_OWNER_PROJECTION_DOMAIN_REQUIRED")
    projected = tuple(BamfProjectionEvent(
        event,
        domain.source_id,
        domain.release_digest,
        domain.model_digest,
        domain.evaluator_digest,
        domain.rights_digest,
        domain.as_of,
    ) for event in events)
    return project_generation_outbox(projected, domain)


def append_accepted_bamf_generation(run_dir: Path, domain):
    events = events_from_accepted_bamf_generation(Path(run_dir))
    return _project_owner_events(events, domain)


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
    package,
    published_path: Path,
    clearance_receipt,
    selection,
    source_frontier,
    authority_registry,
    domain,
):
    event = event_from_public_package_export(
        package,
        published_path,
        clearance_receipt,
        selection,
        source_frontier,
        authority_registry,
    )
    return _project_owner_events((event,), domain)


__all__ = (
    "append_accepted_bamf_generation",
    "append_public_package_export",
    "event_from_public_package_export",
    "events_from_accepted_bamf_generation",
)
