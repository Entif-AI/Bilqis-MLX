"""Codec packing witnesses."""
from __future__ import annotations

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_codec import (
    PackDisposition, SchemaTagMap, pack_frame, unpack_frame,
)
from bilqis_mlx.semantics.tests.frame_codec.fixtures import (
    RELEASE, _schema, _concept, _frame, CodecCase,
)


class CodecPackingTests(CodecCase):
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
