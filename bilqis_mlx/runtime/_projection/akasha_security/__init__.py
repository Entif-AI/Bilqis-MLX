"""Topology-neutral Akasha security and mutation policy."""

from .authorization import authorize_akasha_write
from .contracts import (
    AkashaAuthorityTarget,
    AkashaNamespaceScope,
    AkashaWriteAuthorization,
    AkashaWriteRequest,
    DomainSecurityPolicy,
    DOMAIN_SECURITY_POLICIES,
)

__all__ = (
    "AkashaAuthorityTarget",
    "AkashaNamespaceScope",
    "AkashaWriteAuthorization",
    "AkashaWriteRequest",
    "DomainSecurityPolicy",
    "DOMAIN_SECURITY_POLICIES",
    "authorize_akasha_write",
)
