"""Source snapshots, portable manifests and read-only compatibility plans."""
from dataclasses import dataclass
from hashlib import sha256
from .contracts import (
    PackageArtifact, PackageBinding, PackageKind, SourceRights,
    digest_string, name, require,
)

_PUBLIC_EXPORT_PACKAGE_AUTHORITY = object()


def validate_snapshot(value):
    require(all(name(v) for v in (value.generation_id, value.signature,
                                 value.operator_identity)), 'invalid snapshot identity')
    require(type(value.binding) is PackageBinding, 'invalid package binding')
    value.binding.__post_init__()
    require(type(value.artifacts) is tuple and bool(value.artifacts)
            and all(type(a) is PackageArtifact for a in value.artifacts),
            'invalid package artifacts')
    for artifact in value.artifacts:
        artifact.__post_init__()
    require(len({a.artifact_id for a in value.artifacts}) == len(value.artifacts),
            'duplicate package artifact identity')
    kinds = {a.kind for a in value.artifacts}
    require(bool(kinds & {PackageKind.PROCEDURE, PackageKind.EXACT_TRANSFORM,
                         PackageKind.ADAPTER_DELTA, PackageKind.WEIGHT_DELTA})
            and {PackageKind.FIXTURE, PackageKind.COUNTEREXAMPLE,
                 PackageKind.BEHAVIORAL_DIFF} <= kinds, 'missing package artifact role')
    require(all(type(n) is int and n > 0 for n in (
        value.max_memory_bytes, value.max_storage_bytes))
        and sum(len(a.payload) for a in value.artifacts) <= value.max_storage_bytes,
        'invalid package resource envelope')


@dataclass(frozen=True)
class ExportSnapshot:
    generation_id: str
    signature: str
    binding: PackageBinding
    operator_identity: str
    artifacts: tuple[PackageArtifact, ...]
    max_memory_bytes: int
    max_storage_bytes: int

    def __post_init__(self):
        validate_snapshot(self)


@dataclass(frozen=True)
class CognitivePackage(ExportSnapshot):
    rights: SourceRights
    schema_version: str = 'bilqis.c12.cognitive-package/v1'

    def __post_init__(self):
        validate_snapshot(self)
        require(type(self.rights) is SourceRights, 'invalid source clearance record')
        require(self.schema_version == 'bilqis.c12.cognitive-package/v1',
                'unsupported package schema')
        self.rights.check(self.artifacts)

    @property
    def canonical_json(self):
        from .wire import encode_package
        self.__post_init__()
        return encode_package(self)

    @property
    def digest(self):
        return sha256(self.canonical_json.encode('utf-8')).hexdigest()

    @classmethod
    def from_canonical_json(cls, value):
        from .wire import decode_package
        return decode_package(value)


def _mark_public_export_authorized(package):
    require(type(package) is CognitivePackage, 'invalid cognitive package')
    object.__setattr__(
        package, '_public_export_authority', _PUBLIC_EXPORT_PACKAGE_AUTHORITY)
    return package


def _require_public_export_authorized(package):
    require(
        type(package) is CognitivePackage
        and getattr(package, '_public_export_authority', None)
        is _PUBLIC_EXPORT_PACKAGE_AUTHORITY,
        'public sender package lacks source export authority',
    )


@dataclass(frozen=True)
class ImportPlan:
    package_digest: str
    receiver: PackageBinding
    disposition: str

    def __post_init__(self):
        require(digest_string(self.package_digest) and type(self.receiver) is PackageBinding,
                'invalid import plan binding')
        self.receiver.__post_init__()
        require(self.disposition in ('EXACT_BINDING', 'TEACHING_ONLY'),
                'invalid import plan disposition')
