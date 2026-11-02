from __future__ import annotations

from bilqis_mlx.semantics.tests.frame_codec_cases.helpers import *  # noqa: F403


class ReadoutMixin:
    def test_role_index_is_codec_neutral_and_rejects_inactive_or_held_readout(self):
        schema = _schema("A")
        schema_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
        active_snapshot = _snapshot()
        compact = _frame(
            schema, tuple(_concept(index) for index in range(4)),
            source_instance_id="compact-active",
        )
        packed_compact = pack_frame(
            compact, schema=schema, schema_map=schema_map)
        self.assertEqual(
            role_index(
                packed_compact,
                "slot2",
                0,
                schema_map=schema_map,
                snapshot=active_snapshot,
            ),
            2,
        )

        five_schema = FrameSchema(
            "frame:FIVE",
            1,
            "source:FIVE",
            tuple(RoleSpec("slot" + str(i), ("Entity",), 1, 1)
                  for i in range(5)),
            "ORDERED",
            "fixture",
        )
        five_map = SchemaTagMap.from_schemas(RELEASE, (five_schema,))
        five = _frame(
            five_schema, tuple(_concept(index) for index in range(5)),
            source_instance_id="extended-active",
        )
        packed_extended = pack_frame(
            five, schema=five_schema, schema_map=five_map)
        self.assertEqual(
            role_index(
                packed_extended,
                "slot4",
                0,
                schema_map=five_map,
                snapshot=active_snapshot,
            ),
            4,
        )

        inactive = _frame(
            schema,
            (_concept(0), _concept(1), _concept(2), _concept(4)),
            source_instance_id="compact-inactive",
        )
        packed_inactive = pack_frame(
            inactive, schema=schema, schema_map=schema_map)
        self.assertEqual(packed_inactive.disposition, PackDisposition.COMPACT)
        with self.assertRaises(BilqisError) as caught:
            role_index(
                packed_inactive,
                "slot3",
                0,
                schema_map=schema_map,
                snapshot=_snapshot(inactive=(4,)),
            )
        self.assertEqual(caught.exception.context["reason"],
                         "FRAME_READOUT_INDEX_INACTIVE")

        held_id = "held:semantic"
        held = _frame(
            schema,
            (_concept(0), _concept(1), _concept(2),
             _concept(0, semantic_id=held_id)),
            source_instance_id="compact-held-alias",
        )
        packed_held = pack_frame(
            held, schema=schema, schema_map=schema_map)
        with self.assertRaises(BilqisError) as caught:
            role_index(
                packed_held,
                "slot3",
                0,
                schema_map=schema_map,
                snapshot=_snapshot(held_id=held_id),
            )
        self.assertEqual(caught.exception.context["reason"],
                         "FRAME_READOUT_SEMANTIC_HELD")

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
