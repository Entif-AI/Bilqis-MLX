from __future__ import annotations

from bilqis_mlx.semantics.tests.frame_codec_cases.helpers import *  # noqa: F403


class FallbackMixin:
    def test_pack_frame_compact_and_extended_reconstruct_exactly(self):
        compact_schema = _schema("A")
        compact_map = SchemaTagMap.from_schemas(RELEASE, (compact_schema,))
        compact_frame = _frame(
            compact_schema, tuple(_concept(index) for index in range(4)))
        packed = pack_frame(
            compact_frame, schema=compact_schema, schema_map=compact_map)
        self.assertEqual(packed.disposition, PackDisposition.COMPACT)
        self.assertEqual(packed.reason, FallbackReason.COMPACT_ELIGIBLE)
        self.assertEqual(packed.codec_id, COMPACT_CODEC_ID)
        self.assertEqual(unpack_frame(packed, schema_map=compact_map), compact_frame)

        schemas = tuple(_schema(chr(ord("A") + index)) for index in range(16))
        full_map = SchemaTagMap.from_schemas(RELEASE, schemas)
        seventeenth = _schema("Q")
        seventeenth_frame = _frame(
            seventeenth, tuple(_concept(index) for index in range(4)))
        packed17 = pack_frame(
            seventeenth_frame, schema=seventeenth, schema_map=full_map)
        self.assertEqual(packed17.disposition, PackDisposition.EXTENDED)
        self.assertEqual(packed17.reason, FallbackReason.SCHEMA_TAG_UNAVAILABLE)
        self.assertEqual(packed17.codec_id, EXTENDED_CODEC_ID)
        self.assertEqual(
            unpack_frame(packed17, schema_map=full_map), seventeenth_frame)

    def test_index8192_five_slots_and_nested_child_choose_extended(self):
        schema = _schema("A")
        schema_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
        wide = _frame(
            schema,
            (_concept(0), _concept(1), _concept(2), _concept(8192)),
            source_instance_id="wide",
        )
        wide_packed = pack_frame(wide, schema=schema, schema_map=schema_map)
        self.assertEqual(wide_packed.disposition, PackDisposition.EXTENDED)
        self.assertEqual(
            wide_packed.reason, FallbackReason.INDEX_REQUIRES_UINT32)
        self.assertEqual(
            wide_packed.extended_slots[3].abi_indices, (8192,))
        self.assertEqual(unpack_frame(wide_packed, schema_map=schema_map), wide)

        five_schema = FrameSchema(
            schema_id="frame:FIVE",
            revision=1,
            ast_construct="source:FIVE",
            roles=tuple(
                RoleSpec("slot" + str(index), ("Entity",), 1, 1)
                for index in range(5)
            ),
            order_mode="ORDERED",
            scope="fixture",
        )
        five_map = SchemaTagMap.from_schemas(RELEASE, (five_schema,))
        five = _frame(
            five_schema, tuple(_concept(index) for index in range(5)),
            source_instance_id="five",
        )
        five_packed = pack_frame(five, schema=five_schema, schema_map=five_map)
        self.assertEqual(five_packed.disposition, PackDisposition.EXTENDED)
        self.assertEqual(
            five_packed.reason, FallbackReason.SCHEMA_NOT_FOUR_SINGULAR_ROLES)
        self.assertEqual(len(five_packed.extended_slots), 5)
        self.assertEqual(unpack_frame(five_packed, schema_map=five_map), five)

        child = _frame(
            schema, tuple(_concept(index) for index in range(4)),
            source_instance_id="child",
        )
        nested = make_frame_instance(
            schema,
            source_instance_id="nested",
            structural_path=(),
            source_span=SourceSpan(0, 8),
            parent_occurrence_id=None,
            bindings=(
                RoleOccurrence(
                    "slot0",
                    0,
                    child_frame=ChildFrameRef(
                        child.occurrence_id,
                        child.content_digest,
                        ("Entity",),
                    ),
                ),
                RoleOccurrence("slot1", 0, concept=_concept(1)),
                RoleOccurrence("slot2", 0, concept=_concept(2)),
                RoleOccurrence("slot3", 0, concept=_concept(3)),
            ),
            causal_prefix_end=8,
        )
        nested_packed = pack_frame(
            nested, schema=schema, schema_map=schema_map)
        self.assertEqual(nested_packed.disposition, PackDisposition.EXTENDED)
        self.assertEqual(nested_packed.reason, FallbackReason.CHILD_FRAME)
        self.assertEqual(
            nested_packed.extended_slots[0].child_occurrence_id,
            child.occurrence_id,
        )
        self.assertEqual(
            unpack_frame(nested_packed, schema_map=schema_map), nested)

    def test_partial_and_atomic_fallback_are_typed_not_exception_driven(self):
        schema = _schema("A")
        schema_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
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
        decision = classify_frame(partial, schema, schema_map)
        self.assertEqual(decision.disposition, PackDisposition.EXTENDED)
        self.assertEqual(decision.reason, FallbackReason.NON_VALUE_BINDING)
        self.assertEqual(decision.schema_tag, 0)
        packed_partial = pack_frame(
            partial, schema=schema, schema_map=schema_map)
        self.assertEqual(packed_partial.disposition, PackDisposition.EXTENDED)
        self.assertEqual(packed_partial.extended_slots[2].state, "UNKNOWN")

        atomic = atomic_fallback(
            {"kind": "unknown", "payload": [1, 2, 3]},
            source_instance_id="atomic",
            structural_path=(),
            source_span=SourceSpan(0, 4),
            parent_occurrence_id=None,
            causal_prefix_end=4,
        )
        atomic_decision = classify_frame(atomic, None, schema_map)
        self.assertEqual(atomic_decision.disposition, PackDisposition.ATOMIC)
        packed_atomic = pack_frame(
            atomic, schema=None, schema_map=schema_map)
        self.assertEqual(packed_atomic.codec_id, ATOMIC_CODEC_ID)
        self.assertEqual(
            unpack_frame(packed_atomic, schema_map=schema_map), atomic)
