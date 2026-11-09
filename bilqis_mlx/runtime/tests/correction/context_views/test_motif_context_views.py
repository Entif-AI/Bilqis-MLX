"""Motif/cache identity over stable origin-context contracts."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.tests.test_frame_encoder import FrameEncoderTests
from bilqis_mlx.learning.tests.frames.nested_fixtures import _case as _nested_case
from bilqis_mlx.runtime.atlas_artifact_owner import PackedFrameArtifactOwner
from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
    _new_execution_cache, bind_motif_artifact_owner,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
from bilqis_mlx.semantics.frame_compiler import _prefix_digest


class MotifContextViewTests(unittest.TestCase):
    def setUp(self):
        _ast, _config, nested, _vectors, _params = _nested_case()
        self.manifest = MotifManifest(nested.features.semantic_release)
        self.nested = replace(
            nested,
            extents=replace(
                nested.extents,
                motif_key_map_digest=self.manifest.digest,
            ),
        )
        self.cache = _new_execution_cache(
            run_id="test-c09-motif-context-views",
            generation=7,
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

    def test_identity_uses_stable_origin_keys_not_view_nodes(self):
        owner = bind_motif_artifact_owner(self.cache, self.nested)
        packed = self.nested.packed_frame_artifact_owner
        motif_times = {
            ref for ref in owner.current_node.immediate_dependencies
            if ref.kind is DependencyKind.TIME
            and ref.key.startswith("time:asof:context:")
        }

        self.assertEqual(
            motif_times, set(packed.current_context_dependencies))
        self.assertEqual(
            {node.artifact_id for node in owner.index.nodes
             if node.kind.value == "PACKED_FRAME"},
            {node.artifact_id for node in packed.physical_nodes},
        )
        self.assertTrue(
            set(packed.origin_context_keys).isdisjoint(
                {node.artifact_id for node in owner.index.nodes}))

    def test_cache_keeps_distinct_origin_sets_and_reuses_first(self):
        first_owner = bind_motif_artifact_owner(self.cache, self.nested)
        rows = self.nested.compiled
        first, second = rows.rows
        changed_digest = "f" * 64
        changed_first = replace(
            first,
            context_digest=changed_digest,
            cache_key=_prefix_digest(
                first.source_instance_id, first.semantic_release,
                first.visible_end, first.schema_map, changed_digest,
                first.positions, first.scope, first.policy_version),
        )
        changed_rows = replace(rows, rows=(changed_first, second))
        changed_packed_owner = PackedFrameArtifactOwner(changed_rows)
        changed = replace(self.nested)
        object.__setattr__(
            changed, "packed_frame_artifact_owner", changed_packed_owner)

        second_owner = bind_motif_artifact_owner(self.cache, changed)

        self.assertIsNot(first_owner, second_owner)
        self.assertNotEqual(
            first_owner.current_node.artifact_id,
            second_owner.current_node.artifact_id,
        )
        self.assertIs(
            first_owner, bind_motif_artifact_owner(self.cache, self.nested))

    def test_live_single_context_owner_is_replaced_on_non_context_drift(self):
        fixture = FrameEncoderTests()
        fixture.setUp()
        compiled, _vectors, _ast = fixture.compiled_inputs()
        compiled = replace(
            compiled,
            extents=replace(
                compiled.extents,
                motif_key_map_digest=self.manifest.digest,
            ),
        )
        first_owner = bind_motif_artifact_owner(self.cache, compiled)
        row = compiled.compiled.rows[0]
        version = (
            row.policy_version[0], row.policy_version[1] + 1,
            row.policy_version[2], row.policy_version[3],
        )
        changed_row = replace(
            row,
            policy_version=version,
            cache_key=_prefix_digest(
                row.source_instance_id, row.semantic_release,
                row.visible_end, row.schema_map, row.context_digest,
                row.positions, row.scope, version),
        )
        changed_rows = replace(compiled.compiled, rows=(changed_row,))
        changed = replace(compiled)
        object.__setattr__(
            changed, "packed_frame_artifact_owner",
            PackedFrameArtifactOwner(changed_rows),
        )

        second_owner = bind_motif_artifact_owner(self.cache, changed)

        self.assertIsNot(first_owner, second_owner)
        self.assertIs(
            second_owner, bind_motif_artifact_owner(self.cache, changed))


if __name__ == "__main__":
    unittest.main()
