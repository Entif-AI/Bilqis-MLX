"""Actual codec sidecars reject malformed source metadata."""
from __future__ import annotations

from dataclasses import replace
from unittest import TestCase

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_codec import SchemaTagMap, pack_frame
from bilqis_mlx.semantics.tests.frame_codec.fixtures import (
    RELEASE, _concept, _frame, _schema,
)


class CodecRecordTests(TestCase):
    def test_sidecar_rejects_invalid_codec_and_empty_source_identity(self):
        schema = _schema("A")
        packed = pack_frame(
            _frame(schema, tuple(_concept(index) for index in range(4))),
            schema=schema, schema_map=SchemaTagMap.from_schemas(RELEASE, (schema,)))
        for changes in ({"codec_id": "fixture:invalid"}, {"source_instance_id": ""}):
            with self.subTest(changes=changes):
                with self.assertRaises(BilqisError) as caught:
                    replace(packed.sidecar, **changes)
                self.assertEqual(caught.exception.code, "SEMANTIC_FRAME.CODEC.INVALID")
                self.assertEqual(
                    caught.exception.context["reason"], "FRAME_CODEC_SIDECAR_INVALID")
