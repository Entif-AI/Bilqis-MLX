from __future__ import annotations

from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_codec import (
    ATOMIC_CODEC_ID,
    COMPACT_CODEC_ID,
    CODEC_VERSION,
    EXTENDED_CODEC_ID,
    FallbackReason,
    PackDisposition,
    PRESENCE_MASK,
    PRESENCE_SHIFT,
    SCHEMA_SHIFT,
    VERSION_SHIFT,
    CompactFrameBytes,
    SchemaTagMap,
    classify_frame,
    deserialize_u64,
    pack4,
    pack_frame,
    role_index,
    serialize_u64,
    unpack_frame,
    unpack4,
)
from bilqis_mlx.semantics.atlas_projection import (
    AbiEntry,
    AtlasCounts,
    CorpusCoverageRow,
    FrozenAtlasSnapshot,
)
from bilqis_mlx.semantics.frame_schema import (
    AtomicFrame,
    BindingState,
    ChildFrameRef,
    ConceptRef,
    FrameSchema,
    RoleOccurrence,
    RoleSpec,
    SourceSpan,
    atomic_fallback,
    make_frame_instance,
)


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


def _concept(index: int, *, semantic_id: str | None = None) -> ConceptRef:
    return ConceptRef(
        semantic_id=semantic_id or "formal:entity." + str(index),
        semantic_release=RELEASE,
        abi_index=index,
        type_ids=("Entity",),
        source_reference="fixture:" + str(index),
    )


def _frame(
    schema: FrameSchema,
    concepts: tuple[ConceptRef, ...],
    *,
    source_instance_id: str = "frame-1",
) -> object:
    return make_frame_instance(
        schema,
        source_instance_id=source_instance_id,
        structural_path=(),
        source_span=SourceSpan(0, 8),
        parent_occurrence_id=None,
        bindings=tuple(
            RoleOccurrence(role.role_id, 0, concept=concept)
            for role, concept in zip(schema.roles, concepts)
        ),
        causal_prefix_end=8,
    )


def _snapshot(*, inactive: tuple[int, ...] = (), held_id: str | None = None):
    entries = tuple(AbiEntry(
        index=index,
        bank=0,
        row=index,
        semantic_id="formal:entity." + str(index),
        symbol="fixture.entity." + str(index),
        source="FORMAL_DOMAIN",
        active=index not in inactive,
        teaching_candidate=index not in inactive,
        reason=("PRIOR_ACCEPTED_ABI" if index not in inactive
                else "IMPLEMENTATION_UNCOVERED"),
    ) for index in range(5))
    withheld = ()
    if held_id is not None:
        withheld = (CorpusCoverageRow(
            domain="mapping",
            table="fixture",
            key="held",
            semantic_id=held_id,
            source_disposition="SOURCE_HELD",
            implementation_status="NOT_APPLICABLE",
            teaching_candidate=False,
            reason_code="MAPPING_REVIEW_PENDING",
            teaching_reason="MAPPING_REVIEW_PENDING",
            owner="fixture",
        ),)
    return FrozenAtlasSnapshot(
        schema="bilqis.semantic-atlas-snapshot/v1",
        bundle_id="a" * 64,
        release_sha256=RELEASE,
        source_bundle_id="b" * 64,
        canonical_rdf_sha256="c" * 64,
        coverage_sha256="d" * 64,
        source_rows_sha256="e" * 64,
        conformance_sha256="f" * 64,
        prior_abi_sha256="0" * 64,
        shape_policy_sha256="1" * 64,
        active_set_sha256="2" * 64,
        counts=AtlasCounts(
            source_rows=1,
            rdf_terms=1,
            semantic_concepts=0,
            abi_entries=len(entries),
            abi_banks=1,
            active_abi_indices=sum(entry.active for entry in entries),
            trainable_capabilities=0,
            source_held=len(withheld),
            source_ir_only=0,
            implementation_uncovered=len(inactive),
        ),
        formal_domain_bindings=(),
        abi_entries=entries,
        concepts=(),
        relations=(),
        withheld_rows=withheld,
        semantic_lookup=tuple(sorted(
            (entry.semantic_id, entry.index) for entry in entries)),
        concept_lookup=(),
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

    def test_partial_and_atomic_fallback_are_typed_not_exception_driven(self):
        schema = _schema("A")
        schema_map = SchemaTagMap.from_schemas(RELEASE, (schema,))
        partial = make_frame_instance(
            schema,
            source_instance_id="partial",
            structural_path=(),
            source_span=SourceSpan(0, 8),
            parent_occurrence_id=None,
            bindings=(
                RoleOccurrence("slot0", 0, concept=_concept(0)),
                RoleOccurrence("slot1", 0, concept=_concept(1)),
                RoleOccurrence("slot2", 0, state=BindingState.UNKNOWN),
                RoleOccurrence("slot3", 0, concept=_concept(3)),
            ),
            causal_prefix_end=8,
        )
        decision = classify_frame(partial, schema, schema_map)
        self.assertEqual(decision.disposition, PackDisposition.EXTENDED)
        self.assertEqual(decision.reason, FallbackReason.NON_VALUE_BINDING)
        self.assertEqual(decision.schema_tag, 0)
        packed_partial = pack_frame(
            partial, schema=schema, schema_map=schema_map)
        self.assertEqual(packed_partial.disposition, PackDisposition.EXTENDED)
        self.assertEqual(packed_partial.extended_slots[2].state, "UNKNOWN")

        atomic = atomic_fallback(
            {"kind": "unknown", "payload": [1, 2, 3]},
            source_instance_id="atomic",
            structural_path=(),
            source_span=SourceSpan(0, 4),
            parent_occurrence_id=None,
            causal_prefix_end=4,
        )
        atomic_decision = classify_frame(atomic, None, schema_map)
        self.assertEqual(atomic_decision.disposition, PackDisposition.ATOMIC)
        packed_atomic = pack_frame(
            atomic, schema=None, schema_map=schema_map)
        self.assertEqual(packed_atomic.codec_id, ATOMIC_CODEC_ID)
        self.assertEqual(
            unpack_frame(packed_atomic, schema_map=schema_map), atomic)

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


if __name__ == "__main__":
    unittest.main()
