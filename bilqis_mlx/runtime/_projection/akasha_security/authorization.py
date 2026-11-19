"""Pure topology-neutral authorization for Akasha projection mutations."""
from __future__ import annotations

from .common import invalid, is_digest
from .contracts import (
    AkashaAuthorityTarget,
    AkashaNamespaceScope,
    AkashaWriteAuthorization,
    AkashaWriteRequest,
    DOMAIN_SECURITY_POLICIES,
)


def authorize_akasha_write(
    scope: AkashaNamespaceScope,
    request: AkashaWriteRequest,
    *, current_version_sha256: str | None,
) -> AkashaWriteAuthorization:
    """Authorize one derived-projection mutation without choosing its transport."""
    if (not isinstance(scope, AkashaNamespaceScope)
            or not isinstance(request, AkashaWriteRequest)
            or (current_version_sha256 is not None
                and not is_digest(current_version_sha256))):
        invalid("AKASHA_WRITE_AUTHORIZATION_ARGUMENT_INVALID")
    policy = DOMAIN_SECURITY_POLICIES[request.domain]
    if request.writer_role != policy.writer_role:
        invalid("AKASHA_WRITE_ROLE_FORBIDDEN")
    if (request.tenant_id != scope.tenant_id
            or request.project_id != scope.project_id
            or request.namespace != scope.namespace_for(request.domain)):
        invalid("AKASHA_WRITE_NAMESPACE_FORBIDDEN")
    if request.operation not in policy.allowed_operations:
        invalid("AKASHA_WRITE_OPERATION_FORBIDDEN")
    if (request.target is not policy.allowed_target
            or request.target in policy.forbidden_targets
            or request.target is not AkashaAuthorityTarget.DERIVED_PROJECTION):
        invalid("AKASHA_WRITE_CANONICAL_MUTATION_FORBIDDEN")
    if request.expected_version_sha256 != current_version_sha256:
        invalid("AKASHA_WRITE_EXPECTED_VERSION_STALE")
    return AkashaWriteAuthorization.create(
        request.domain, policy.policy_sha256,
        request.request_sha256, current_version_sha256)
