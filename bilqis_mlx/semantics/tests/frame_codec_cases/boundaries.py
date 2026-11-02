from __future__ import annotations

from bilqis_mlx.semantics.tests.frame_codec_cases.helpers import *  # noqa: F403


class BoundaryMixin:
    def test_extended_uint32_upper_boundary_roundtrips_and_overflow_rejects(self):
        schema = _schema("A")
        schema_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
        valid = _frame(schema, (
            _concept(0), _concept(1), _concept(2), _concept((1 << 32) - 1)))
        packed = pack_frame(valid, schema=schema, schema_map=schema_map)
        self.assertEqual(packed.disposition, PackDisposition.EXTENDED)
        self.assertEqual(packed.extended_slots[3].abi_indices, ((1 << 32) - 1,))
        self.assertEqual(unpack_frame(packed, schema_map=schema_map), valid)

        overflow = _frame(schema, (
            _concept(0), _concept(1), _concept(2), _concept(1 << 32)))
        with self.assertRaises(BilqisError) as caught:
            pack_frame(overflow, schema=schema, schema_map=schema_map)
        self.assertEqual(caught.exception.code, "SEMANTIC_FRAME.CODEC.INVALID")
        self.assertEqual(
            caught.exception.context["reason"], "FRAME_EXTENDED_SLOT_INVALID")

    def test_constituent_sidecar_preserves_order_source_and_occurrence(self):
        schema = _schema("A")
        schema_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
        concepts = tuple(_concept(index) for index in range(4))
        first = _frame(schema, concepts, source_instance_id="first")
        second = _frame(schema, concepts, source_instance_id="second")
        first_packed = pack_frame(first, schema=schema, schema_map=schema_map)
        second_packed = pack_frame(second, schema=schema, schema_map=schema_map)
        self.assertEqual(first.content_digest, second.content_digest)
        self.assertNotEqual(first.occurrence_id, second.occurrence_id)
        self.assertNotEqual(
            first_packed.projection_sha256, second_packed.projection_sha256)
        self.assertEqual(
            tuple(member.role_id for member in first_packed.sidecar.constituents),
            ("slot0", "slot1", "slot2", "slot3"),
        )
        self.assertEqual(
            first_packed.sidecar.constituents[0].abi_indices, (0,))
        self.assertEqual(
            first_packed.sidecar.constituents[0].source_references, ("fixture:0",))
        self.assertEqual(
            unpack_frame(first_packed, schema_map=schema_map), first)

        partial = make_frame_instance(
            schema,
            source_instance_id="partial",
            structural_path=(),
            source_span=SourceSpan(0, 8),
            parent_occurrence_id=None,
            bindings=(
                RoleOccurrence("slot0", 0, concept=_concept(0)),
                RoleOccurrence("slot1", 0, concept=_concept(1)),
                RoleOccurrence("slot2", 0, state=BindingState.UNKNOWN),
                RoleOccurrence("slot3", 0, concept=_concept(3)),
            ),
            causal_prefix_end=8,
        )
        partial_packed = pack_frame(
            partial, schema=schema, schema_map=schema_map)
        self.assertEqual(partial_packed.sidecar.constituents[0].abi_indices, (0,))
        self.assertEqual(partial_packed.sidecar.constituents[2].abi_indices, ())
        self.assertEqual(partial_packed.sidecar.constituents[2].state, "UNKNOWN")
        self.assertEqual(
            unpack_frame(partial_packed, schema_map=schema_map), partial)
