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

    def test_held_gloss_cannot_promote_across_semantic_or_teacher_surfaces(self):
        from bilqis_mlx.factory.skos_curriculum import (
            LearnedFrontier, SOURCE_FAMILY_ADAPTERS,
            _compile_semantic_curriculum_snapshot,
            _compile_source_constructive_lessons_snapshot,
        )
        from bilqis_mlx.factory.tests.test_skos_curriculum import _snapshot
        from bilqis_mlx.semantics.atlas_features import (
            FeatureSchema, build_feature_manifest,
            plan_prospective_identity_features,
        )
        from bilqis_mlx.runtime.model_topology_v2 import (
            GenerationExtents, ModelTopologySpecV2,
        )
        from bilqis_mlx.semantics.atlas.vocabulary import (
            VocabularyPrior, plan_vocabulary_extension,
        )
        from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
        from bilqis_mlx.semantics.atlas_projection import AtlasLabel

        original = _snapshot()
        held = next(
            row for row in original.withheld_rows
            if row.source_disposition == "SOURCE_HELD")
        admitted = original.concepts[0]
        plausible = "plausible English gloss matching the held source"
        renamed = replace(
            admitted,
            concept=replace(
                admitted.concept,
                labels=(
                    AtlasLabel("altLabel", "near synonym"),
                    AtlasLabel("prefLabel", plausible),
                )))
        relabeled = replace(
            original, concepts=(renamed, *original.concepts[1:]))

        for snapshot in (original, relabeled):
            with self.subTest(labels=snapshot.concepts[0].concept.labels):
                admitted_ids = {entry.semantic_id for entry in snapshot.abi_entries}
                self.assertNotIn(held.semantic_id, admitted_ids)

                features = build_feature_manifest(snapshot, FeatureSchema((), ()))
                self.assertIn(
                    (held.semantic_id, held.reason_code), features.held_reasons)
                with self.assertRaises(BilqisError) as caught:
                    features.features_for(
                        held.semantic_id, "UNKNOWN", "UNKNOWN", "task:held")
                self.assertEqual(
                    caught.exception.context["reason"],
                    "BAMF_FEATURE_CONCEPT_NOT_ADMITTED")
                with self.assertRaises(BilqisError):
                    plan_prospective_identity_features(
                        snapshot, features, (held.semantic_id,),
                        expected_feature_digest=features.digest)

                selection = AtlasArtifactSelection(
                    "fixture", snapshot.bundle_id, snapshot.release_sha256,
                    snapshot.source_bundle_id)
                active = tuple(
                    entry.semantic_id for entry in snapshot.abi_entries
                    if entry.active)
                prior = VocabularyPrior(
                    selection,
                    GenerationExtents(
                        1, 1, snapshot.active_set_sha256,
                        "b" * 64, features.digest),
                    features, FeatureSchema((), ()), active, "e" * 64)
                with patch(
                        "bilqis_mlx.semantics.atlas.vocabulary_planning.load_pinned_atlas_snapshot",
                        return_value=snapshot), self.assertRaises(BilqisError):
                    plan_vocabulary_extension(
                        prior, (held.semantic_id,), ModelTopologySpecV2())

                source_lessons = _compile_source_constructive_lessons_snapshot(
                    snapshot).lessons
                self.assertFalse(any(
                    held.semantic_id in (
                        lesson.semantic_id, *lesson.constituents,
                        *lesson.prerequisite_closure)
                    for lesson in source_lessons))

                teacher = _compile_semantic_curriculum_snapshot(
                    snapshot, SOURCE_FAMILY_ADAPTERS,
                    LearnedFrontier(
                        snapshot.release_sha256,
                        claimed_exposed=(held.semantic_id,),
                        claimed_qualified=(held.semantic_id,)))
                self.assertNotIn(
                    held.semantic_id, teacher.source_eligible_concept_ids)
                self.assertFalse(any(
                    held.semantic_id in (
                        lesson.semantic_id, *lesson.constituents,
                        *lesson.prerequisite_closure)
                    for lesson in teacher.source_lessons))
                self.assertEqual(
                    next(row for row in teacher.source_hold_rows
                         if row.semantic_id == held.semantic_id).reason_code,
                    held.reason_code)

    @unittest.skipUnless(
        os.environ.get("BILQIS_A01_ATLAS_BUNDLE")
        and os.environ.get("BILQIS_A01_SOURCE_BUNDLE"),
        "real pinned A01 artifact/source bundle is an optional integration witness",
    )
    def test_real_pinned_producers_replay_one_authority(self):
        selection = _selection()
        selection = replace(
            selection, path=os.environ["BILQIS_A01_ATLAS_BUNDLE"])
        snapshot = load_pinned_atlas_snapshot(selection)
        feature_schema = FeatureSchema((), ())
        features = build_feature_manifest(snapshot, feature_schema)
        active = tuple(
            entry.semantic_id for entry in snapshot.abi_entries if entry.active)
        bank_count = max(
            1,
            max((entry.index for entry in snapshot.abi_entries if entry.active),
                default=0) // ModelTopologySpecV2.semantic_bank_rows + 1)
        prior = VocabularyPrior(
            selection,
            GenerationExtents(
                bank_count, 1, snapshot.active_set_sha256,
                "b" * 64, features.digest),
            features, feature_schema, active, "e" * 64)
        active_set = set(active)
        next_source = next(
            entry for entry in snapshot.abi_entries
            if entry.semantic_id not in active_set
            and any(item.concept.semantic_id == entry.semantic_id
                    for item in snapshot.concepts)
            and not any(
                row.semantic_id == entry.semantic_id
                and row.source_disposition != "SOURCE_ELIGIBLE"
                for row in snapshot.withheld_rows))
        abi = plan_vocabulary_extension(
            prior, (next_source.semantic_id,), ModelTopologySpecV2())
        mirror = build_registry_mirror_delta(
            prior, abi,
            source_bundle_path=Path(os.environ["BILQIS_A01_SOURCE_BUNDLE"]))
        ast = _load_pinned_released_frame_schemas("boolean", selection)
        lessons = compile_source_constructive_lessons(selection)
        receipt = audit_atlas_authority(
            selection, abi, ast, lessons, mirror)
        self.assertEqual(receipt.source_release_sha256, snapshot.release_sha256)
        self.assertEqual(len(receipt.consumer_bindings), 5)
        self.assertEqual(
            receipt.prior_abi_sha256,
            "30d18c7140d49c168488416e04644b934ea79492561c2b73f65e55be18ed4e8c")
        self.assertIn(
            ("bilqis_mlx/semantics/legacy_abi_v1.json",
             "DECLARED_FORMAL_DOMAIN"),
            receipt.source_dispositions)
        self.assertIn(
            ("bilqis_mlx/semantics/numeric_v1.json",
             "DECLARED_FORMAL_DOMAIN"),
            receipt.source_dispositions)


class AtlasExportClearanceTests(unittest.TestCase):
    def setUp(self):
        self.selection = _selection()
        self.frontier = SourceFrontier(7, 3, ())
        self.public = ("1" * 64, "2" * 64)
        self.receipt = _receipt(
            self.selection, self.frontier, self.public,
            private=("3" * 64,), revoked=("4" * 64,), lineage=("5" * 64,))

    def test_owner_signed_exact_export_is_accepted(self):
        self.assertEqual(
            _verify(self.receipt, self.selection, self.frontier, self.public),
            self.receipt.clearance_sha256)

    def test_caller_minted_matching_fields_do_not_gain_authority(self):
        forged = replace(self.receipt, signature_hex="0" * 128)
        with self.assertRaises(BilqisError):
            _verify(forged, self.selection, self.frontier, self.public)

    def test_stale_or_foreign_release_clearance_fails_closed(self):
        newer = SourceFrontier(8, 3, ())
        with self.assertRaises(BilqisError):
            _verify(self.receipt, self.selection, newer, self.public)
        foreign = replace(self.receipt, source_bundle_id="6" * 64)
        foreign = replace(
            foreign, signature_hex=PRIVATE.sign(foreign.signing_bytes()).hex())
        with self.assertRaises(BilqisError):
            _verify(foreign, self.selection, self.frontier, self.public)

    def test_private_revoked_or_mismatched_export_set_is_rejected(self):
        for artifacts in (("3" * 64,), ("4" * 64,), ("1" * 64,)):
            with self.subTest(artifacts=artifacts), self.assertRaises(BilqisError):
                _verify(self.receipt, self.selection, self.frontier, artifacts)

    def test_revocation_lineage_and_frontier_are_signature_bound(self):
        changed = replace(self.receipt, revocation_lineage=("6" * 64,))
        with self.assertRaises(BilqisError):
            _verify(changed, self.selection, self.frontier, self.public)


if __name__ == "__main__":
    unittest.main()
