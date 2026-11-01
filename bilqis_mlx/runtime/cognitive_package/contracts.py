"""Immutable package address, payload and source-clearance contracts."""
from dataclasses import dataclass, fields
from enum import Enum
from hashlib import sha256
import re
from bilqis_mlx.errors import ErrorBus, SCHOOL


def invalid(reason):
    ErrorBus.raise_(SCHOOL.BAMF_PACKAGE.INVALID, reason=reason)


def require(condition, reason):
    if not condition:
        invalid(reason)


def name(value):
    return (type(value) is str and bool(value.strip())
            and all(ord(c) >= 32 and not 0xD800 <= ord(c) <= 0xDFFF for c in value))


def digest_string(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def digest_tuple(value):
    return (type(value) is tuple and all(digest_string(d) for d in value)
            and value == tuple(sorted(set(value))))


class PackageKind(str, Enum):
    PROCEDURE = 'procedure'
    EXACT_TRANSFORM = 'exact_transform'
    ADAPTER_DELTA = 'adapter_delta'
    WEIGHT_DELTA = 'weight_delta'
    FIXTURE = 'fixture'
    COUNTEREXAMPLE = 'counterexample'
    BEHAVIORAL_DIFF = 'behavioral_diff'


@dataclass(frozen=True)
class PackageBinding:
    base_weight_digest: str
    parameter_schema_digest: str
    topology_digest: str
    semantic_release: str
    active_set_digest: str
    factor_map_digest: str
    motif_key_map_digest: str

    def __post_init__(self):
        require(all(digest_string(getattr(self, f.name)) for f in fields(self)),
                'invalid package binding digest')


@dataclass(frozen=True)
class PackageArtifact:
    artifact_id: str
    kind: PackageKind
    payload: bytes

    def __post_init__(self):
        require(name(self.artifact_id) and type(self.kind) is PackageKind
                and type(self.payload) is bytes and bool(self.payload),
                'invalid package artifact')

    @property
    def digest(self):
        return sha256(self.payload).hexdigest()


@dataclass(frozen=True)
class SourceRights:
    authority_id: str
    clearance_digest: str
    public_artifact_digests: tuple[str, ...]
    revoked_artifact_digests: tuple[str, ...]
    revocation_lineage: tuple[str, ...]

    def __post_init__(self):
        require(name(self.authority_id) and digest_string(self.clearance_digest)
                and all(digest_tuple(v) for v in (self.public_artifact_digests,
                    self.revoked_artifact_digests, self.revocation_lineage)),
                'invalid source clearance record')

    def check(self, artifacts):
        self.__post_init__()
        for artifact in artifacts:
            require(artifact.digest not in self.revoked_artifact_digests,
                    'artifact clearance revoked')
            require(artifact.digest in self.public_artifact_digests,
                    'artifact lacks public clearance')
