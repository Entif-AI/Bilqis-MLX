"""C06 host signer binds private authority to the already-accepted C09 public root."""
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from types import SimpleNamespace
from unittest.mock import patch
import pytest

from bilqis_mlx.runtime.atlas_source_authority import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.bamf_bundle._darwin_salience_signer import (
    HostSourceAuthoritySigner,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef
from bilqis_mlx.learning.atlas_salience import DispatchTier, rank_attention_options
from bilqis_mlx.learning.salience_contracts import Ordinal


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


def test_foundation_priority_issuer_emits_unknown_evidence_and_c06_rotation_only():
    from bilqis_mlx.runtime import priority_authority as authority

    registry = _registry()
    signer = HostSourceAuthoritySigner("owner:c06", "44" * 32, registry)
    release = SimpleNamespace(
        release_sha256="a" * 64,
        execution_plan=SimpleNamespace(capabilities=(
            SimpleNamespace(id="capability:alpha"),
            SimpleNamespace(id="capability:beta"),
        )),
    )
    source_context = SimpleNamespace(release=release)
    parent = SimpleNamespace(
        teacher_state={"next_seed": 7},
        compiler_features={"rights_epoch": 0, "correction_generation": 0},
    )

    def offer(_context, _parent, _path, *, capability, source_seed, source_each):
        return SimpleNamespace(
            capability_id=capability,
            source_seed=source_seed,
            source_each=source_each,
            source_family_id="family:" + capability,
            source_binding_digest=("b" if capability.endswith("alpha") else "c") * 64,
            release_sha256=release.release_sha256,
            generation_binding="d" * 64,
            source_authority=SimpleNamespace(content_sha256="e" * 64),
        )

    with patch(
        "bilqis_mlx.runtime.bamf_bundle.accepted_runtime._accepted_correction_registry",
        return_value=(object(), registry),
    ), patch(
        "bilqis_mlx.runtime.bamf_bundle._darwin_salience_signer.read_host_system_source_authority_signer",
        return_value=signer,
    ), patch.object(authority, "prepare_priority_source_offer", side_effect=offer), patch.object(
        authority, "priority_rotation_state",
        return_value=(1, {"capability:alpha": 1}),
    ):
        issued = authority.issue_foundation_priority_authority(
            "/run", source_context, parent, {"epoch": 1}, "/atlas")

    evidence = dict(issued.frontier.evidence)
    assert issued.now == 1
    assert {item.impact.ordinal for item in evidence.values()} == {Ordinal.UNKNOWN}
    assert {item.exigency.ordinal for item in evidence.values()} == {Ordinal.UNKNOWN}
    assert {item.novelty.ordinal for item in evidence.values()} == {Ordinal.UNKNOWN}
    ranked = rank_attention_options(
        issued.frontier.options, evidence, issued.frontier.snapshot)
    assert tuple(item.stable_id for item in ranked.ordered) == (
        "capability:beta", "capability:alpha")
    assert {tier for _, tier in ranked.tiers} == {DispatchTier.FAIR_ROTATION}
    assert {offer.source_each for _, offer in issued.offers} == {1}
    assert len({offer.source_seed for _, offer in issued.offers}) == 2
