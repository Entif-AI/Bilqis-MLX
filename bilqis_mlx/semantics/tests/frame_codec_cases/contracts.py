from __future__ import annotations

import pickle

import bilqis_mlx.semantics.frame_codec as frame_codec
from bilqis_mlx.semantics.tests.frame_codec_cases.helpers import *  # noqa: F403


class ContractMixin:
    def test_public_facade_preserves_module_identity_and_pickle_path(self):
        public_objects = (
            frame_codec.FallbackReason,
            frame_codec.PackDisposition,
            frame_codec.CompactFrameBytes,
            frame_codec.SchemaTagEntry,
            frame_codec.SchemaTagMap,
            frame_codec.SlotTuple,
            frame_codec.ConstituentMetadata,
            frame_codec.ExtendedSlot,
            frame_codec.FrameSidecar,
            frame_codec.PackDecision,
            frame_codec.PackedFrame,
            frame_codec.pack4,
            frame_codec.unpack4,
            frame_codec.serialize_u64,
            frame_codec.deserialize_u64,
            frame_codec.classify_frame,
            frame_codec.pack_frame,
            frame_codec.role_index,
            frame_codec.unpack_frame,
        )
        self.assertEqual(
            frame_codec.__doc__,
            "Reversible compact and extended encodings for released semantic frames.",
        )
        self.assertTrue(all(
            item.__module__ == "bilqis_mlx.semantics.frame_codec"
            for item in public_objects
        ))

        schema_map = SchemaTagMap.from_schemas(RELEASE, (_schema("A"),))
        payload = pickle.dumps(schema_map)
        self.assertIn(b"bilqis_mlx.semantics.frame_codec", payload)
        self.assertNotIn(b"frame_codec_parts", payload)
        self.assertEqual(pickle.loads(payload), schema_map)

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
