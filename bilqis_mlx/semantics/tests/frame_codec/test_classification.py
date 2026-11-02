"""Codec classification witnesses."""
from __future__ import annotations

from dataclasses import replace

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_codec import (
    FallbackReason, PackDisposition, SchemaTagMap, pack_frame, unpack_frame,
)
from bilqis_mlx.semantics.frame_schema import (
    ChildFrameRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan,
    make_frame_instance,
)
from bilqis_mlx.semantics.tests.frame_codec.fixtures import (
    RELEASE, _schema, _concept, _frame, CodecCase,
)


class CodecClassificationTests(CodecCase):
    def test_singular_schema_role_cannot_fall_back_to_extended_when_duplicated(self):
        schema = _schema("A")
        schema_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
        valid = _frame(schema, tuple(_concept(index) for index in range(4)))
        duplicate = make_frame_instance(
            schema,
            source_instance_id="duplicate-singular-role",
            structural_path=(),
            source_span=SourceSpan(0, 8),
            parent_occurrence_id=None,
            bindings=(
                valid.bindings[0],
                RoleOccurrence("slot0", 1, concept=_concept(4)),
                *valid.bindings[1:],
            ),
            causal_prefix_end=8,
        )
        with self.assertRaises(BilqisError) as caught:
            pack_frame(duplicate, schema=schema, schema_map=schema_map)
        self.assertEqual(
            caught.exception.context["reason"], "FRAME_ROLE_CARDINALITY_INVALID")


    def test_packed_frame_must_match_authoritative_schema_role_order(self):
        schema = _schema("A")
        schema_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
        forged_schema = replace(schema, roles=tuple(reversed(schema.roles)))
        forged_frame = _frame(
            forged_schema, tuple(_concept(index) for index in range(4)))
        with self.assertRaises(BilqisError) as caught:
            pack_frame(
                forged_frame, schema=schema, schema_map=schema_map)
        self.assertEqual(
            caught.exception.context["reason"],
            "FRAME_PACKED_FRAME_SCHEMA_ROLE_ORDER_MISMATCH")


    def test_role_type_mismatch_is_not_a_codec_fallback(self):
        schema = _schema("A")
        schema_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
        invalid = _frame(schema, (
            replace(_concept(0), type_ids=("Number",)),
            _concept(1), _concept(2), _concept(3),
        ))
        with self.assertRaises(BilqisError) as caught:
            pack_frame(invalid, schema=schema, schema_map=schema_map)
        self.assertEqual(
            caught.exception.context["reason"], "FRAME_ROLE_TYPE_INVALID")


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
