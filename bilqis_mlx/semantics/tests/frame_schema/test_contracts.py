"""Frame and legacy source digests retain distinct wire recipes."""
from hashlib import sha256
from unittest import TestCase

from bilqis_mlx.semantics.frame_schema import _bytes, source_node_digest


class DigestContractTests(TestCase):
    def test_frame_wire_uses_utf8_and_one_trailing_newline(self):
        self.assertEqual(_bytes({"term": "é"}), b'{"term":"\xc3\xa9"}\n')

    def test_legacy_source_wire_keeps_ascii_escapes_without_newline(self):
        self.assertEqual(
            source_node_digest({"term": "é"}),
            sha256(b'{"term":"\\u00e9"}').hexdigest())
