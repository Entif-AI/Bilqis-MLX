"""Machine-readable Akasha domain security and mutation contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType

from bilqis_mlx.runtime.akasha_domains import AkashaDomain, DOMAIN_CONTRACTS
from .common import canonical, digest, invalid, is_digest, is_name


SECURITY_POLICY_SCHEMA = "bilqis.akasha.domain-security-policy/v1"
WRITE_REQUEST_SCHEMA = "bilqis.akasha.write-request/v1"
WRITE_AUTHORIZATION_SCHEMA = "bilqis.akasha.write-authorization/v1"
VERSION_PRECONDITION = "exact-current-or-empty"
WRITER_IDENTITY_CLASS = "authenticated-principal-id"
NAMESPACE_RULE = "tenant/project/domain"


class AkashaAuthorityTarget(str, Enum):
    DERIVED_PROJECTION = "DERIVED_PROJECTION"
    CANONICAL_SEMANTIC_SOURCE = "CANONICAL_SEMANTIC_SOURCE"
    HISTORICAL_EVIDENCE_SOURCE = "HISTORICAL_EVIDENCE_SOURCE"


@dataclass(frozen=True)
class DomainSecurityPolicy:
    domain: AkashaDomain
    authority_owner: str
    writer_identity_class: str
    writer_role: str
    read_scopes: tuple[str, ...]
    allowed_operations: tuple[str, ...]
    allowed_target: AkashaAuthorityTarget
    forbidden_targets: tuple[AkashaAuthorityTarget, ...]
    namespace_rule: str
    version_precondition: str
    audit_obligations: tuple[str, ...]
    schema_version: str = field(default=SECURITY_POLICY_SCHEMA, init=False)

    def __post_init__(self) -> None:
        contract = DOMAIN_CONTRACTS.get(self.domain)
        if (contract is None
                or self.authority_owner != contract.authority_owner
                or self.writer_identity_class != WRITER_IDENTITY_CLASS
                or not is_name(self.writer_role)
                or not self.read_scopes
                or len(self.read_scopes) != len(set(self.read_scopes))
                or self.allowed_operations != contract.allowed_operations
                or self.allowed_target is not AkashaAuthorityTarget.DERIVED_PROJECTION
                or set(self.forbidden_targets) != {
                    AkashaAuthorityTarget.CANONICAL_SEMANTIC_SOURCE,
                    AkashaAuthorityTarget.HISTORICAL_EVIDENCE_SOURCE,
                }
                or self.namespace_rule != NAMESPACE_RULE
                or self.version_precondition != VERSION_PRECONDITION
                or not self.audit_obligations
                or len(self.audit_obligations) != len(set(self.audit_obligations))
                or self.schema_version != SECURITY_POLICY_SCHEMA):
            invalid("AKASHA_SECURITY_POLICY_INVALID")

    def to_record(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "domain": self.domain.value,
            "authority_owner": self.authority_owner,
            "writer_identity_class": self.writer_identity_class,
            "writer_role": self.writer_role,
            "read_scopes": self.read_scopes,
            "allowed_operations": self.allowed_operations,
            "allowed_target": self.allowed_target.value,
            "forbidden_targets": tuple(item.value for item in self.forbidden_targets),
            "namespace_rule": self.namespace_rule,
            "version_precondition": self.version_precondition,
            "audit_obligations": self.audit_obligations,
        }

    @property
    def policy_sha256(self) -> str:
        return digest(self.to_record())


def _policy(domain: AkashaDomain, role: str, read_scopes: tuple[str, ...]):
    contract = DOMAIN_CONTRACTS[domain]
    return DomainSecurityPolicy(
        domain=domain,
        authority_owner=contract.authority_owner,
        writer_identity_class=WRITER_IDENTITY_CLASS,
        writer_role=role,
        read_scopes=read_scopes,
        allowed_operations=contract.allowed_operations,
        allowed_target=AkashaAuthorityTarget.DERIVED_PROJECTION,
        forbidden_targets=(
            AkashaAuthorityTarget.CANONICAL_SEMANTIC_SOURCE,
            AkashaAuthorityTarget.HISTORICAL_EVIDENCE_SOURCE,
        ),
        namespace_rule=NAMESPACE_RULE,
        version_precondition=VERSION_PRECONDITION,
        audit_obligations=(
            "authority-evidence-receipt",
            "exact-precondition-receipt",
            "append-only-mutation-receipt",
        ),
    )


_POLICIES = (
    _policy(AkashaDomain.SEMANTIC_GRAPH, "semantic-projection-writer", (
        "semantic-release:read", "materialization-receipt:read", "projection:read")),
    _policy(AkashaDomain.LEARNER_EVIDENCE, "learner-evidence-projection-writer", (
        "accepted-generation:read", "learning-evidence:read", "projection:read")),
    _policy(AkashaDomain.FACTORY_RELEASE_LEDGER, "factory-release-projection-writer", (
        "factory-release:read", "admission-receipt:read", "projection:read")),
    _policy(AkashaDomain.RUN_HISTORY, "run-history-projection-writer", (
        "run-manifest:read", "checkpoint:read", "projection:read")),
    _policy(AkashaDomain.RECEIPT_PROVENANCE, "receipt-index-writer", (
        "immutable-receipt:read", "accepted-event:read", "projection:read")),
    _policy(AkashaDomain.PROGRAM_OPERATIONS, "program-operations-projection-writer", (
        "program-policy:read", "gate-receipt:read", "projection:read")),
)

DOMAIN_SECURITY_POLICIES = MappingProxyType(
    {policy.domain: policy for policy in _POLICIES})


@dataclass(frozen=True)
class AkashaNamespaceScope:
    tenant_id: str
    project_id: str

    def __post_init__(self) -> None:
        if not is_name(self.tenant_id) or not is_name(self.project_id):
            invalid("AKASHA_SECURITY_SCOPE_INVALID")

    def namespace_for(self, domain: AkashaDomain) -> str:
        if domain not in DOMAIN_SECURITY_POLICIES:
            invalid("AKASHA_SECURITY_DOMAIN_UNKNOWN")
        return f"{self.tenant_id}/{self.project_id}/{domain.value}"


@dataclass(frozen=True)
class AkashaWriteRequest:
    domain: AkashaDomain
    writer_id: str
    writer_role: str
    tenant_id: str
    project_id: str
    namespace: str
    operation: str
    target: AkashaAuthorityTarget
    expected_version_sha256: str | None
    authority_receipt_sha256: str
    schema_version: str = field(default=WRITE_REQUEST_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if self.target is not AkashaAuthorityTarget.DERIVED_PROJECTION:
            invalid("AKASHA_WRITE_CANONICAL_MUTATION_FORBIDDEN")
        if (self.domain not in DOMAIN_SECURITY_POLICIES
                or not is_name(self.writer_id)
                or not is_name(self.writer_role)
                or not is_name(self.tenant_id)
                or not is_name(self.project_id)
                or not isinstance(self.namespace, str) or not self.namespace
                or not isinstance(self.operation, str) or not self.operation
                or not isinstance(self.target, AkashaAuthorityTarget)
                or (self.expected_version_sha256 is not None
                    and not is_digest(self.expected_version_sha256))
                or not is_digest(self.authority_receipt_sha256)
                or self.schema_version != WRITE_REQUEST_SCHEMA):
            invalid("AKASHA_WRITE_REQUEST_INVALID")

    def to_record(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "domain": self.domain.value,
            "writer_id": self.writer_id,
            "writer_role": self.writer_role,
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
            "namespace": self.namespace,
            "operation": self.operation,
            "target": self.target.value,
            "expected_version_sha256": self.expected_version_sha256,
            "authority_receipt_sha256": self.authority_receipt_sha256,
        }

    @property
    def request_sha256(self) -> str:
        return digest(self.to_record())
