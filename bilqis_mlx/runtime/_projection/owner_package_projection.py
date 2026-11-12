"""A12/C12-authorized public package projection into C10."""
from pathlib import Path

from .akasha_outbox import AkashaEventKind, _invalid


def build_package_adapters(issue):
    def event_from(
        package, published_path: Path, clearance_receipt, selection,
        source_frontier, authority_registry,
    ):
        from bilqis_mlx.runtime.cognitive_package.records import (
            CognitivePackage, _require_public_export_authorized,
        )
        from bilqis_mlx.semantics.atlas_release_audit import (
            ExportClearanceReceipt, validate_export_clearance_context,
        )
        if (type(package) is not CognitivePackage
                or type(clearance_receipt) is not ExportClearanceReceipt):
            _invalid("BAMF_C10_PACKAGE_EXPORT_ARGUMENT_INVALID")
        _require_public_export_authorized(package)
        artifact_digests = tuple(sorted(
            artifact.digest for artifact in package.artifacts))
        clearance_sha256 = validate_export_clearance_context(
            clearance_receipt, selection, source_frontier,
            artifact_digests, authority_registry)
        path = Path(published_path)
        if (path.is_symlink() or not path.is_file()
                or path.name != package.digest + ".json"
                or path.read_bytes() != package.canonical_json.encode("utf-8")
                or package.binding.semantic_release
                != clearance_receipt.semantic_release
                or package.rights.clearance_digest != clearance_sha256):
            _invalid("BAMF_C10_PACKAGE_EXPORT_PUBLICATION_DRIFT")
        return issue(
            kind=AkashaEventKind.PACKAGE_EXPORT,
            subject_id="package:" + package.digest,
            source_receipt_sha256=clearance_sha256,
            payload={
                "package_digest": package.digest,
                "generation_id": package.generation_id,
                "semantic_release": clearance_receipt.semantic_release,
                "source_owner": clearance_receipt.source_owner,
                "clearance_sha256": clearance_sha256,
                "rights_epoch": clearance_receipt.rights_epoch,
                "correction_generation": clearance_receipt.correction_generation,
            },
            source_time=None, effective_time=None, observed_at=None, recorded_at=None)

    def append(
        package, published_path, clearance_receipt, selection,
        source_frontier, authority_registry, domain,
    ):
        from .bamf_projection import (
            BamfProjectionEvent, ProjectionDomainContract, project_generation_outbox,
        )
        if not isinstance(domain, ProjectionDomainContract):
            _invalid("BAMF_C10_OWNER_PROJECTION_DOMAIN_REQUIRED")
        event = event_from(
            package, published_path, clearance_receipt, selection,
            source_frontier, authority_registry)
        projected = BamfProjectionEvent(
            event, domain.source_id, domain.release_digest, domain.model_digest,
            domain.evaluator_digest, domain.rights_digest, domain.as_of)
        return project_generation_outbox((projected,), domain)

    return event_from, append
