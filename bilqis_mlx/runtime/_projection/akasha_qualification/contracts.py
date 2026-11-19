"""Content-addressed qualification receipt for the physical Akasha/Falkor topology."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import statistics

from bilqis_mlx.runtime.akasha_domains import DOMAIN_CONTRACTS
from bilqis_mlx.runtime.akasha_security import DOMAIN_SECURITY_POLICIES
from .common import (
    QUALIFICATION_SCHEMA,
    TOPOLOGY_ID,
    QualificationDataset,
    QualificationEnvironment,
    _canonical,
    _digest,
    _git_sha,
    _invalid,
    _name,
    _sha,
)

MIN_LATENCY_SAMPLES = 5


@dataclass(frozen=True)
class QualificationMeasurements:
    rebuild_seconds: float
    restore_seconds: float
    idempotent_seconds: float
    read_latency_ms: tuple[float, ...]
    nodes: int
    edges: int
    indexes: int
    canonical_rdf_bytes: int
    backup_bytes: int
    idempotent_node_growth: int = 0
    idempotent_edge_growth: int = 0

    def __post_init__(self) -> None:
        durations = (self.rebuild_seconds, self.restore_seconds, self.idempotent_seconds)
        sizes = (self.nodes, self.edges, self.indexes,
                 self.canonical_rdf_bytes, self.backup_bytes)
        if (any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0
                for value in durations)
                or len(self.read_latency_ms) < MIN_LATENCY_SAMPLES
                or any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0
                       for value in self.read_latency_ms)
                or any(type(value) is not int or value <= 0 for value in sizes)
                or self.idempotent_node_growth != 0
                or self.idempotent_edge_growth != 0):
            _invalid("AKASHA_QUALIFICATION_MEASUREMENTS_INVALID")

    def to_record(self) -> dict:
        ordered = sorted(float(value) for value in self.read_latency_ms)
        p95_index = max(0, math.ceil(len(ordered) * 0.95) - 1)
        return {
            "rebuild_seconds": self.rebuild_seconds,
            "restore_seconds": self.restore_seconds,
            "idempotent_seconds": self.idempotent_seconds,
            "read_latency_ms": self.read_latency_ms,
            "read_latency_p50_ms": statistics.median(ordered),
            "read_latency_p95_ms": ordered[p95_index],
            "nodes": self.nodes,
            "edges": self.edges,
            "indexes": self.indexes,
            "canonical_rdf_bytes": self.canonical_rdf_bytes,
            "backup_bytes": self.backup_bytes,
            "idempotent_node_growth": self.idempotent_node_growth,
            "idempotent_edge_growth": self.idempotent_edge_growth,
        }


@dataclass(frozen=True)
class QualificationOutcomes:
    backup_restore_identity_match: bool
    backup_restore_census_match: bool
    backup_restore_query_match: bool
    clean_rebuild_match: bool
    stale_detected: bool
    corruption_detected: bool
    partial_recovery: bool
    foreign_isolation: bool
    restart_reconnect: bool
    logical_domain_isolation: bool

    def __post_init__(self) -> None:
        if not all(value is True for value in self.to_record().values()):
            _invalid("AKASHA_QUALIFICATION_OUTCOME_INCOMPLETE")

    def to_record(self) -> dict:
        return {
            "backup_restore_identity_match": self.backup_restore_identity_match,
            "backup_restore_census_match": self.backup_restore_census_match,
            "backup_restore_query_match": self.backup_restore_query_match,
            "clean_rebuild_match": self.clean_rebuild_match,
            "stale_detected": self.stale_detected,
            "corruption_detected": self.corruption_detected,
            "partial_recovery": self.partial_recovery,
            "foreign_isolation": self.foreign_isolation,
            "restart_reconnect": self.restart_reconnect,
            "logical_domain_isolation": self.logical_domain_isolation,
        }


@dataclass(frozen=True)
class AkashaQualificationReceipt:
    candidate_revision: str
    environment: QualificationEnvironment
    dataset: QualificationDataset
    measurements: QualificationMeasurements
    outcomes: QualificationOutcomes
    prerequisite_heads: tuple[tuple[str, str], ...]
    commands: tuple[str, ...]
    residual_debt: tuple[str, ...]
    domain_contract_set_sha256: str
    security_policy_set_sha256: str
    receipt_sha256: str
    topology_id: str = field(default=TOPOLOGY_ID, init=False)
    status: str = field(default="PASSED", init=False)
    schema_version: str = field(default=QUALIFICATION_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if (not _git_sha(self.candidate_revision)
                or not isinstance(self.environment, QualificationEnvironment)
                or not isinstance(self.dataset, QualificationDataset)
                or not isinstance(self.measurements, QualificationMeasurements)
                or not isinstance(self.outcomes, QualificationOutcomes)
                or not self.prerequisite_heads
                or any(not _name(label) or not _git_sha(head)
                       for label, head in self.prerequisite_heads)
                or len({label for label, _ in self.prerequisite_heads})
                    != len(self.prerequisite_heads)
                or not self.commands or any(not _name(item) for item in self.commands)
                or any(not _name(item) for item in self.residual_debt)
                or not _sha(self.domain_contract_set_sha256)
                or not _sha(self.security_policy_set_sha256)
                or self.topology_id != TOPOLOGY_ID
                or self.status != "PASSED"
                or self.schema_version != QUALIFICATION_SCHEMA
                or self.receipt_sha256 != _digest(self._identity_record())):
            _invalid("AKASHA_QUALIFICATION_RECEIPT_INVALID")

    def _identity_record(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "topology_id": self.topology_id,
            "candidate_revision": self.candidate_revision,
            "environment": self.environment.to_record(),
            "dataset": self.dataset.to_record(),
            "measurements": self.measurements.to_record(),
            "outcomes": self.outcomes.to_record(),
            "prerequisite_heads": self.prerequisite_heads,
            "commands": self.commands,
            "residual_debt": self.residual_debt,
            "domain_contract_set_sha256": self.domain_contract_set_sha256,
            "security_policy_set_sha256": self.security_policy_set_sha256,
        }

    @property
    def canonical_json(self) -> str:
        return _canonical({**self._identity_record(), "receipt_sha256": self.receipt_sha256})

    @classmethod
    def create(cls, *, candidate_revision: str, environment: QualificationEnvironment,
               dataset: QualificationDataset, measurements: QualificationMeasurements,
               outcomes: QualificationOutcomes,
               prerequisite_heads: tuple[tuple[str, str], ...],
               commands: tuple[str, ...], residual_debt: tuple[str, ...]):
        domain_digest = _digest(tuple(
            (domain.value, contract.digest)
            for domain, contract in sorted(DOMAIN_CONTRACTS.items(), key=lambda item: item[0].value)))
        security_digest = _digest(tuple(
            (domain.value, policy.policy_sha256)
            for domain, policy in sorted(
                DOMAIN_SECURITY_POLICIES.items(), key=lambda item: item[0].value)))
        values = {
            "candidate_revision": candidate_revision,
            "environment": environment,
            "dataset": dataset,
            "measurements": measurements,
            "outcomes": outcomes,
            "prerequisite_heads": prerequisite_heads,
            "commands": commands,
            "residual_debt": residual_debt,
            "domain_contract_set_sha256": domain_digest,
            "security_policy_set_sha256": security_digest,
        }
        provisional = cls.__new__(cls)
        for key, value in values.items():
            object.__setattr__(provisional, key, value)
        object.__setattr__(provisional, "topology_id", TOPOLOGY_ID)
        object.__setattr__(provisional, "status", "PASSED")
        object.__setattr__(provisional, "schema_version", QUALIFICATION_SCHEMA)
        object.__setattr__(provisional, "receipt_sha256", "")
        return cls(**values, receipt_sha256=_digest(provisional._identity_record()))


__all__ = (
    "AkashaQualificationReceipt", "QualificationDataset", "QualificationEnvironment",
    "QualificationMeasurements", "QualificationOutcomes", "QUALIFICATION_SCHEMA",
    "TOPOLOGY_ID",
)
