"""Shared fixtures extracted structurally from test_atlas_revalidation.py."""
from __future__ import annotations
from dataclasses import replace
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyIndex, DependencyKind,
    DependencyRef,
)
from bilqis_mlx.runtime.atlas_revalidation import (
    CorrectionEvent, RevalidatedArtifact, RevalidationFrontier,
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
    advance_revalidation as _advance_revalidation,
    apply_correction as _apply_correction,
    next_revalidation_task, read_artifact,
    revalidate_node as _revalidate_node,
)
from bilqis_mlx.runtime.atlas_requalification import (
    CapabilitySupport, CorrectionBranches, RequalificationLedger,
    RequalificationStatus, add_correction as _add_correction,
    mark_affected_capabilities,
)
from bilqis_mlx.runtime.atlas_temporal_revalidation import (
    DerivedClaim, RemediationReceipt, RemediationStatus, TemporalEvent,
    TemporalEventKind, TemporalStatus, bind_as_of_dependency,
    escalate_stale_replay as _escalate_stale_replay, project_as_of,
)

_TEST_PRIVATE = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("11" * 32))

_TEST_PUBLIC = _TEST_PRIVATE.public_key().public_bytes(
    Encoding.Raw, PublicFormat.Raw).hex()

_SOURCE_OWNER = "synthetic:source-authority"

_TEST_PREFIXES = (
    "source:", "rights:", "fixture:", "time:asof:",
    "feature:", "frame:", "motif:", "cache:",
    "composition:", "capability:", "artifact:",
    "a", "b", "c", "d", "feature", "frame",
)

AUTHORITY = SourceAuthorityRegistry((
    SourceAuthorityKey(
        _SOURCE_OWNER, _TEST_PUBLIC,
        tuple(sorted((
            SourceAuthorityScope(kind, prefix)
            for kind in DependencyKind for prefix in _TEST_PREFIXES
        ), key=lambda scope: (scope.kind.value, scope.key_prefix)))),
))

def _sign_event(event: CorrectionEvent) -> CorrectionEvent:
    return replace(
        event, source_signature_hex=_TEST_PRIVATE.sign(
            event.signing_bytes()).hex())

def _sign_result(result: RevalidatedArtifact) -> RevalidatedArtifact:
    return replace(
        result, source_signature_hex=_TEST_PRIVATE.sign(
            result.signing_bytes()).hex())

def apply_correction(event, index):
    return _apply_correction(event, index, AUTHORITY)

def revalidate_node(node, frontier):
    return _revalidate_node(node, frontier, AUTHORITY)

def advance_revalidation(index, queue, transition):
    return _advance_revalidation(index, queue, transition, AUTHORITY)

def add_correction(branches, event, *, supersedes_event_ids=()):
    return _add_correction(
        branches, event, authority_registry=AUTHORITY,
        supersedes_event_ids=supersedes_event_ids)

def escalate_stale_replay(remediation, claim, correction, index, ledger):
    return _escalate_stale_replay(
        remediation, claim, correction, index, ledger, AUTHORITY)

def _ref(kind: DependencyKind, key: str) -> DependencyRef:
    return DependencyRef(kind, key)

def _node(
    key: str, kind: ArtifactKind, deps: tuple[DependencyRef, ...],
    *, impact: int = 1, exigency: int = 1,
) -> ArtifactNode:
    return ArtifactNode(
        artifact_id=key, kind=kind, content_digest="a" * 64,
        eligible=True, immediate_dependencies=deps,
        impact=impact, exigency=exigency,
    )

def _event(dependency: DependencyRef) -> CorrectionEvent:
    return _sign_event(CorrectionEvent(
        event_id="correction:synthetic:1",
        dependency=dependency,
        source_owner=_SOURCE_OWNER,
        source_receipt_sha256="f" * 64,
        old_evidence_sha256="a" * 64,
        new_evidence_sha256="b" * 64,
        source_time=570, effective_time=620, observed_at=625,
        recorded_at=630, reason_code="SOURCE_CORRECTION",
        source_signature_hex="0" * 128,
    ))

def _result(node: ArtifactNode, *, digest: str = "a" * 64,
            eligible: bool = True,
            correction: CorrectionEvent | None = None) -> RevalidationFrontier:
    correction = correction or _event(
        _ref(DependencyKind.SOURCE, "source:alpha"))
    return RevalidationFrontier((
        _sign_result(RevalidatedArtifact(
            artifact_id=node.artifact_id,
            immediate_dependencies=node.immediate_dependencies,
            content_digest=digest, eligible=eligible,
            source_receipt_sha256="c" * 64,
            correction_event_id=correction.event_id,
            correction_receipt_sha256=correction.source_receipt_sha256,
            source_owner=_SOURCE_OWNER,
            source_signature_hex="0" * 128,
        )),
    ))

def _chain() -> tuple[DependencyIndex, DependencyRef, DependencyRef]:
    source_a = _ref(DependencyKind.SOURCE, "source:alpha")
    source_b = _ref(DependencyKind.SOURCE, "source:beta")
    feature = _node("feature:alpha", ArtifactKind.ATLAS_FEATURE, (source_a,))
    frame = _node("frame:alpha", ArtifactKind.PACKED_FRAME, (
        _ref(DependencyKind.ARTIFACT, feature.artifact_id),))
    motif = _node("motif:alpha", ArtifactKind.MOTIF, (
        _ref(DependencyKind.ARTIFACT, frame.artifact_id),))
    cache = _node("cache:alpha", ArtifactKind.EXACT_CACHE, (
        _ref(DependencyKind.ARTIFACT, motif.artifact_id),))
    composition = _node("composition:alpha", ArtifactKind.OPERATOR_COMPOSITION, (
        _ref(DependencyKind.ARTIFACT, cache.artifact_id),))
    capability = _node("capability:alpha", ArtifactKind.CAPABILITY_SUPPORT, (
        _ref(DependencyKind.ARTIFACT, composition.artifact_id),))
    unrelated = _node("feature:beta", ArtifactKind.ATLAS_FEATURE, (source_b,))
    return DependencyIndex.build((
        feature, frame, motif, cache, composition, capability, unrelated,
    )), source_a, source_b

if __name__ == "__main__":
    unittest.main()
