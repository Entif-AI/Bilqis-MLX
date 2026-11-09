"""C09 motif custody on the actual compiled-frame/B13 cache boundary."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.frame_encoder import CompiledEncoderInput
from bilqis_mlx.learning.tests.test_frame_encoder import FrameEncoderTests
from bilqis_mlx.runtime.atlas_motif_owner import MotifArtifactOwner
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime._atlas_owner_ingress import apply_motif_correction
from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
    _new_execution_cache, bind_motif_artifact_owner,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    AUTHORITY, _SOURCE_OWNER, _TEST_PUBLIC, _event, _result,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind


class MotifArtifactOwnerTests(unittest.TestCase):
    def setUp(self):
        fixture = FrameEncoderTests()
        fixture.setUp()
        compiled, _vectors, _ast = fixture.compiled_inputs()
        self.manifest = MotifManifest(compiled.features.semantic_release)
        extents = replace(
            compiled.extents, motif_key_map_digest=self.manifest.digest)
        self.compiled = CompiledEncoderInput(
            compiled.compiled, compiled.compiler_configs,
            compiled.features, extents)
        self.cache = _new_execution_cache(
            run_id="test-c09-motif", generation=7,
            accepted_manifest_sha256="8" * 64,
            generation_binding="7" * 64,
            motif_manifest=self.manifest,
        )
        custody = patch(
            "bilqis_mlx.runtime.bamf_bundle.execution_cache.require_accepted_execution_cache",
            side_effect=lambda cache: cache,
        )
        custody.start()
        self.addCleanup(custody.stop)
        self.owner = bind_motif_artifact_owner(self.cache, self.compiled)

    def test_source_correction_holds_real_frame_before_motif_lookup(self):
        source = self.owner.source_dependencies[0]
        apply_motif_correction(
            self.cache, self.compiled, _event(source), AUTHORITY)
        queue = self.owner.queue
        self.assertTrue(queue.held_artifact_ids)
        with self.assertRaises(BilqisError) as caught:
            self.owner.require(self.cache, self.compiled)
        self.assertIn(caught.exception.context["reason"], (
            "BAMF_C09_ARTIFACT_HELD",
            "BAMF_C09_ARTIFACT_DEPENDENCY_HELD",
        ))

    def test_real_owner_nodes_supply_non_tie_revalidation_priority(self):
        motif = self.owner.current_node
        self.assertEqual((motif.impact, motif.exigency), (4, 4))
        frames = tuple(
            node for node in self.owner.index.nodes
            if node.kind.value == "PACKED_FRAME")
        self.assertTrue(frames)
        self.assertTrue(all(
            (node.impact, node.exigency) == (3, 3) for node in frames))

    def test_packed_frames_declare_frame_compiler_operator_dependency(self):
        frames = tuple(
            node for node in self.owner.index.nodes
            if node.kind.value == "PACKED_FRAME")
        self.assertTrue(frames)
        for node in frames:
            operator_refs = tuple(
                ref.key for ref in node.immediate_dependencies
                if ref.kind is DependencyKind.OPERATOR)
            self.assertEqual(
                operator_refs,
                ("operator:frame-compiler:bilqis.compiled-frame-batch/v2",),
            )

    def test_frame_compiler_correction_holds_packed_frame_before_motif_use(self):
        dependency = next(
            ref for node in self.owner.index.nodes
            if node.kind.value == "PACKED_FRAME"
            for ref in node.immediate_dependencies
            if ref.kind is DependencyKind.OPERATOR)
        authority = SourceAuthorityRegistry((SourceAuthorityKey(
            _SOURCE_OWNER,
            _TEST_PUBLIC,
            (SourceAuthorityScope(
                DependencyKind.OPERATOR, "operator:frame-compiler:"),),
        ),))
        apply_motif_correction(
            self.cache, self.compiled, _event(dependency), authority)
        with self.assertRaises(BilqisError) as caught:
            self.owner.require(self.cache, self.compiled)
        self.assertIn(caught.exception.context["reason"], (
            "BAMF_C09_ARTIFACT_HELD",
            "BAMF_C09_ARTIFACT_DEPENDENCY_HELD",
        ))

    def test_equal_input_revalidation_stops_before_motif(self):
        source = self.owner.source_dependencies[0]
        event = _event(source)
        apply_motif_correction(
            self.cache, self.compiled, event, AUTHORITY)
        queue = self.owner.queue
        held = self.owner.index.node(queue.held_artifact_ids[0])
        progress = self.owner.advance(
            _result(held, digest=held.content_digest, correction=event), AUTHORITY)
        self.assertEqual(progress.queue.pending, ())
        self.assertEqual(progress.queue.held_artifact_ids, ())
        self.assertIs(self.owner.require(self.cache, self.compiled), self.owner.current_node)

    def test_changed_input_propagates_hold_to_manifest(self):
        source = self.owner.source_dependencies[0]
        event = _event(source)
        apply_motif_correction(
            self.cache, self.compiled, event, AUTHORITY)
        queue = self.owner.queue
        held = self.owner.index.node(queue.held_artifact_ids[0])
        self.owner.advance(
            _result(held, digest="9" * 64, correction=event), AUTHORITY)
        self.assertIn(self.owner.current_node.artifact_id,
                      self.owner.queue.held_artifact_ids)
        with self.assertRaises(BilqisError):
            self.owner.require(self.cache, self.compiled)

    def test_cache_lifetime_reuses_one_owner(self):
        self.assertIs(
            self.owner,
            bind_motif_artifact_owner(self.cache, self.compiled),
        )

    def test_cache_lifetime_keeps_distinct_batch_scoped_motif_owners(self):
        fixture = FrameEncoderTests()
        fixture.setUp()
        second, _vectors, _ast = fixture.compiled_inputs(prefix=7)
        second = replace(
            second,
            extents=replace(
                second.extents,
                motif_key_map_digest=self.manifest.digest,
            ),
        )

        second_owner = bind_motif_artifact_owner(self.cache, second)

        self.assertIsNot(second_owner, self.owner)
        self.assertIs(second_owner, bind_motif_artifact_owner(self.cache, second))
        self.assertNotEqual(
            second_owner.current_node.artifact_id,
            self.owner.current_node.artifact_id,
        )
        self.assertEqual(
            second_owner.current_node.content_digest,
            self.owner.current_node.content_digest,
        )


if __name__ == "__main__":
    unittest.main()
