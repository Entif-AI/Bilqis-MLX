"""Canonical identities for packed codec records and enums."""
from __future__ import annotations

import pickle
from unittest import TestCase

from bilqis_mlx.semantics import frame_codec
from bilqis_mlx.semantics.tests.frame_codec.fixtures import (
    RELEASE, _concept, _frame, _schema,
)


class PackedIdentityTests(TestCase):
    def test_all_codec_record_and_enum_types_keep_public_pickle_identity(self):
        schema = _schema("A")
        schema_map = frame_codec.SchemaTagMap.from_schemas(RELEASE, (schema,))
        frame = _frame(schema, tuple(_concept(index) for index in range(4)))
        packed = frame_codec.pack_frame(frame, schema=schema, schema_map=schema_map)
        extended = frame_codec.pack_frame(
            _frame(schema, tuple(_concept(index) for index in (0, 1, 2, 8192))),
            schema=schema, schema_map=schema_map)
        values = (
            frame_codec.PackDisposition.COMPACT,
            frame_codec.FallbackReason.COMPACT_ELIGIBLE,
            schema_map.entries[0], schema_map,
            frame_codec.unpack4(packed.compact_word, schema_map),
            frame_codec.serialize_u64(packed.compact_word),
            extended.extended_slots[0], packed.sidecar.constituents[0],
            packed.sidecar, frame_codec.classify_frame(frame, schema, schema_map), packed)
        self.assertEqual(len({type(value) for value in values}), 11)
        for value in values:
            with self.subTest(record=type(value).__name__):
                self.assertEqual(type(value).__module__, frame_codec.__name__)
                restored = pickle.loads(pickle.dumps(value))
                self.assertIs(type(restored), type(value))
                self.assertEqual(restored, value)
