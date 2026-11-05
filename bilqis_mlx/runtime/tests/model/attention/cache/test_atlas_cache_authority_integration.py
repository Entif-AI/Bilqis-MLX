"""B14.4 cache rebuild authority comes from live B13/A12/context owners."""
from __future__ import annotations

from dataclasses import replace
from contextlib import ExitStack
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.atlas_cache_codec import (
    HEAD_WIDTH, CacheBinding, CacheEligibilityReceipt, codec_manifest,
    encode_cold_cache, issue_cache_eligibility, rebuild_revoked_cache,
)
from bilqis_mlx.runtime.atlas_cache_binding import binding_digest
from bilqis_mlx.runtime.atlas_cache_eligibility import CacheEligibilityInputs
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.bamf_bundle import publish_bamf_generation
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    DECLARED, candidate, parent_state, shape_patch,
)
from bilqis_mlx.runtime.tests.model.attention.cache.authority_fixture import (
    OWNER_ID, PUBLIC_KEY_HEX, authority_for_registry, install_test_owner,
)
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


class CacheAuthorityIntegrationTests(unittest.TestCase):
    def setUp(self):
        install_test_owner(self, eligibility=False)

    def test_caller_matching_receipt_is_not_authority(self):
        binding = CacheBinding(
            codec_manifest(), *(value * 64 for value in "123456789abcde"),
            17, OWNER_ID, PUBLIC_KEY_HEX)
        forged = CacheEligibilityReceipt(
            binding_digest(binding).hex(), binding.source_release_sha256,
            binding.semantic_release_sha256, binding.source_rights_sha256,
            binding.rights_purpose_sha256, binding.policy_epoch_sha256,
            binding.context_eligibility_sha256, True)
        stale = encode_cold_cache(
            authority_for_registry(SourceAuthorityRegistry((SourceAuthorityKey(
                OWNER_ID, PUBLIC_KEY_HEX,
                (SourceAuthorityScope(DependencyKind.ARTIFACT, "cache:"),)),))),
            np.zeros((256, HEAD_WIDTH), dtype=np.float32), binding.codec_manifest,
            binding=binding)
        with self.assertRaises(BilqisError):
            rebuild_revoked_cache(
                authority_for_registry(SourceAuthorityRegistry((SourceAuthorityKey(
                    OWNER_ID, PUBLIC_KEY_HEX,
                    (SourceAuthorityScope(DependencyKind.ARTIFACT, "cache:"),)),))),
                stale, replace(binding, policy_epoch_sha256="f" * 64),
                eligibility_receipt=forged,
                canonical_fp32_source=lambda: np.zeros(
                    (256, HEAD_WIDTH), dtype=np.float32),
                persist=lambda _: self.fail("caller receipt persisted"))

    def test_live_b13_a12_and_context_authority_issue_exact_rebuild_receipt(self):
        selection = _selection()
        frames, task, frontier, policy = _context(selection.release_sha256)
        clearance = _clearance(selection, frontier)
        with TemporaryDirectory() as temporary, patch.dict(
                os.environ, {"BILQIS_DATA_PLANE": str(Path(temporary) / "plane.sqlite3")}):
            run = Path(temporary) / "run"
            source = _source(selection, frontier)
            with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
                pointer = publish_bamf_generation(run, source)
            inputs = CacheEligibilityInputs(
                run / "bamf-state.json", clearance, selection, frontier,
                _EXPORTED, frames, task, policy,
            )
            authority = authority_for_registry(
                _registry(), eligibility_source=lambda: inputs)
            binding = _binding(
                pointer, source, selection, clearance, frames, task, frontier, policy)
            with _cache_shape_patch():
                receipt = issue_cache_eligibility(authority, binding)
            stale_binding = replace(binding, generation_sha256="f" * 64)
            stale = encode_cold_cache(
                authority, np.ones((256, HEAD_WIDTH), dtype=np.float32),
                stale_binding.codec_manifest, binding=stale_binding)
            persisted = []
            with _cache_shape_patch():
                rebuilt = rebuild_revoked_cache(
                    authority, stale, binding, eligibility_receipt=receipt,
                    canonical_fp32_source=lambda: np.zeros(
                        (256, HEAD_WIDTH), dtype=np.float32),
                    persist=persisted.append)
            self.assertTrue(rebuilt.persisted)
            self.assertEqual(persisted, [rebuilt.artifact])

            for changed in (
                replace(binding, generation_sha256="0" * 64),
                replace(binding, lineage_sha256="0" * 64),
                replace(binding, source_release_sha256="0" * 64),
                replace(binding, semantic_release_sha256="0" * 64),
                replace(binding, source_rights_sha256="0" * 64),
                replace(binding, rights_purpose_sha256="0" * 64),
                replace(binding, policy_epoch_sha256="0" * 64),
                replace(binding, context_eligibility_sha256="0" * 64),
                replace(binding, inference_state_sha256="0" * 64),
            ):
                with self.subTest(changed=changed), self.assertRaises(BilqisError), \
                        _cache_shape_patch():
                    issue_cache_eligibility(authority, changed)


if __name__ == "__main__":
    unittest.main()
