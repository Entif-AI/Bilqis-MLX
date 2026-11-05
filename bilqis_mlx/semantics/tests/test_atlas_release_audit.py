"""A12 current consumers share source authority; exports stay frontier-bound."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.skos_curriculum import compile_source_constructive_lessons
from bilqis_mlx.factory.skos_curriculum.lesson_types import (
    SourceConstructiveLesson, SourceConstructiveLessonSet,
)
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2
from bilqis_mlx.semantics.atlas.snapshot import load_pinned_atlas_snapshot
from bilqis_mlx.semantics.atlas.vocabulary import (
    VocabularyAllocation, VocabularyExtension, VocabularyPrior,
    plan_vocabulary_extension,
)
from bilqis_mlx.semantics.atlas.vocabulary_resources import (
    RegistryMirrorDelta, RegistryMirrorRow, build_registry_mirror_delta,
)
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_release_audit import (
    ExportClearanceReceipt, SOURCE_DISPOSITIONS, audit_atlas_authority,
    validate_export_clearance_context,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
from bilqis_mlx.semantics.context_eligibility import SourceFrontier
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.released_frame_schemas import (
    _load_pinned_released_frame_schemas, load_released_frame_schemas,
    seal_released_frame_schemas,
)


PRIVATE = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("29" * 32))
PUBLIC = PRIVATE.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
OWNER = "fixture:a12-source-owner"
REGISTRY = SourceAuthorityRegistry((SourceAuthorityKey(
    OWNER, PUBLIC, (SourceAuthorityScope(DependencyKind.ARTIFACT, "a12-export:"),)),))


def _selection():
    path = Path(__file__).resolve().parents[1] / "atlas_source_pins_v1.json"
    entry = json.loads(path.read_text())["entries"][0]
    return AtlasArtifactSelection(
        "fixture-atlas", entry["bundle_id"], entry["release_sha256"],
        entry["source_bundle_id"])


def _receipt(selection, frontier, exported, *, private=(), revoked=(), lineage=()):
    receipt = ExportClearanceReceipt(
        OWNER, selection.bundle_id, selection.release_sha256,
        selection.source_bundle_id, contract_digest(frontier),
        frontier.rights_epoch, frontier.correction_generation,
        exported, private, revoked, lineage, "0" * 128)
    return replace(receipt, signature_hex=PRIVATE.sign(receipt.signing_bytes()).hex())


def _verify(receipt, selection, frontier, artifacts):
    REGISTRY.verify_detached(
        receipt.source_owner, receipt.dependency(),
        receipt.signature_hex, receipt.signing_bytes())
    return validate_export_clearance_context(receipt, selection, frontier, artifacts)


def _typed_authority_fixture():
    from bilqis_mlx.semantics.tests.test_atlas_features import _snapshot
    snapshot = _snapshot((
        ("urn:concept:prior", ("urn:type:Entity",)),
        ("urn:concept:next", ("urn:type:Entity",)),
    ))
    selection = AtlasArtifactSelection(
        "fixture-atlas", snapshot.bundle_id, snapshot.release_sha256,
        snapshot.source_bundle_id)
    entry = next(
        item for item in snapshot.abi_entries
        if item.semantic_id == "urn:concept:next")
    allocation = VocabularyAllocation(
        entry.semantic_id, entry.index, entry.bank, entry.row, entry.source)
    abi = VocabularyExtension(
        "e" * 64, "f" * 64, snapshot.source_bundle_id,
        snapshot.release_sha256, "1" * 64, "2" * 64, "3" * 64,
        (allocation,), (entry.index,), "4" * 64, max(1, entry.bank + 1))
    mirror = RegistryMirrorDelta(
        abi.semantic_release, abi.source_bundle_id, abi.parent_generation_id,
        abi.source_allocation_digest, abi.active_indices,
        tuple(RegistryMirrorRow(
            item.semantic_id, item.abi_index, item.bank, item.row,
            item.source_status, "fixture description", "7" * 64)
              for item in abi.allocations))
    from bilqis_mlx.semantics.tests.released_schemas.fixtures import _schema
    schema = _schema()
    tag_map = SchemaTagMap.from_schemas(snapshot.release_sha256, (schema,))
    staged = seal_released_frame_schemas((schema,), tag_map, snapshot)
    payload = staged.canonical_bytes()
    manifest_digest = hashlib.sha256(payload).hexdigest()
    ast = load_released_frame_schemas(
        payload, expected_sha256=manifest_digest, snapshot=snapshot,
        expected_semantic_release=snapshot.release_sha256,
        expected_schema_map_sha256=tag_map.digest)
    lessons = SourceConstructiveLessonSet(
        snapshot.release_sha256, "5" * 64, (), ())
    ast_pin = {
        "family": "fixture",
        "semantic_release": snapshot.release_sha256,
        "atlas_bundle_id": snapshot.bundle_id,
        "source_bundle_id": snapshot.source_bundle_id,
        "schema_manifest_sha256": ast.trusted_sha256,
        "schema_map_sha256": ast.manifest.schema_map.digest,
    }
    return snapshot, selection, abi, ast, lessons, mirror, ast_pin


class AtlasAuthorityAuditTests(unittest.TestCase):
    def test_current_consumers_bind_one_pinned_source(self):
        snapshot, selection, abi, ast, lessons, mirror, ast_pin = _typed_authority_fixture()
        with patch(
                "bilqis_mlx.semantics.atlas_release_audit.load_pinned_atlas_snapshot",
                return_value=snapshot), patch(
                "bilqis_mlx.semantics.atlas_release_audit._current_prior_abi_sha256",
                return_value=snapshot.prior_abi_sha256), patch(
                "bilqis_mlx.semantics.atlas_release_audit._source_pins",
                return_value=(ast_pin,)):
            first = audit_atlas_authority(
                selection, abi, ast, lessons, mirror)
            second = audit_atlas_authority(
                selection, abi, ast, lessons, mirror)
        self.assertEqual(first, second)
        self.assertEqual(
            tuple(item.consumer for item in first.consumer_bindings),
            ("abi", "ast_frames", "lessons", "graph_projection",
             "registry_mirror"))
        self.assertEqual(
            {item.semantic_release for item in first.consumer_bindings},
            {snapshot.release_sha256})
        self.assertEqual(
            first.source_dispositions[:len(SOURCE_DISPOSITIONS)],
            SOURCE_DISPOSITIONS)
        self.assertEqual(first.prior_abi_sha256, snapshot.prior_abi_sha256)
        self.assertEqual(
            first.source_dispositions[len(SOURCE_DISPOSITIONS):],
            tuple(
                (binding.source_owner, "DECLARED_FORMAL_DOMAIN")
                for binding in snapshot.formal_domain_bindings))

    def test_first_mismatched_consumer_fails_closed(self):
        snapshot, selection, abi, ast, lessons, mirror, ast_pin = _typed_authority_fixture()
        with patch(
                "bilqis_mlx.semantics.atlas_release_audit.load_pinned_atlas_snapshot",
                return_value=snapshot), patch(
                "bilqis_mlx.semantics.atlas_release_audit._current_prior_abi_sha256",
                return_value=snapshot.prior_abi_sha256), patch(
                "bilqis_mlx.semantics.atlas_release_audit._source_pins",
                return_value=(ast_pin,)):
            with self.assertRaises(BilqisError) as caught:
                audit_atlas_authority(
                    selection, replace(abi, semantic_release="9" * 64),
                    ast, lessons, mirror)
        self.assertEqual(
            caught.exception.context["reason"],
            "A12_AUTHORITY_SOURCE_BINDING_MISMATCH")

    def test_stale_shadow_catalog_is_not_an_authority_input(self):
        snapshot, selection, abi, ast, lessons, mirror, ast_pin = _typed_authority_fixture()
        with patch(
                "bilqis_mlx.semantics.atlas_release_audit.load_pinned_atlas_snapshot",
                return_value=snapshot), patch(
                "bilqis_mlx.semantics.atlas_release_audit._current_prior_abi_sha256",
                return_value=snapshot.prior_abi_sha256), patch(
                "bilqis_mlx.semantics.atlas_release_audit._source_pins",
                return_value=(ast_pin,)):
            baseline = audit_atlas_authority(
                selection, abi, ast, lessons, mirror)
            stale_shadow = {
                "urn:concept:next": "plausible renamed gloss",
                "semantic_release": "0" * 64,
            }
            stale_shadow["urn:concept:next"] = "another label"
            replay = audit_atlas_authority(
                selection, abi, ast, lessons, mirror)
        self.assertEqual(replay, baseline)

    def test_unpinned_ast_and_foreign_lesson_inputs_fail_closed(self):
        snapshot, selection, abi, ast, lessons, mirror, ast_pin = _typed_authority_fixture()
        common = (
            patch(
                "bilqis_mlx.semantics.atlas_release_audit.load_pinned_atlas_snapshot",
                return_value=snapshot),
            patch(
                "bilqis_mlx.semantics.atlas_release_audit._current_prior_abi_sha256",
                return_value=snapshot.prior_abi_sha256),
        )
        with common[0], common[1], patch(
                "bilqis_mlx.semantics.atlas_release_audit._source_pins",
                return_value=()):
            with self.assertRaises(BilqisError) as caught:
                audit_atlas_authority(selection, abi, ast, lessons, mirror)
        self.assertEqual(
            caught.exception.context["reason"],
            "A12_AUTHORITY_AST_SOURCE_PIN_MISMATCH")

        entry = next(iter(snapshot.abi_entries))
        lesson = SourceConstructiveLesson(
            snapshot.release_sha256, entry.semantic_id, "positive_identity",
            "8" * 64,
            ("identity", entry.semantic_id, "source:fixture"),
            ("identity", entry.semantic_id, "source:contrast"),
            "SEMANTIC_ID", "fixture.checker/v1", (entry.semantic_id,), (),
            ("source-identity",))
        forged = replace(
            lesson,
            constituents=(entry.semantic_id, "urn:foreign:not-admitted"),
            prerequisite_closure=("urn:foreign:not-admitted",))
        forged_set = replace(lessons, lessons=(forged,))
        with patch(
                "bilqis_mlx.semantics.atlas_release_audit.load_pinned_atlas_snapshot",
                return_value=snapshot), patch(
                "bilqis_mlx.semantics.atlas_release_audit._current_prior_abi_sha256",
                return_value=snapshot.prior_abi_sha256), patch(
                "bilqis_mlx.semantics.atlas_release_audit._source_pins",
                return_value=(ast_pin,)):
            with self.assertRaises(BilqisError) as caught:
                audit_atlas_authority(
                    selection, abi, ast, forged_set, mirror)
        self.assertEqual(
            caught.exception.context["reason"],
            "A12_AUTHORITY_LESSON_SOURCE_MISMATCH")
