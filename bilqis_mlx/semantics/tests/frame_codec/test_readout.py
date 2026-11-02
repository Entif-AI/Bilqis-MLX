"""Codec-neutral readout and source-admission rejection witnesses."""
from __future__ import annotations

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_codec import (
    PackDisposition, SchemaTagMap, pack_frame, role_index,
)
from bilqis_mlx.semantics.frame_schema import FrameSchema, RoleSpec
from bilqis_mlx.semantics.tests.frame_codec_cases.helpers import (
    _snapshot_with_authoritative_types,
)
from bilqis_mlx.semantics.tests.frame_codec.fixtures import (
    RELEASE, _schema, _concept, _frame, _snapshot, CodecCase,
)


class CodecReadoutTests(CodecCase):
    def test_role_index_is_codec_neutral_for_compact_and_extended(self):
        schema = _schema("A")
        schema_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
        active_snapshot = _snapshot_with_authoritative_types()
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

    def test_role_index_rejects_inactive_or_held_readout(self):
        schema = _schema("A")
        schema_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
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
                snapshot=_snapshot_with_authoritative_types(inactive=(4,)),
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
