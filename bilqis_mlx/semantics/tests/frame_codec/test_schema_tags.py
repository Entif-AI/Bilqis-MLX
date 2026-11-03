"""Public schema map annotations remain runtime-resolvable."""
from __future__ import annotations

from typing import get_type_hints
from unittest import TestCase
from dataclasses import replace

from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.tests.frame_codec.fixtures import RELEASE, CodecCase


class SchemaTagIdentityTests(TestCase):
    def test_schema_map_factory_return_type_is_the_public_map_class(self):
        self.assertIs(
            get_type_hints(SchemaTagMap.from_schemas.__func__)["return"], SchemaTagMap)


class CodecSchemaTagsTests(CodecCase):
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
