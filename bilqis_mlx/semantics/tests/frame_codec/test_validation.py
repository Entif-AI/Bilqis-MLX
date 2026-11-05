"""Codec validation witnesses."""
from __future__ import annotations

from dataclasses import replace
import hashlib

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_codec import SchemaTagMap, pack_frame, unpack_frame
from bilqis_mlx.semantics.tests.frame_codec.fixtures import (
    RELEASE, _schema, _concept, _frame, CodecCase,
)


class CodecValidationTests(CodecCase):
    def test_wrong_release_or_schema_map_refuses_sidecar_reinterpretation(self):
        schema = _schema("A")
        schema_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
        frame = _frame(
            schema, tuple(_concept(index) for index in range(4)))
        packed = pack_frame(frame, schema=schema, schema_map=schema_map)
        foreign_release = SchemaTagMap.from_schemas("2" * 64, (schema,))
        revised_schema = replace(schema, scope="foreign")
        revised_map = SchemaTagMap.from_schemas(RELEASE, (revised_schema,))
        for wrong_map, reason in (
            (foreign_release, "FRAME_PACKED_RELEASE_MISMATCH"),
            (revised_map, "FRAME_PACKED_SCHEMA_MAP_MISMATCH"),
        ):
            with self.subTest(reason=reason), self.assertRaises(BilqisError) as caught:
                unpack_frame(packed, schema_map=wrong_map)
            self.assertEqual(caught.exception.context["reason"], reason)


    def test_payload_and_sidecar_cannot_rebind_another_schema_or_release(self):
        schema = _schema("A")
        schema_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
        concepts = tuple(_concept(index) for index in range(4))
        packed = pack_frame(
            _frame(schema, concepts), schema=schema, schema_map=schema_map)

        foreign_schema_frame = _frame(_schema("B"), concepts)
        payload = foreign_schema_frame.canonical_bytes()
        forged_sidecar = replace(
            packed.sidecar,
            content_digest=foreign_schema_frame.content_digest,
            frame_payload_sha256=hashlib.sha256(payload).hexdigest(),
        )
        with self.assertRaises(BilqisError) as caught:
            unpack_frame(
                replace(packed, frame_payload=payload, sidecar=forged_sidecar),
                schema_map=schema_map,
            )
        self.assertEqual(caught.exception.code, "SEMANTIC_FRAME.CODEC.INVALID")
        self.assertEqual(
            caught.exception.context["reason"], "FRAME_PACKED_FRAME_SCHEMA_MISMATCH")

        foreign_release = "2" * 64
        foreign_concepts = tuple(
            replace(concept, semantic_release=foreign_release)
            for concept in concepts
        )
        foreign_frame = _frame(schema, foreign_concepts)
        payload = foreign_frame.canonical_bytes()
        forged_sidecar = replace(
            packed.sidecar,
            content_digest=foreign_frame.content_digest,
            frame_payload_sha256=hashlib.sha256(payload).hexdigest(),
            constituents=tuple(
                replace(member, semantic_releases=(foreign_release,))
                for member in packed.sidecar.constituents
            ),
        )
        with self.assertRaises(BilqisError) as caught:
            unpack_frame(
                replace(packed, frame_payload=payload, sidecar=forged_sidecar),
                schema_map=schema_map,
            )
        self.assertEqual(caught.exception.code, "SEMANTIC_FRAME.CODEC.INVALID")
        self.assertEqual(
            caught.exception.context["reason"], "FRAME_PACKED_FRAME_RELEASE_MISMATCH")
