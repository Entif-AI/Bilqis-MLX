"""Public export and compatibility inspection without executing or adopting payloads."""
from .contracts import (
    ExportClassification, PackageBinding, PackageKind, PublicExportGrant, SourceRights,
    _issue_public_export_grant, require,
)
from .records import (
    CognitivePackage, ExportSnapshot, ImportPlan, _mark_public_export_authorized,
)


_PUBLIC_FIXTURE_KINDS = frozenset({
    PackageKind.FIXTURE,
    PackageKind.COUNTEREXAMPLE,
})
_PUBLIC_DERIVED_KINDS = frozenset({
    PackageKind.PROCEDURE,
    PackageKind.EXACT_TRANSFORM,
    PackageKind.ADAPTER_DELTA,
    PackageKind.WEIGHT_DELTA,
    PackageKind.BEHAVIORAL_DIFF,
})


def _artifact_classifications(artifacts):
    result = []
    for artifact in artifacts:
        if artifact.kind in _PUBLIC_FIXTURE_KINDS:
            classification = ExportClassification.PUBLIC_FIXTURE
        elif artifact.kind in _PUBLIC_DERIVED_KINDS:
            classification = ExportClassification.PUBLIC_DERIVED
        else:
            require(False, 'unsupported public export artifact kind')
        result.append((artifact.digest, classification))
    result = tuple(sorted(result, key=lambda item: item[0]))
    require(len({item[0] for item in result}) == len(result),
            'duplicate package artifact digest')
    return result


def authorize_public_export(
        generation, receipt, selection, source_frontier, authority_registry):
    """Issue a non-portable grant only after current A12 source-owner clearance."""
    from bilqis_mlx.semantics.atlas_release_audit import (
        ExportClearanceReceipt, validate_export_clearance_context,
    )

    require(type(generation) is ExportSnapshot, 'invalid source export snapshot')
    generation.__post_init__()
    require(type(receipt) is ExportClearanceReceipt, 'A12 export clearance required')
    classes = _artifact_classifications(generation.artifacts)
    digests = tuple(item[0] for item in classes)
    clearance = validate_export_clearance_context(
        receipt, selection, source_frontier, digests, authority_registry)
    rights = SourceRights(
        receipt.source_owner, clearance, receipt.export_artifact_digests,
        receipt.revoked_artifact_digests, receipt.revocation_lineage)
    return _issue_public_export_grant(rights, classes)


def export_capability(generation, signature, rights):
    require(type(generation) is ExportSnapshot, 'invalid source export snapshot')
    generation.__post_init__()
    require(type(signature) is str and signature == generation.signature,
            'package signature differs from source')
    require(type(rights) is PublicExportGrant, 'issued public export grant required')
    rights.__post_init__()
    require(
        rights.artifact_classifications == _artifact_classifications(generation.artifacts),
        'public export grant differs from source artifacts',
    )
    package = CognitivePackage(
        generation.generation_id, signature, generation.binding,
        generation.operator_identity, generation.artifacts,
        generation.max_memory_bytes, generation.max_storage_bytes, rights.rights)
    return _mark_public_export_authorized(package)


def stage_import(package, receiver):
    """Compare supplied labels only; this does not establish receiver custody."""
    require(type(package) is CognitivePackage, 'invalid cognitive package')
    package.__post_init__()
    require(type(receiver) is PackageBinding, 'invalid receiver binding')
    receiver.__post_init__()
    matches = package.binding == receiver
    contains_delta = any(a.kind in (PackageKind.ADAPTER_DELTA, PackageKind.WEIGHT_DELTA)
                         for a in package.artifacts)
    require(matches or not contains_delta, 'delta requires identical receiver binding')
    return ImportPlan(package.digest, receiver, 'EXACT_BINDING' if matches else 'TEACHING_ONLY')
