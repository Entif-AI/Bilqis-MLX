"""Immutable contracts for Akasha projection lifecycle custody."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from bilqis_mlx.runtime.akasha_domains import (
    AkashaDomain,
    DOMAIN_CONTRACTS,
    rebuild_projection_identity,
)
from .common import _canonical, _digest, _invalid, _sha


BUILD_INTENT_SCHEMA = "bilqis.akasha.projection-build-intent/v1"
PROJECTION_VERSION_SCHEMA = "bilqis.akasha.projection-version/v1"


@dataclass(frozen=True)
class ProjectionBuildIntent:
    domain: AkashaDomain
    projection_schema: str
    projection_version: int
    rebuild_source: str
    contract_sha256: str
    source_frontier_sha256: str
    expected_active_sha256: str | None
    build_sha256: str
    schema_version: str = field(default=BUILD_INTENT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        contract = DOMAIN_CONTRACTS.get(self.domain)
        if (contract is None
                or self.projection_schema != contract.projection_schema
                or type(self.projection_version) is not int
                or self.projection_version < 1
                or self.rebuild_source not in contract.rebuild_sources
                or self.contract_sha256 != contract.digest
                or not _sha(self.source_frontier_sha256)
                or (self.expected_active_sha256 is not None
                    and not _sha(self.expected_active_sha256))
                or self.schema_version != BUILD_INTENT_SCHEMA
                or self.build_sha256 != _digest(self._identity_payload())):
            _invalid("AKASHA_PROJECTION_BUILD_INTENT_INVALID")

    def _identity_payload(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "domain": self.domain.value,
            "projection_schema": self.projection_schema,
            "projection_version": self.projection_version,
            "rebuild_source": self.rebuild_source,
            "contract_sha256": self.contract_sha256,
            "source_frontier_sha256": self.source_frontier_sha256,
            "expected_active_sha256": self.expected_active_sha256,
        }

    @property
    def canonical_json(self) -> str:
        return _canonical({**self._identity_payload(), "build_sha256": self.build_sha256})

    @classmethod
    def create(cls, domain: AkashaDomain, *, projection_version: int,
               rebuild_source: str, source_records: tuple[dict, ...],
               expected_active_sha256: str | None) -> "ProjectionBuildIntent":
        contract = DOMAIN_CONTRACTS.get(domain)
        if contract is None or not isinstance(source_records, tuple):
            _invalid("AKASHA_PROJECTION_BUILD_ARGUMENT_INVALID")
        source = rebuild_projection_identity(domain, source_records)
        payload = {
            "schema_version": BUILD_INTENT_SCHEMA,
            "domain": domain.value,
            "projection_schema": contract.projection_schema,
            "projection_version": projection_version,
            "rebuild_source": rebuild_source,
            "contract_sha256": contract.digest,
            "source_frontier_sha256": source.source_frontier_sha256,
            "expected_active_sha256": expected_active_sha256,
        }
        return cls(
            domain, contract.projection_schema, projection_version,
            rebuild_source, contract.digest, source.source_frontier_sha256,
            expected_active_sha256, _digest(payload))

    @classmethod
    def from_canonical_json(cls, value: str) -> "ProjectionBuildIntent":
        try:
            raw = json.loads(value)
            schema_version = raw.pop("schema_version")
            item = cls(**{**raw, "domain": AkashaDomain(raw["domain"])})
            if schema_version != item.schema_version:
                _invalid("AKASHA_PROJECTION_BUILD_STORED_INVALID")
            return item
        except (TypeError, ValueError, KeyError):
            _invalid("AKASHA_PROJECTION_BUILD_STORED_INVALID")


@dataclass(frozen=True)
class ProjectionVersion:
    build_sha256: str
    domain: AkashaDomain
    projection_schema: str
    projection_version: int
    rebuild_source: str
    contract_sha256: str
    source_frontier_sha256: str
    payload_json: str
    payload_sha256: str
    version_sha256: str
    schema_version: str = field(default=PROJECTION_VERSION_SCHEMA, init=False)

    def __post_init__(self) -> None:
        contract = DOMAIN_CONTRACTS.get(self.domain)
        if (not _sha(self.build_sha256)
                or contract is None
                or self.projection_schema != contract.projection_schema
                or type(self.projection_version) is not int
                or self.projection_version < 1
                or self.rebuild_source not in contract.rebuild_sources
                or self.contract_sha256 != contract.digest
                or not _sha(self.source_frontier_sha256)
                or not isinstance(self.payload_json, str)
                or _digest(json.loads(self.payload_json)) != self.payload_sha256
                or self.schema_version != PROJECTION_VERSION_SCHEMA
                or self.version_sha256 != _digest(self._identity_payload())):
            _invalid("AKASHA_PROJECTION_VERSION_INVALID")

    def _identity_payload(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "build_sha256": self.build_sha256,
            "domain": self.domain.value,
            "projection_schema": self.projection_schema,
            "projection_version": self.projection_version,
            "rebuild_source": self.rebuild_source,
            "contract_sha256": self.contract_sha256,
            "source_frontier_sha256": self.source_frontier_sha256,
            "payload_sha256": self.payload_sha256,
        }

    @property
    def canonical_json(self) -> str:
        return _canonical({
            **self._identity_payload(),
            "payload_json": self.payload_json,
            "version_sha256": self.version_sha256,
        })

    @classmethod
    def from_payload(cls, intent: ProjectionBuildIntent, payload: object) -> "ProjectionVersion":
        payload_json = _canonical(payload)
        payload_sha256 = _digest(payload)
        identity = {
            "schema_version": PROJECTION_VERSION_SCHEMA,
            "build_sha256": intent.build_sha256,
            "domain": intent.domain.value,
            "projection_schema": intent.projection_schema,
            "projection_version": intent.projection_version,
            "rebuild_source": intent.rebuild_source,
            "contract_sha256": intent.contract_sha256,
            "source_frontier_sha256": intent.source_frontier_sha256,
            "payload_sha256": payload_sha256,
        }
        return cls(
            intent.build_sha256, intent.domain, intent.projection_schema,
            intent.projection_version, intent.rebuild_source,
            intent.contract_sha256, intent.source_frontier_sha256,
            payload_json, payload_sha256, _digest(identity))

    @classmethod
    def from_canonical_json(cls, value: str) -> "ProjectionVersion":
        try:
            raw = json.loads(value)
            schema_version = raw.pop("schema_version")
            item = cls(**{**raw, "domain": AkashaDomain(raw["domain"])})
            if schema_version != item.schema_version:
                _invalid("AKASHA_PROJECTION_STORED_CORRUPT")
            return item
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            _invalid("AKASHA_PROJECTION_STORED_CORRUPT")
