"""Primitive qualification identities and environment/dataset contracts."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from bilqis_mlx.errors import ErrorBus, SCHOOL


QUALIFICATION_SCHEMA = "bilqis.akasha.topology-qualification/v1"
TOPOLOGY_ID = "single-falkor-service-logically-federated/v1"


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_AKASHA.INVALID, reason=reason)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _sha(value: object) -> bool:
    return (isinstance(value, str) and len(value) == len(hashlib.sha256().hexdigest())
            and all(char in "0123456789abcdef" for char in value))


def _git_sha(value: object) -> bool:
    return (isinstance(value, str) and len(value) in (40, 64)
            and all(char in "0123456789abcdef" for char in value))


def _name(value: object) -> bool:
    return isinstance(value, str) and bool(value)


@dataclass(frozen=True)
class QualificationEnvironment:
    platform: str
    machine: str
    python: str
    falkordb_client: str
    redis_client: str
    server_version: str
    endpoint: str

    def __post_init__(self) -> None:
        if any(not _name(value) for value in self.to_record().values()):
            _invalid("AKASHA_QUALIFICATION_ENVIRONMENT_INVALID")

    def to_record(self) -> dict:
        return {
            "platform": self.platform,
            "machine": self.machine,
            "python": self.python,
            "falkordb_client": self.falkordb_client,
            "redis_client": self.redis_client,
            "server_version": self.server_version,
            "endpoint": self.endpoint,
        }


@dataclass(frozen=True)
class QualificationDataset:
    release_ref: str
    canonical_rdf_sha256: str
    canonical_triples: int
    bundle_manifest_sha256: str
    suite_sha256: str
    prior_live_proof_sha256: str

    def __post_init__(self) -> None:
        if (not _name(self.release_ref)
                or any(not _sha(value) for value in (
                    self.canonical_rdf_sha256, self.bundle_manifest_sha256,
                    self.suite_sha256, self.prior_live_proof_sha256))
                or type(self.canonical_triples) is not int
                or self.canonical_triples <= 0):
            _invalid("AKASHA_QUALIFICATION_DATASET_INVALID")

    def to_record(self) -> dict:
        return {
            "release_ref": self.release_ref,
            "canonical_rdf_sha256": self.canonical_rdf_sha256,
            "canonical_triples": self.canonical_triples,
            "bundle_manifest_sha256": self.bundle_manifest_sha256,
            "suite_sha256": self.suite_sha256,
            "prior_live_proof_sha256": self.prior_live_proof_sha256,
        }
