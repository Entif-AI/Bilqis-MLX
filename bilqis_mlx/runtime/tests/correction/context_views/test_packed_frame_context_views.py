"""Packed-frame physical identity versus scoped context-view custody."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.tests.frames.nested_fixtures import _case as _nested_case
from bilqis_mlx.runtime.atlas_artifact_owner import PackedFrameArtifactOwner
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
from bilqis_mlx.semantics.frame_compiler import _prefix_digest


class PackedFrameContextViewTests(unittest.TestCase):
    def test_rows_share_physical_identity_and_keep_scoped_time(self):
        _ast, _config, compiled, _vectors, _params = _nested_case()
        owner = compiled.packed_frame_artifact_owner
        first = owner.require_row(compiled.compiled.rows[0])
        second = owner.require_row(compiled.compiled.rows[1])
        shared = {node.artifact_id for node in first} & {
            node.artifact_id for node in second}

        self.assertEqual(len(shared), 1)
        shared_id = next(iter(shared))
        first_node = next(node for node in first if node.artifact_id == shared_id)
        second_node = next(node for node in second if node.artifact_id == shared_id)
        self.assertEqual(first_node.content_digest, second_node.content_digest)
        self.assertNotEqual(
            tuple(ref for ref in first_node.immediate_dependencies
                  if ref.kind is DependencyKind.TIME),
            tuple(ref for ref in second_node.immediate_dependencies
                  if ref.kind is DependencyKind.TIME),
        )
        self.assertEqual(len(owner.origin_context_keys), 2)
        self.assertNotIn(
            owner.origin_context_keys[0],
            {node.artifact_id for node in owner.physical_nodes},
        )

    def test_non_context_drift_still_fails_closed(self):
        _ast, _config, compiled, _vectors, _params = _nested_case()
        first, second = compiled.compiled.rows
        version = (
            first.policy_version[0], first.policy_version[1] + 1,
            first.policy_version[2], first.policy_version[3],
        )
        changed = replace(
            first,
            policy_version=version,
            cache_key=_prefix_digest(
                first.source_instance_id, first.semantic_release,
                first.visible_end, first.schema_map, first.context_digest,
                first.positions, first.scope, version),
        )
        rows = replace(compiled.compiled, rows=(changed, second))

        with self.assertRaises(BilqisError) as caught:
            PackedFrameArtifactOwner(rows)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_PACKED_FRAME_IDENTITY_DRIFT",
        )

    def test_changed_packed_content_still_fails_closed(self):
        _ast, _config, compiled, _vectors, _params = _nested_case()
        first, second = compiled.compiled.rows
        index = next(
            i for i, position in enumerate(first.positions)
            if position.packed is not None)
        position = first.positions[index]
        packed = position.packed
        slot = packed.extended_slots[0]
        changed_slot = replace(slot, semantic_ids=("formal:changed",))
        changed_packed = replace(
            packed, extended_slots=(changed_slot, *packed.extended_slots[1:]))
        changed_positions = (
            *first.positions[:index],
            replace(position, packed=changed_packed),
            *first.positions[index + 1:],
        )
        changed = replace(
            first,
            positions=changed_positions,
            cache_key=_prefix_digest(
                first.source_instance_id, first.semantic_release,
                first.visible_end, first.schema_map, first.context_digest,
                changed_positions, first.scope, first.policy_version),
        )
        rows = replace(
            compiled.compiled,
            rows=(changed, second),
            padded_positions=(
                changed_positions
                + compiled.compiled.padded_positions[0][len(changed_positions):],
                compiled.compiled.padded_positions[1],
            ),
        )

        with self.assertRaises(BilqisError) as caught:
            PackedFrameArtifactOwner(rows)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_PACKED_FRAME_IDENTITY_DRIFT",
        )


if __name__ == "__main__":
    unittest.main()
