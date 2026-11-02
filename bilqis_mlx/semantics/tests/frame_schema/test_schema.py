"""Canonical source schema record identity."""
import pickle
from unittest import TestCase

from bilqis_mlx.semantics.frame_schema import FrameSchema
from bilqis_mlx.semantics.tests.frame_schema.fixtures import _transfer_schema


class SchemaIdentityTests(TestCase):
    def test_schema_roundtrip_keeps_public_type_identity_and_canonical_bytes(self):
        schema = _transfer_schema()
        restored = pickle.loads(pickle.dumps(schema))
        self.assertIs(type(restored), FrameSchema)
        self.assertEqual(FrameSchema.__module__, "bilqis_mlx.semantics.frame_schema")
        self.assertEqual(restored.identity, "formal.frame.TRANSFER@1")
        self.assertEqual(restored.canonical_bytes(), schema.canonical_bytes())
