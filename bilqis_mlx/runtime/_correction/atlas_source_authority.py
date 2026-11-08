"""Host-provisioned source authority keys and scoped signature checks."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ..semantics.cognitive_dependencies import DependencyKind, DependencyRef
from ..semantics.foundation.domains import contract_digest
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

    @property
    def digest(self) -> str:
        return contract_digest(self)

    def to_record(self) -> dict:
        return {
            "keys": [
                {
                    "allowed_scopes": [
                        {
                            "key_prefix": scope.key_prefix,
                            "kind": scope.kind.value,
                            "schema_version": scope.schema_version,
                        }
                        for scope in key.allowed_scopes
                    ],
                    "owner_id": key.owner_id,
                    "public_key_hex": key.public_key_hex,
                    "schema_version": key.schema_version,
                }
                for key in self.keys
            ],
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_record(cls, record) -> "SourceAuthorityRegistry":
        if (not isinstance(record, Mapping)
                or set(record) != {"keys", "schema_version"}
                or record.get("schema_version") != SOURCE_AUTHORITY_REGISTRY_SCHEMA
                or not isinstance(record.get("keys"), (tuple, list))
                or not record["keys"]):
            _invalid("BAMF_C09_SOURCE_AUTHORITY_REGISTRY_INVALID")
        keys = []
        for item in record["keys"]:
            if (not isinstance(item, Mapping)
                    or set(item) != {
                        "allowed_scopes", "owner_id", "public_key_hex",
                        "schema_version",
                    }
                    or not isinstance(item.get("allowed_scopes"), (tuple, list))):
                _invalid("BAMF_C09_SOURCE_AUTHORITY_REGISTRY_INVALID")
            scopes = []
            for scope in item["allowed_scopes"]:
                if (not isinstance(scope, Mapping)
                        or set(scope) != {"key_prefix", "kind", "schema_version"}):
                    _invalid("BAMF_C09_SOURCE_AUTHORITY_REGISTRY_INVALID")
                try:
                    kind = DependencyKind(scope["kind"])
                except (TypeError, ValueError):
                    _invalid("BAMF_C09_SOURCE_AUTHORITY_REGISTRY_INVALID")
                scopes.append(SourceAuthorityScope(
                    kind, scope["key_prefix"], scope["schema_version"]))
            keys.append(SourceAuthorityKey(
                item["owner_id"], item["public_key_hex"], tuple(scopes),
                item["schema_version"]))
        registry = cls(tuple(keys), record["schema_version"])
        if registry.to_record() != dict(record):
            _invalid("BAMF_C09_SOURCE_AUTHORITY_REGISTRY_INVALID")
        return registry

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
    """Create one process-local owner for opaque accepted-cache authority."""
    issued = {}

    def require(authority, accepted_cache):
        from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
            require_accepted_execution_cache,
        )

        cache = require_accepted_execution_cache(accepted_cache)
        entry = issued.get(id(authority))
        if (entry is None or entry[0] is not authority
                or entry[1] is not cache):
            _invalid("BAMF_C09_SOURCE_AUTHORITY_RUNTIME_INVALID")
        registry = entry[2]
        if (cache._source_authority is not authority
                or cache._correction_registry is not registry
                or cache.source_authority_registry_sha256 is None
                or cache.source_authority_registry_sha256 != registry.digest):
            _invalid("BAMF_C09_SOURCE_AUTHORITY_RUNTIME_INVALID")
        return registry

    def issue(accepted_cache):
        from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
            require_accepted_execution_cache,
        )

        cache = require_accepted_execution_cache(accepted_cache)
        registry = cache._correction_registry
        if (type(registry) is not SourceAuthorityRegistry
                or cache.source_authority_registry_sha256 is None
                or cache.source_authority_registry_sha256 != registry.digest):
            _invalid("BAMF_C09_SOURCE_AUTHORITY_RUNTIME_INVALID")
        authority = object.__new__(SourceAuthorityRuntime)
        issued[id(authority)] = (authority, cache, registry)
        return authority

    return require, issue


def _make_source_authority_provisioner(issue):
    def provision(accepted_cache):
        from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
            require_accepted_execution_cache,
        )
        from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
            _EXECUTION_CACHE_OWNER,
        )

        with _EXECUTION_CACHE_OWNER.lock:
            cache = require_accepted_execution_cache(accepted_cache)
            authority = cache._source_authority
            if authority is None:
                authority = issue(cache)
                object.__setattr__(cache, "_source_authority", authority)
            require_source_authority_runtime(authority, cache)
            return authority

    return provision


_authority_state, _raw_authority_issue = _new_authority_owner()
_provision_source_authority_runtime = _make_source_authority_provisioner(
    _raw_authority_issue)
del _raw_authority_issue


class SourceAuthorityRuntime:
    """Opaque C09 capability bound by accepted-run custody to one registry."""

    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        _invalid("BAMF_C09_SOURCE_AUTHORITY_RUNTIME_INVALID")

    def _validate_export_clearance_context(
            self, accepted_cache, receipt, selection, source_frontier,
            artifact_digests):
        from bilqis_mlx.semantics.atlas_release_audit import (
            validate_export_clearance_context,
        )
        return validate_export_clearance_context(
            receipt, selection, source_frontier, artifact_digests,
            _authority_state(self, accepted_cache))


def require_source_authority_runtime(
        authority, accepted_cache) -> SourceAuthorityRuntime:
    if type(authority) is not SourceAuthorityRuntime:
        _invalid("BAMF_C09_SOURCE_AUTHORITY_RUNTIME_INVALID")
    _authority_state(authority, accepted_cache)
    return authority
