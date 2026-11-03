"""Scoped source-authority verification for C09 correction evidence."""
from __future__ import annotations
from dataclasses import dataclass
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from ..semantics.cognitive_dependencies import DependencyKind, DependencyRef
from ._revalidation_base import (
    SOURCE_AUTHORITY_KEY_SCHEMA, SOURCE_AUTHORITY_REGISTRY_SCHEMA,
    SOURCE_AUTHORITY_SCOPE_SCHEMA, _ED25519_SIGNATURE, _SHA256,
    _invalid, _name,
)
from ._revalidation_events import CorrectionEvent, RevalidatedArtifact
from ._revalidation_queue import StateTransition

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

    def _verify(
        self, owner_id: str, dependency_kind: DependencyKind,
        dependency_key: str, signature_hex: str, payload: bytes,
    ) -> None:
        authority = next(
            (key for key in self.keys if key.owner_id == owner_id), None)
        if authority is None:
            _invalid("BAMF_C09_SOURCE_AUTHORITY_UNREGISTERED")
        if not any(
            scope.kind is dependency_kind
            and dependency_key.startswith(scope.key_prefix)
            for scope in authority.allowed_scopes
        ):
            _invalid("BAMF_C09_SOURCE_AUTHORITY_SCOPE_MISMATCH")
        try:
            Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(authority.public_key_hex)
            ).verify(bytes.fromhex(signature_hex), payload)
        except (InvalidSignature, ValueError):
            _invalid("BAMF_C09_SOURCE_SIGNATURE_INVALID")

    def verify_detached(self, owner_id: str, dependency: DependencyRef,
                        signature_hex: str, payload: bytes) -> None:
        """Verify another domain's signed payload under the same scoped key registry."""
        if (not _name(owner_id) or not isinstance(dependency, DependencyRef)
                or not isinstance(signature_hex, str)
                or not _ED25519_SIGNATURE.fullmatch(signature_hex)
                or not isinstance(payload, bytes)):
            _invalid("BAMF_SOURCE_DETACHED_SIGNATURE_INPUT_INVALID")
        self._verify(owner_id, dependency.kind, dependency.key, signature_hex, payload)

    def verify_correction(self, event: "CorrectionEvent") -> None:
        if not isinstance(event, CorrectionEvent):
            _invalid("BAMF_C09_SOURCE_AUTHORITY_MISSING")
        self._verify(
            event.source_owner, event.dependency.kind,
            event.dependency.key,
            event.source_signature_hex, event.signing_bytes())

    def verify_revalidation(self, result: "RevalidatedArtifact") -> None:
        if not isinstance(result, RevalidatedArtifact):
            _invalid("BAMF_C09_SOURCE_AUTHORITY_MISSING")
        self._verify(
            result.source_owner, DependencyKind.ARTIFACT,
            result.artifact_id,
            result.source_signature_hex, result.signing_bytes())

    def verify_transition(self, transition: "StateTransition") -> None:
        if not isinstance(transition, StateTransition):
            _invalid("BAMF_C09_SOURCE_AUTHORITY_MISSING")
        self._verify(
            transition.source_owner, DependencyKind.ARTIFACT,
            transition.artifact_id,
            transition.source_signature_hex,
            transition.revalidated_signing_bytes())
