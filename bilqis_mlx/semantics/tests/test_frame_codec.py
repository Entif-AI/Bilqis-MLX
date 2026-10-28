from __future__ import annotations

from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_codec import (
    COMPACT_CODEC_ID,
    CODEC_VERSION,
    PRESENCE_MASK,
    PRESENCE_SHIFT,
    SCHEMA_SHIFT,
    VERSION_SHIFT,
    CompactFrameBytes,
    SchemaTagMap,
    deserialize_u64,
    pack4,
    serialize_u64,
    unpack4,
)
from bilqis_mlx.semantics.frame_schema import FrameSchema, RoleSpec


RELEASE = "1" * 64


def _schema(name: str) -> FrameSchema:
    return FrameSchema(
        schema_id="frame:" + name,
        revision=1,
        ast_construct="source:" + name,
        roles=tuple(
            RoleSpec("slot" + str(index), ("Entity",), 1, 1)
            for index in range(4)
        ),
        order_mode="ORDERED",
        scope="fixture",
    )


class CompactFrameCodecTests(unittest.TestCase):
    def setUp(self):
        self.schemas = tuple(_schema(name) for name in ("A", "B", "C", "D"))
        self.schema_map = SchemaTagMap.from_schemas(RELEASE, self.schemas)

    def test_literal_bit_layout_and_roundtrip(self):
        schema_tag = self.schema_map.tag_for(_schema("D"))
        self.assertEqual(schema_tag, 3)
        word = pack4((0, 1, 8190, 8191), schema_tag)
        self.assertEqual(word, 1441151880624349184)
        self.assertEqual(hex(word), "0x13fffffff8002000")
        decoded = unpack4(word, self.schema_map)
        self.assertEqual(decoded.indices, (0, 1, 8190, 8191))
        self.assertEqual(decoded.schema_tag, 3)
        self.assertEqual(decoded.schema.schema_id, "frame:D")
        self.assertEqual(decoded.presence_mask, 15)
        self.assertEqual(decoded.codec_version, 1)

    def test_all_zero_indices_and_all_max_fields_match_literal_words(self):
        zero_word = pack4((0, 0, 0, 0), 0)
        max_word = pack4((8191, 8191, 8191, 8191), 15)
        self.assertEqual(zero_word, 1220475499017404416)
        self.assertEqual(max_word, 2305843009213693951)
        self.assertEqual(
            zero_word,
            (CODEC_VERSION << VERSION_SHIFT)
            | (PRESENCE_MASK << PRESENCE_SHIFT),
        )
        self.assertEqual(
            max_word,
            (CODEC_VERSION << VERSION_SHIFT)
            | (PRESENCE_MASK << PRESENCE_SHIFT)
            | (15 << SCHEMA_SHIFT)
            | ((1 << 52) - 1),
        )
        self.assertEqual(unpack4(zero_word, self.schema_map).indices, (0, 0, 0, 0))

    def test_zero_index_is_present_not_empty(self):
        word = pack4((0, 7, 8, 9), 0)
        decoded = unpack4(word, self.schema_map)
        self.assertEqual(decoded.indices[0], 0)
        self.assertEqual(decoded.presence_mask, 15)

    def test_range_version_presence_and_unknown_tag_fail_closed(self):
        bad_inputs = (
            ((-1, 0, 0, 0), 0, "FRAME_COMPACT_INDEX_OUT_OF_RANGE"),
            ((8192, 0, 0, 0), 0, "FRAME_COMPACT_INDEX_OUT_OF_RANGE"),
            ((0, 0, 0, 0), 16, "FRAME_COMPACT_SCHEMA_TAG_OUT_OF_RANGE"),
        )
        for indices, tag, reason in bad_inputs:
            with self.subTest(reason=reason), self.assertRaises(BilqisError) as caught:
                pack4(indices, tag)
            self.assertEqual(caught.exception.code, "SEMANTIC_FRAME.CODEC.INVALID")
            self.assertEqual(caught.exception.context["reason"], reason)

        valid = pack4((1, 2, 3, 4), 0)
        wrong_version = (valid & ~(((1 << 4) - 1) << VERSION_SHIFT)) | (2 << VERSION_SHIFT)
        wrong_presence = valid & ~(1 << PRESENCE_SHIFT)
        for word, reason in (
            (wrong_version, "FRAME_COMPACT_VERSION_MISMATCH"),
            (wrong_presence, "FRAME_COMPACT_PRESENCE_INVALID"),
        ):
            with self.subTest(reason=reason), self.assertRaises(BilqisError) as caught:
                unpack4(word, self.schema_map)
            self.assertEqual(caught.exception.context["reason"], reason)

        unknown_tag_word = pack4((1, 2, 3, 4), 7)
        with self.assertRaises(BilqisError) as caught:
            unpack4(unknown_tag_word, self.schema_map)
        self.assertEqual(caught.exception.context["reason"], "FRAME_SCHEMA_TAG_UNKNOWN")

    def test_schema_map_is_release_local_content_addressed_and_schema_exact(self):
        first = SchemaTagMap.from_schemas(RELEASE, self.schemas)
        second = SchemaTagMap.from_schemas(RELEASE, tuple(reversed(self.schemas)))
        foreign = SchemaTagMap.from_schemas("2" * 64, self.schemas)
        revised = replace(self.schemas[0], scope="changed")
        revised_map = SchemaTagMap.from_schemas(
            RELEASE, (revised, *self.schemas[1:]))

        self.assertEqual(first, second)
        self.assertEqual(first.digest, second.digest)
        self.assertNotEqual(first.digest, foreign.digest)
        self.assertNotEqual(first.digest, revised_map.digest)
        self.assertIsNone(first.tag_for(revised))

    def test_little_endian_eight_bytes_and_decimal_json_are_literal(self):
        word = pack4((0, 1, 8190, 8191), 3)
        encoded = serialize_u64(word)
        self.assertEqual(encoded.codec_id, COMPACT_CODEC_ID)
        self.assertEqual(encoded.payload.hex(), "002000f8ffffff13")
        self.assertEqual(encoded.word_decimal, "1441151880624349184")
        self.assertEqual(encoded.json_value(), {
            "codec_id": "bamf.frame-u64/v1",
            "word_decimal": "1441151880624349184",
            "little_endian_hex": "002000f8ffffff13",
        })
        self.assertEqual(deserialize_u64(encoded), word)

        with self.assertRaises(BilqisError):
            CompactFrameBytes(
                codec_id=COMPACT_CODEC_ID,
                payload=encoded.payload,
                word_decimal="0",
            )


if __name__ == "__main__":
    unittest.main()
