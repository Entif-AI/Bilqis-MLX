"""Canonical released-schema JSON boundary errors."""
from unittest import TestCase

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.released_frame_schemas import _json


class JsonContractTests(TestCase):
    def test_duplicate_object_keys_fail_with_exact_typed_reason(self):
        with self.assertRaises(BilqisError) as caught:
            _json(b'{"schema":1,"schema":2}')
        self.assertEqual(
            caught.exception.context["reason"],
            "FRAME_RELEASED_SCHEMA_JSON_DUPLICATE_KEY")

    def test_non_object_json_fails_with_exact_typed_reason(self):
        with self.assertRaises(BilqisError) as caught:
            _json(b'[]')
        self.assertEqual(
            caught.exception.context["reason"],
            "FRAME_RELEASED_SCHEMA_JSON_INVALID")
