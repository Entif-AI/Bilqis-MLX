"""Public export and compatibility inspection without executing or adopting payloads."""
from .contracts import (
    ExportClassification, PackageBinding, PackageKind, SourceRights, require,
)
from .records import CognitivePackage, ExportSnapshot, ImportPlan


def export_capability(generation, signature, rights):
    require(type(generation) is ExportSnapshot, 'invalid source export snapshot')
    generation.__post_init__()
    require(type(signature) is str and signature == generation.signature,
            'package signature differs from source')
    require(type(rights) is SourceRights, 'invalid source clearance record')
    require(all(artifact.classification in {
                ExportClassification.PUBLIC_FIXTURE,
                ExportClassification.PUBLIC_DERIVED,
            } for artifact in generation.artifacts),
            'public export classification rejects private or unclassified material')
    return CognitivePackage(
        generation.generation_id, signature, generation.binding,
        generation.operator_identity, generation.artifacts,
        generation.max_memory_bytes, generation.max_storage_bytes, rights)


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
