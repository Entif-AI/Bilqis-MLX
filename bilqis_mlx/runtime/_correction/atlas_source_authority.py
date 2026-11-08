"""Host-provisioned source authority keys and scoped signature checks."""
from __future__ import annotations

from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ..semantics.cognitive_dependencies import DependencyKind, DependencyRef
from .atlas_revalidation_common import (
    SOURCE_AUTHORITY_KEY_SCHEMA,
    SOURCE_AUTHORITY_REGISTRY_SCHEMA,
    SOURCE_AUTHORITY_SCOPE_SCHEMA,
    _ED25519_SIGNATURE,
    _SHA256,
    _invalid,
    _name,
)
from .atlas_revalidation_evidence import (
    CorrectionEvent,
    RevalidatedArtifact,
    StateTransition,
)


@dataclass(frozen=True)
class SourceAuthorityScope:
    kind: DependencyKind
    key_prefix: str
    schema_version: str = SOURCE_AUTHORITY_SCOPE_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.kind, DependencyKind)
                or not _name(self.key_prefix)
                or self.schema_version != SOURCE_AUTHORITY_SCOPE_SCHEMA):
            _invalid("BAMF_C09_SOURCE_AUTHORITY_SCOPE_INVALID")


@dataclass(frozen=True)
class SourceAuthorityKey:
    owner_id: str
    public_key_hex: str
    allowed_scopes: tuple[SourceAuthorityScope, ...]
    schema_version: str = SOURCE_AUTHORITY_KEY_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.owner_id)
                or not isinstance(self.public_key_hex, str)
                or not _SHA256.fullmatch(self.public_key_hex)
                or not isinstance(self.allowed_scopes, tuple)
                or not self.allowed_scopes
                or any(not isinstance(scope, SourceAuthorityScope)
                       for scope in self.allowed_scopes)
                or self.allowed_scopes != tuple(sorted(
                    set(self.allowed_scopes),
                    key=lambda scope: (scope.kind.value, scope.key_prefix)))
                or self.schema_version != SOURCE_AUTHORITY_KEY_SCHEMA):
            _invalid("BAMF_C09_SOURCE_AUTHORITY_KEY_INVALID")


@dataclass(frozen=True)
class SourceAuthorityRegistry:
    """Trusted host-provisioned public keys; never inferred from event data."""
    keys: tuple[SourceAuthorityKey, ...]
    schema_version: str = SOURCE_AUTHORITY_REGISTRY_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.keys, tuple) or not self.keys
                or any(not isinstance(key, SourceAuthorityKey)
                       for key in self.keys)
                or self.keys != tuple(sorted(
                    self.keys, key=lambda key: key.owner_id))
                or len({key.owner_id for key in self.keys}) != len(self.keys)
                or self.schema_version != SOURCE_AUTHORITY_REGISTRY_SCHEMA):
            _invalid("BAMF_C09_SOURCE_AUTHORITY_REGISTRY_INVALID")

    def _require(
        self, owner_id: str, dependency_kind: DependencyKind,
        dependency_key: str,
        claimed_public_key_hex: str | None = None,
    ) -> SourceAuthorityKey:
        authority = next(
            (key for key in self.keys if key.owner_id == owner_id), None)
        if authority is None:
            _invalid("BAMF_C09_SOURCE_AUTHORITY_UNREGISTERED")
        if (claimed_public_key_hex is not None
                and claimed_public_key_hex != authority.public_key_hex):
            _invalid("BAMF_C09_SOURCE_AUTHORITY_KEY_MISMATCH")
        if not any(
            scope.kind is dependency_kind
            and dependency_key.startswith(scope.key_prefix)
            for scope in authority.allowed_scopes
        ):
            _invalid("BAMF_C09_SOURCE_AUTHORITY_SCOPE_MISMATCH")
        return authority

    def _verify(
        self, owner_id: str, dependency_kind: DependencyKind,
        dependency_key: str, signature_hex: str, payload: bytes,
        claimed_public_key_hex: str | None = None,
    ) -> None:
        authority = self._require(
            owner_id, dependency_kind, dependency_key, claimed_public_key_hex)
        try:
            Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(authority.public_key_hex)
            ).verify(bytes.fromhex(signature_hex), payload)
        except (InvalidSignature, ValueError):
            _invalid("BAMF_C09_SOURCE_SIGNATURE_INVALID")

    def require_claimed_authority(
        self, owner_id: str, dependency: DependencyRef,
        claimed_public_key_hex: str,
    ) -> None:
        """Require one claimed owner/key/scope to match this host registry."""
        if (not _name(owner_id) or not isinstance(dependency, DependencyRef)
                or not isinstance(claimed_public_key_hex, str)
                or not _SHA256.fullmatch(claimed_public_key_hex)):
            _invalid("BAMF_SOURCE_AUTHORITY_INPUT_INVALID")
        self._require(
            owner_id, dependency.kind, dependency.key, claimed_public_key_hex)

    def verify_detached(self, owner_id: str, dependency: DependencyRef,
                        signature_hex: str, payload: bytes,
                        claimed_public_key_hex: str | None = None) -> None:
        """Verify another domain's signed payload under the same scoped key registry."""
        if (not _name(owner_id) or not isinstance(dependency, DependencyRef)
                or not isinstance(signature_hex, str)
                or not _ED25519_SIGNATURE.fullmatch(signature_hex)
                or not isinstance(payload, bytes)
                or (claimed_public_key_hex is not None
                    and not _SHA256.fullmatch(claimed_public_key_hex))):
            _invalid("BAMF_SOURCE_DETACHED_SIGNATURE_INPUT_INVALID")
        self._verify(
            owner_id, dependency.kind, dependency.key, signature_hex, payload,
            claimed_public_key_hex,
        )

    def verify_correction(self, event: CorrectionEvent) -> None:
        if not isinstance(event, CorrectionEvent):
            _invalid("BAMF_C09_SOURCE_AUTHORITY_MISSING")
        self._verify(
            event.source_owner, event.dependency.kind,
            event.dependency.key,
            event.source_signature_hex, event.signing_bytes())

    def verify_revalidation(self, result: RevalidatedArtifact) -> None:
        if not isinstance(result, RevalidatedArtifact):
            _invalid("BAMF_C09_SOURCE_AUTHORITY_MISSING")
        self._verify(
            result.source_owner, DependencyKind.ARTIFACT,
            result.artifact_id,
            result.source_signature_hex, result.signing_bytes())

    def verify_transition(self, transition: StateTransition) -> None:
        if not isinstance(transition, StateTransition):
            _invalid("BAMF_C09_SOURCE_AUTHORITY_MISSING")
        self._verify(
            transition.source_owner, DependencyKind.ARTIFACT,
            transition.artifact_id,
            transition.source_signature_hex,
            transition.revalidated_signing_bytes())


def _new_authority_owner():
    """Create one process-local owner for opaque C09 source authority."""
    issued = {}

    def require(authority):
        entry = issued.get(id(authority))
        if entry is None or entry[0] is not authority:
            _invalid("BAMF_C09_SOURCE_AUTHORITY_RUNTIME_INVALID")
        return entry[1]

    def issue(registry):
        if type(registry) is not SourceAuthorityRegistry:
            _invalid("BAMF_C09_SOURCE_AUTHORITY_RUNTIME_INVALID")
        authority = object.__new__(SourceAuthorityRuntime)
        issued[id(authority)] = (authority, registry)
        return authority

    return require, issue


class _AcceptedSourceAuthorityIssuer:
    """Issuer reachable only through authenticated accepted-run custody."""

    def __init__(self, issue):
        self._issue = issue
        self._accepted = {}

    def issue(self, accepted_cache, registry):
        from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
            require_accepted_execution_cache,
        )

        cache = require_accepted_execution_cache(accepted_cache)
        if type(registry) is not SourceAuthorityRegistry:
            _invalid("BAMF_C09_SOURCE_AUTHORITY_RUNTIME_INVALID")
        retained = self._accepted.get(id(cache))
        if retained is not None:
            if retained[0] is not cache or retained[1] != registry:
                _invalid("BAMF_C09_SOURCE_AUTHORITY_RUNTIME_INVALID")
            return retained[2]
        authority = self._issue(registry)
        self._accepted[id(cache)] = (cache, registry, authority)
        return authority


_authority_state, _raw_authority_issue = _new_authority_owner()
_ACCEPTED_SOURCE_AUTHORITY_ISSUER = _AcceptedSourceAuthorityIssuer(
    _raw_authority_issue)
del _raw_authority_issue


class SourceAuthorityRuntime:
    """Opaque C09 capability bound by accepted-run custody to one registry."""

    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        _invalid("BAMF_C09_SOURCE_AUTHORITY_RUNTIME_INVALID")

    def _validate_export_clearance_context(
            self, receipt, selection, source_frontier, artifact_digests):
        from bilqis_mlx.semantics.atlas_release_audit import (
            validate_export_clearance_context,
        )
        return validate_export_clearance_context(
            receipt, selection, source_frontier, artifact_digests,
            _authority_state(self))


def require_source_authority_runtime(authority) -> SourceAuthorityRuntime:
    if type(authority) is not SourceAuthorityRuntime:
        _invalid("BAMF_C09_SOURCE_AUTHORITY_RUNTIME_INVALID")
    _authority_state(authority)
    return authority
