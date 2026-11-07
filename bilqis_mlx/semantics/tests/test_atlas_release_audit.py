"""A12 current semantic consumers must replay one admitted source authority."""
from contextlib import ExitStack, contextmanager
from dataclasses import replace
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError, ErrorBus, SEMANTIC_FRAME
from bilqis_mlx.factory.skos_curriculum import (
    _compile_source_constructive_lessons_snapshot,
)
from bilqis_mlx.factory.tests.sources.test_skos_curriculum import (
    _snapshot as _source_grade_snapshot,
)
from bilqis_mlx.factory.skos_curriculum.lesson_types import SourceConstructiveLessonSet
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2
from bilqis_mlx.semantics.atlas.vocabulary import (
    VocabularyAllocation, VocabularyExtension, VocabularyPrior,
    plan_vocabulary_extension,
)
from bilqis_mlx.semantics.atlas.vocabulary_resources import (
    RegistryMirrorDelta, RegistryMirrorRow,
)
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas_projection import (
    SHAPE_POLICY, _canonical_bytes as _atlas_bytes, _digest as _atlas_sha256,
)
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_release_audit import SOURCE_DISPOSITIONS, audit_atlas_authority
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.released_frame_schemas import (
    load_released_frame_schemas, seal_released_frame_schemas,
)


def _typed_authority_fixture():
    from bilqis_mlx.semantics.tests.test_atlas_features import _snapshot
    from bilqis_mlx.semantics.tests.released_schemas.fixtures import _schema

    snapshot = _snapshot((("urn:concept:prior", ("urn:type:Entity",)),
                          ("urn:concept:next", ("urn:type:Entity",))))
    selection = AtlasArtifactSelection(
        "fixture-atlas", snapshot.bundle_id, snapshot.release_sha256,
        snapshot.source_bundle_id)
    entry = next(item for item in snapshot.abi_entries
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
        (RegistryMirrorRow(
            allocation.semantic_id, allocation.abi_index, allocation.bank,
            allocation.row, allocation.source_status, "fixture definition",
            "7" * 64),))
    schema = _schema()
    tag_map = SchemaTagMap.from_schemas(snapshot.release_sha256, (schema,))
    staged = seal_released_frame_schemas((schema,), tag_map, snapshot)
    payload = staged.canonical_bytes()
    ast = load_released_frame_schemas(
        payload, expected_sha256=hashlib.sha256(payload).hexdigest(),
        snapshot=snapshot, expected_semantic_release=snapshot.release_sha256,
        expected_schema_map_sha256=tag_map.digest)
    lessons = SourceConstructiveLessonSet(snapshot.release_sha256, "5" * 64, (), ())
    features = build_feature_manifest(snapshot, FeatureSchema((), ()))
    active_ids = tuple(item.semantic_id for item in snapshot.abi_entries if item.active)
    prior = VocabularyPrior(
        selection, GenerationExtents(1, 1, snapshot.active_set_sha256,
                                     "b" * 64, features.digest),
        features, FeatureSchema((), ()), active_ids, "e" * 64)
    ast_pin = {
        "family": "fixture", "semantic_release": snapshot.release_sha256,
        "atlas_bundle_id": snapshot.bundle_id,
        "source_bundle_id": snapshot.source_bundle_id,
        "schema_manifest_sha256": ast.trusted_sha256,
        "schema_map_sha256": ast.manifest.schema_map.digest,
    }
    return snapshot, selection, abi, ast, lessons, mirror, prior, ast_pin


@contextmanager
def _replayed(fixture, *, ast_pins=True):
    snapshot, _selection, abi, _ast, lessons, mirror, _prior, ast_pin = fixture

    def lesson_replay(candidate, _release):
        if candidate != lessons:
            ErrorBus.raise_(
                SEMANTIC_FRAME.BINDING.INVALID,
                reason="BAMF_LESSON_SOURCE_PROJECTION_DRIFT",
                role_id="<a12-test>", span_start=0, span_end=0)

    with ExitStack() as stack:
        stack.enter_context(patch(
            "bilqis_mlx.semantics._atlas_release_audit.authority.load_pinned_atlas_snapshot",
            return_value=snapshot))
        stack.enter_context(patch(
            "bilqis_mlx.semantics._atlas_release_audit.authority._current_prior_abi_sha256",
            return_value=snapshot.prior_abi_sha256))
        stack.enter_context(patch(
            "bilqis_mlx.semantics._atlas_release_audit.authority._source_pins",
            return_value=(ast_pin,) if ast_pins else ()))
        stack.enter_context(patch(
            "bilqis_mlx.semantics._atlas_release_audit.authority.plan_vocabulary_extension",
            return_value=abi))
        stack.enter_context(patch(
            "bilqis_mlx.semantics._atlas_release_audit.authority.build_registry_mirror_delta",
            return_value=mirror))
        stack.enter_context(patch(
            "bilqis_mlx.semantics._atlas_release_audit.authority.assert_source_lesson_set_current",
            side_effect=lesson_replay))
        yield


def _audit(fixture, *, abi=None, ast=None, lessons=None, mirror=None):
    _snapshot, selection, base_abi, base_ast, base_lessons, base_mirror, prior, _pin = fixture
    return audit_atlas_authority(
        selection, abi or base_abi, ast or base_ast, lessons or base_lessons,
        mirror or base_mirror, abi_prior=prior,
        source_bundle_path=Path("/synthetic-source"))


class AtlasAuthorityAuditTests(unittest.TestCase):
    def test_data_only_source_successor_reuses_generic_semantic_path(self):
        snapshot = _source_grade_snapshot()
        active_ids = tuple(
            entry.semantic_id for entry in snapshot.abi_entries if entry.active)
        active_indices = tuple(
            entry.index for entry in snapshot.abi_entries if entry.active)
        snapshot = replace(
            snapshot,
            shape_policy_sha256=_atlas_sha256(_atlas_bytes(SHAPE_POLICY)),
            active_set_sha256=_atlas_sha256(_atlas_bytes(list(active_indices))),
        )
        features = build_feature_manifest(snapshot, FeatureSchema((), ()))
        prior = VocabularyPrior(
            AtlasArtifactSelection(
                "fixture", snapshot.bundle_id, snapshot.release_sha256,
                snapshot.source_bundle_id),
            GenerationExtents(
                1, 1, snapshot.active_set_sha256, "b" * 64, features.digest),
            features, FeatureSchema((), ()), active_ids, "e" * 64,
        )
        successor_id = "urn:lex:root"
        with patch(
                "bilqis_mlx.semantics.atlas.vocabulary_planning."
                "load_pinned_atlas_snapshot",
                return_value=snapshot):
            extension = plan_vocabulary_extension(
                prior, (successor_id,), ModelTopologySpecV2())

        lessons = _compile_source_constructive_lessons_snapshot(snapshot)
        allocation, = extension.allocations
        self.assertEqual(allocation.semantic_id, successor_id)
        self.assertEqual(allocation.abi_index, snapshot.abi_for_semantic(successor_id).index)
        self.assertEqual(
            extension.active_indices,
            tuple(sorted((*active_indices, allocation.abi_index))))
        self.assertEqual(
            tuple(
                entry.index for entry in snapshot.abi_entries
                if entry.semantic_id in active_ids),
            active_indices)
        self.assertTrue(any(
            lesson.semantic_id == successor_id
            and lesson.family_id == "positive_identity"
            for lesson in lessons.lessons))

    def test_current_consumers_bind_one_pinned_source_deterministically(self):
        fixture = _typed_authority_fixture()
        snapshot = fixture[0]
        with _replayed(fixture):
            first = _audit(fixture)
            second = _audit(fixture)
        self.assertEqual(first, second)
        self.assertEqual(
            tuple(item.consumer for item in first.consumer_bindings),
            ("abi", "ast_frames", "lessons", "graph_projection", "registry_mirror"))
        self.assertEqual({item.semantic_release for item in first.consumer_bindings},
                         {snapshot.release_sha256})
        self.assertEqual(first.source_dispositions[:len(SOURCE_DISPOSITIONS)],
                         SOURCE_DISPOSITIONS)
        self.assertEqual(first.prior_abi_sha256, snapshot.prior_abi_sha256)

    def test_outer_binding_and_unpinned_ast_fail_closed(self):
        fixture = _typed_authority_fixture()
        abi = fixture[2]
        with _replayed(fixture):
            with self.assertRaises(BilqisError) as caught:
                _audit(fixture, abi=replace(abi, semantic_release="9" * 64))
        self.assertEqual(caught.exception.context["reason"],
                         "A12_AUTHORITY_SOURCE_BINDING_MISMATCH")
        with _replayed(fixture, ast_pins=False):
            with self.assertRaises(BilqisError) as caught:
                _audit(fixture)
        self.assertEqual(caught.exception.context["reason"],
                         "A12_AUTHORITY_AST_SOURCE_PIN_MISMATCH")

    def test_replay_rejects_self_consistent_caller_tampering(self):
        fixture = _typed_authority_fixture()
        abi, lessons, mirror = fixture[2], fixture[4], fixture[5]
        cases = (
            ("abi-allocation", dict(abi=replace(abi, source_allocation_digest="9" * 64)),
             "A12_AUTHORITY_ABI_SOURCE_MISMATCH"),
            ("abi-features", dict(abi=replace(abi, prospective_feature_digest="8" * 64)),
             "A12_AUTHORITY_ABI_SOURCE_MISMATCH"),
            ("mirror-row", dict(mirror=replace(
                mirror, rows=(replace(mirror.rows[0], source_record_digest="6" * 64),))),
             "A12_AUTHORITY_REGISTRY_MIRROR_MISMATCH"),
            ("lesson-census", dict(lessons=replace(lessons, census_digest="4" * 64)),
             "A12_AUTHORITY_LESSON_SOURCE_MISMATCH"),
        )
        for name, kwargs, reason in cases:
            with self.subTest(name=name), _replayed(fixture):
                with self.assertRaises(BilqisError) as caught:
                    _audit(fixture, **kwargs)
                self.assertEqual(caught.exception.context["reason"], reason)

    def test_stale_shadow_catalog_cannot_change_current_semantics(self):
        fixture = _typed_authority_fixture()
        with _replayed(fixture), patch(
                "bilqis_mlx.semantics.foundation.catalog.load_catalog",
                side_effect=AssertionError("historical catalog consulted by current A12 path")):
            baseline = _audit(fixture)
            replay = _audit(fixture)
        self.assertEqual(replay, baseline)


if __name__ == "__main__":
    unittest.main()
