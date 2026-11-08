"""Fixture construction for B14/C09 accepted-cache integration tests."""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import replace
import json
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import numpy as np

from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.atlas_cache_codec import HEAD_WIDTH, CacheBinding, codec_manifest
from bilqis_mlx.runtime.atlas_cache_eligibility import CacheEligibilityInputs
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle import publish_bamf_generation
from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_cache_authority
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    DECLARED, acceptance, candidate, parent_state, shape_patch,
)
from bilqis_mlx.runtime.tests.model.attention.cache.authority_fixture import (
    OWNER_ID, PUBLIC_KEY_HEX,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import AUTHORITY
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_release_audit import ExportClearanceReceipt
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextEligibility, ContextMember, ContextPolicy,
    SourceFrontier, SourceGrant, TaskScope, frame_evidence_digest,
    member_evidence_digest, project_context,
)
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.semantics.frame_schema import (
    ConceptRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan,
    make_frame_instance,
)


_A12_PRIVATE = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("29" * 32))
_A12_PUBLIC = _A12_PRIVATE.public_key().public_bytes(
    Encoding.Raw, PublicFormat.Raw).hex()
_A12_OWNER = "fixture:a12-source-owner"
_EXPORTED = ("1" * 64,)


def _cache_shape_patch():
    stack = ExitStack()
    stack.enter_context(shape_patch())
    stack.enter_context(patch(
        "bilqis_mlx.runtime.backbone_identity.expected_bamf_shapes",
        return_value=DECLARED,
    ))
    stack.enter_context(patch(
        "bilqis_mlx.runtime.topology_v2.validation.expected_bamf_shapes",
        return_value=DECLARED,
    ))
    return stack


def _selection() -> AtlasArtifactSelection:
    path = Path(__file__).resolve().parents[5] / "semantics" / "atlas_source_pins_v1.json"
    entry = json.loads(path.read_text())["entries"][0]
    return AtlasArtifactSelection(
        "fixture-atlas", entry["bundle_id"], entry["release_sha256"],
        entry["source_bundle_id"])


def _context(release: str):
    schema = FrameSchema(
        "frame:cache-authority", 1, "source:cache-authority",
        (RoleSpec("subject", ("Entity",), 1, 1),), "ORDERED", "fixture")
    frame = make_frame_instance(
        schema, source_instance_id="cache-authority-source", structural_path=(),
        source_span=SourceSpan(0, 8), parent_occurrence_id=None,
        bindings=(RoleOccurrence(
            "subject", 0,
            concept=ConceptRef(
                "formal:cache-authority", release, 0, ("Entity",),
                "fixture:cache-authority")),),
        causal_prefix_end=8)
    frame_source = "source:frame:cache-authority"
    member_source = "source:member:cache-authority"
    member = ContextMember("subject", 0, member_source, 8)
    envelope = ContextEligibility(
        "frame:cache-authority", frame, frame_source, (member,),
        "fixture:principal", "fixture:tenant", "TRAINING", PUBLIC_FORMAL,
        release, "fixture:region", "fixture:scope", PUBLIC_FORMAL,
        7, 2, 4, 5, 0, None, 8)
    grants = (
        SourceGrant(
            frame_source, "fixture:principal", "fixture:tenant", PUBLIC_FORMAL,
            release, frame_evidence_digest(frame), ("TRAINING",),
            ("fixture:region",), ("fixture:scope",), 2, 4, 5, 0),
        SourceGrant(
            member_source, "fixture:principal", "fixture:tenant", PUBLIC_FORMAL,
            release, member_evidence_digest(frame, member), ("TRAINING",),
            ("fixture:region",), ("fixture:scope",), 2, 4, 5, 0),
    )
    frontier = SourceFrontier(2, 4, tuple(sorted(
        grants, key=lambda item: item.source_handle)))
    task = TaskScope(
        "fixture:principal", "fixture:tenant", "TRAINING", release,
        "fixture:region", "fixture:scope", 6, 6, 8)
    policy = ContextPolicy(
        "fixture:policy", 7, 2, ("TRAINING",), (PUBLIC_FORMAL,),
        ("fixture:region",), ("fixture:scope",), (PUBLIC_FORMAL,), (), ())
    return (envelope,), task, frontier, policy


def _clearance(selection, frontier):
    receipt = ExportClearanceReceipt(
        _A12_OWNER, selection.bundle_id, selection.release_sha256,
        selection.source_bundle_id, contract_digest(frontier),
        frontier.rights_epoch, frontier.correction_generation,
        _EXPORTED, (), (), (), "0" * 128)
    return replace(
        receipt, signature_hex=_A12_PRIVATE.sign(receipt.signing_bytes()).hex())


def _registry() -> SourceAuthorityRegistry:
    return SourceAuthorityRegistry(tuple(sorted((
        SourceAuthorityKey(
            OWNER_ID, PUBLIC_KEY_HEX,
            (SourceAuthorityScope(DependencyKind.ARTIFACT, "cache:"),)),
        SourceAuthorityKey(
            _A12_OWNER, _A12_PUBLIC,
            (SourceAuthorityScope(DependencyKind.ARTIFACT, "a12-export:"),)),
    ), key=lambda item: item.owner_id)))


def _accepted_registry() -> SourceAuthorityRegistry:
    return SourceAuthorityRegistry(tuple(sorted(
        (*_registry().keys, *AUTHORITY.keys), key=lambda item: item.owner_id)))


def _source(selection, frontier):
    source = candidate(parent_state())
    return replace(
        source,
        provenance=replace(
            source.provenance, release_digest=selection.release_sha256),
        correction_frontier={
            **source.correction_frontier,
            "release_digest": selection.release_sha256,
            "rights_epoch": frontier.rights_epoch,
            "correction_generation": frontier.correction_generation,
            "source_authority_registry_sha256": _accepted_registry().digest,
            "source_authority_registry": _accepted_registry().to_record(),
        },
        compiler_features={
            **source.compiler_features,
            "rights_epoch": frontier.rights_epoch,
            "correction_generation": frontier.correction_generation,
        },
    )


def _binding(pointer, source, selection, clearance, frames, task, frontier, policy):
    projection = project_context(frames, task, frontier, policy)
    purpose = contract_digest({
        "purpose": task.purpose, "jurisdiction": task.jurisdiction,
        "scope": task.scope})
    policy_digest = contract_digest({
        "policy_id": policy.policy_id, "policy_epoch": policy.policy_epoch,
        "rights_epoch": policy.rights_epoch})
    lineage_digest = contract_digest({
        "schema": "bilqis.mlx.bamf-cache-lineage/v1", "run_id": source.run_id})
    with _cache_shape_patch():
        inference_digest = execution_generation_digest(
            source.retained_state.optimizer.parameters,
            spec=source.topology, extents=source.extents)
    return CacheBinding(
        codec_manifest(), pointer["manifest_sha256"], lineage_digest,
        source.topology.digest, selection.source_bundle_id,
        selection.release_sha256, clearance.clearance_sha256, purpose,
        policy_digest, projection.digest, "a" * 64, "b" * 64,
        "c" * 64, "d" * 64, inference_digest, 17, OWNER_ID, PUBLIC_KEY_HEX)


def _publish_cache_fixture(run, source):
    with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
        return publish_bamf_generation(
            run, source, acceptance=acceptance(source))


def _accepted_cache_authority(
    run, selection, clearance, frames, task, frontier, policy,
):
    inputs = CacheEligibilityInputs(
        run / "bamf-state.json", clearance, selection, frontier,
        _EXPORTED, frames, task, policy,
        lambda binding: np.zeros((256, HEAD_WIDTH), dtype=np.float32),
    )
    registry = _accepted_registry()
    eligibility_source = lambda: inputs
    with _cache_shape_patch():
        _cache, authority = bind_accepted_cache_authority(
            run, eligibility_source)
    return authority, registry, eligibility_source
