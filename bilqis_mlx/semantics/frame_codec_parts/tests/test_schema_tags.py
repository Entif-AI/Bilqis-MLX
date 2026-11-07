import unittest
from typing import get_type_hints

from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_schema import FrameSchema


class SchemaTagMapAnnotationTests(unittest.TestCase):
    def test_from_schemas_public_annotations_resolve_to_canonical_types(self):
        hints = get_type_hints(SchemaTagMap.from_schemas.__func__)

        self.assertIs(hints["return"], SchemaTagMap)
        self.assertEqual(hints["schemas"], tuple[FrameSchema, ...])
