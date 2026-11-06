from __future__ import annotations

import unittest

from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.tests.frame_codec_cases.boundaries import BoundaryMixin
from bilqis_mlx.semantics.tests.frame_codec_cases.contracts import ContractMixin
from bilqis_mlx.semantics.tests.frame_codec_cases.fallback import FallbackMixin
from bilqis_mlx.semantics.tests.frame_codec_cases.helpers import RELEASE, _schema
from bilqis_mlx.semantics.tests.frame_codec_cases.readout import ReadoutMixin


class CompactFrameCodecTests(
    ContractMixin, FallbackMixin, ReadoutMixin, BoundaryMixin, unittest.TestCase
):
    def setUp(self):
        self.schemas = tuple(_schema(name) for name in ("A", "B", "C", "D"))
        self.schema_map = SchemaTagMap.from_schemas(RELEASE, self.schemas)


if __name__ == "__main__":
    unittest.main()
