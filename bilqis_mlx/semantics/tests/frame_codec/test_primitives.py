"""Literal canonical codec JSON wire contract."""
from __future__ import annotations

from unittest import TestCase

from bilqis_mlx.semantics.frame_codec import _canonical_bytes


class CodecPrimitiveTests(TestCase):
    def test_canonical_codec_bytes_keep_utf8_and_one_newline(self):
        self.assertEqual(_canonical_bytes({"term": "é"}), b'{"term":"\xc3\xa9"}\n')
