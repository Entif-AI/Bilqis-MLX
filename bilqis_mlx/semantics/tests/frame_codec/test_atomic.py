"""Codec atomic witnesses."""
from __future__ import annotations

from bilqis_mlx.semantics.frame_codec import (
    ATOMIC_CODEC_ID, FallbackReason, PackDisposition, SchemaTagMap, classify_frame,
    pack_frame, unpack_frame,
)
from bilqis_mlx.semantics.frame_schema import (
    BindingState, RoleOccurrence, SourceSpan, atomic_fallback, make_frame_instance,
)
from bilqis_mlx.semantics.tests.frame_codec.fixtures import (
    RELEASE, _schema, _concept, CodecCase,
)


class CodecAtomicTests(CodecCase):
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
