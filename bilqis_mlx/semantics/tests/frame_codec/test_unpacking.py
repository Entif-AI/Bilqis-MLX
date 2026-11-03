"""Codec unpacking witnesses."""
from __future__ import annotations

from bilqis_mlx.semantics.frame_codec import (
    COMPACT_CODEC_ID, EXTENDED_CODEC_ID, FallbackReason, PackDisposition,
    SchemaTagMap, pack_frame, unpack_frame,
)
from bilqis_mlx.semantics.tests.frame_codec.fixtures import (
    RELEASE, _schema, _concept, _frame, CodecCase,
)


class CodecUnpackingTests(CodecCase):
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
