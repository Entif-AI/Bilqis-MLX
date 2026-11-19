"""Trusted authentication and authority-evidence inputs for Akasha policy."""
from dataclasses import dataclass, field

from bilqis_mlx.runtime.akasha_domains import AkashaDomain, DOMAIN_CONTRACTS
from .common import invalid, is_digest, is_name
from .contracts import WRITER_IDENTITY_CLASS


@dataclass(frozen=True)
class AuthenticatedAkashaPrincipal:
    principal_id: str
    role: str
    identity_class: str = field(default=WRITER_IDENTITY_CLASS, init=False)

    def __post_init__(self) -> None:
        if (not is_name(self.principal_id)
                or not is_name(self.role)
                or self.identity_class != WRITER_IDENTITY_CLASS):
            invalid("AKASHA_AUTHENTICATED_PRINCIPAL_INVALID")


@dataclass(frozen=True)
class VerifiedAuthorityEvidence:
    domain: AkashaDomain
    authority_owner: str
    receipt_sha256: str

    def __post_init__(self) -> None:
        contract = DOMAIN_CONTRACTS.get(self.domain)
        if (contract is None
                or self.authority_owner != contract.authority_owner
                or not is_digest(self.receipt_sha256)):
            invalid("AKASHA_AUTHORITY_EVIDENCE_INVALID")
