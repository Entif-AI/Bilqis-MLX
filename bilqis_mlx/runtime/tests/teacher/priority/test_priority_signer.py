"""C06 host signer binds private authority to the already-accepted C09 public root."""
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import pytest

from bilqis_mlx.runtime.atlas_source_authority import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.bamf_bundle._darwin_salience_signer import (
    HostSourceAuthoritySigner,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef


def _registry(private_hex="44" * 32):
    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_hex))
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    scopes = tuple(sorted((SourceAuthorityScope(kind, prefix) for kind, prefix in (
        (DependencyKind.POLICY, "salience-policy:"),
        (DependencyKind.SOURCE, "salience-fact:"),
        (DependencyKind.ARTIFACT, "salience-option:"),
        (DependencyKind.ARTIFACT, "salience-event:"),
    )), key=lambda scope: (scope.kind.value, scope.key_prefix)))
    return SourceAuthorityRegistry((SourceAuthorityKey("owner:c06", public, scopes),))


def test_host_signer_must_match_registered_owner_key_and_scope():
    registry = _registry()
    signer = HostSourceAuthoritySigner("owner:c06", "44" * 32, registry)
    dependency = DependencyRef(DependencyKind.POLICY, "salience-policy:foundation")
    payload = b"signed-c06-record"
    signature = signer.sign(dependency, payload)
    registry.verify_detached(signer.owner_id, dependency, signature, payload)

    with pytest.raises(ValueError):
        signer.sign(DependencyRef(DependencyKind.POLICY, "other-policy:foundation"), payload)
    with pytest.raises(ValueError):
        HostSourceAuthoritySigner("owner:c06", "55" * 32, registry).sign(
            dependency, payload)
