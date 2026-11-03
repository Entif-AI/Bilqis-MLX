"""Published released-schema record identities survive structural extraction."""
import pickle
from typing import get_type_hints
import unittest

from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.released_frame_schemas import ReleasedFrameSchemaManifest
from bilqis_mlx.semantics.tests.released_schemas.fixtures import _release


class ReleasedRecordIdentityTests(unittest.TestCase):
    def test_public_records_keep_pickle_and_runtime_annotation_contracts(self):
        schema, _, _, _, verified = _release()
        records = (
            (verified.manifest.bodies[0], "canonical_body_json", str),
            (verified.manifest, "schema_map", SchemaTagMap),
            (verified.lookup(schema.schema_id, schema.revision), "revision", int),
            (verified, "manifest", ReleasedFrameSchemaManifest),
        )
        for value, field, expected_type in records:
            with self.subTest(record=type(value).__name__):
                self.assertEqual(type(value).__module__,
                                 "bilqis_mlx.semantics.released_frame_schemas")
                self.assertIs(get_type_hints(type(value))[field], expected_type)
                self.assertEqual(pickle.loads(pickle.dumps(value)), value)
