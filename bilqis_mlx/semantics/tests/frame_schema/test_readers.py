"""Frame-schema readers witnesses."""
from __future__ import annotations

import json
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_schema import (
    RoleOccurrence, SourceSpan, frame_instance_from_bytes, make_frame_instance,
)
from bilqis_mlx.semantics.tests.frame_schema.fixtures import _concept, _transfer_schema


class FrameReadersTests(unittest.TestCase):
    def test_serialized_frame_rejects_forged_occurrence_content_and_prefix(self):
        schema = _transfer_schema()
        frame = make_frame_instance(
            schema,
            source_instance_id="boundary-1",
            structural_path=(2,),
            source_span=SourceSpan(10, 25),
            parent_occurrence_id=None,
            bindings=(
                RoleOccurrence("agent", 0, concept=_concept("alice", 10)),
                RoleOccurrence("recipient", 0, concept=_concept("bob", 11)),
                RoleOccurrence("theme", 0, concept=_concept("book", 12)),
            ),
            causal_prefix_end=25,
        )
        canonical = json.loads(frame.canonical_bytes())
        cases = (
            ("occurrence_id", "0" * 64, "FRAME_OCCURRENCE_ID_MISMATCH"),
            ("content_digest", "0" * 64, "FRAME_CONTENT_DIGEST_MISMATCH"),
            ("causal_prefix_end", 0, "FRAME_INSTANCE_INVALID"),
        )
        for field, value, reason in cases:
            with self.subTest(field=field):
                forged = {**canonical, field: value}
                payload = (json.dumps(
                    forged,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                ) + "\n").encode()
                with self.assertRaises(BilqisError) as caught:
                    frame_instance_from_bytes(payload)
                self.assertIn(reason, str(caught.exception.context.get("reason")))


    def test_canonical_frame_reader_rejects_permuted_role_bindings(self):
        schema = _transfer_schema()
        frame = make_frame_instance(
            schema,
            source_instance_id="ordered-source",
            structural_path=(),
            source_span=SourceSpan(0, 12),
            parent_occurrence_id=None,
            bindings=(
                RoleOccurrence("agent", 0, concept=_concept("alice", 10)),
                RoleOccurrence("recipient", 0, concept=_concept("bob", 11)),
                RoleOccurrence("theme", 0, concept=_concept("book", 12)),
            ),
            causal_prefix_end=12,
        )
        payload = json.loads(frame.canonical_bytes())
        payload["bindings"] = list(reversed(payload["bindings"]))
        permuted = (json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False) + "\n").encode()
        with self.assertRaises(BilqisError) as caught:
            frame_instance_from_bytes(permuted)
        self.assertEqual(
            caught.exception.context["reason"],
            "FRAME_BINDING_ORDER_NONCANONICAL",
        )
