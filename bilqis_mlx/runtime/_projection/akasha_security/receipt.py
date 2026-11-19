"""Content-addressed Akasha write authorization receipt."""
from dataclasses import dataclass, field

from bilqis_mlx.runtime.akasha_domains import AkashaDomain
from .common import canonical, digest, invalid, is_digest
from .contracts import WRITE_AUTHORIZATION_SCHEMA, DOMAIN_SECURITY_POLICIES


@dataclass(frozen=True)
class AkashaWriteAuthorization:
    domain: AkashaDomain
    policy_sha256: str
    request_sha256: str
    current_version_sha256: str | None
    authorization_sha256: str
    schema_version: str = field(default=WRITE_AUTHORIZATION_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if (self.domain not in DOMAIN_SECURITY_POLICIES
                or self.policy_sha256
                    != DOMAIN_SECURITY_POLICIES[self.domain].policy_sha256
                or not is_digest(self.request_sha256)
                or (self.current_version_sha256 is not None
                    and not is_digest(self.current_version_sha256))
                or self.schema_version != WRITE_AUTHORIZATION_SCHEMA
                or self.authorization_sha256 != digest(self._identity_record())):
            invalid("AKASHA_WRITE_AUTHORIZATION_INVALID")

    def _identity_record(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "domain": self.domain.value,
            "policy_sha256": self.policy_sha256,
            "request_sha256": self.request_sha256,
            "current_version_sha256": self.current_version_sha256,
        }

    @property
    def canonical_json(self) -> str:
        return canonical({
            **self._identity_record(),
            "authorization_sha256": self.authorization_sha256,
        })

    @classmethod
    def create(cls, domain: AkashaDomain, policy_sha256: str,
               request_sha256: str, current_version_sha256: str | None):
        identity = {
            "schema_version": WRITE_AUTHORIZATION_SCHEMA,
            "domain": domain.value,
            "policy_sha256": policy_sha256,
            "request_sha256": request_sha256,
            "current_version_sha256": current_version_sha256,
        }
        return cls(
            domain, policy_sha256, request_sha256, current_version_sha256,
            digest(identity))
