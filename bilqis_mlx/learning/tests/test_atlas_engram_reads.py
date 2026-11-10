"""B08.2 literal motif-read reporting acceptance."""
import unittest

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_engram import (
    INITIAL_MOTIF_CAPACITY, MotifReadReport, motif_read_report,
)
from bilqis_mlx.learning.atlas_engram_reads import MotifReadResult

from .motif_reads.fixtures import _source, _base_parameters, _parameters, _read


class MotifReadReportTests(unittest.TestCase):
    def test_reports_hit_miss_counts_and_actual_page_rows(self):
        read = MotifReadResult(
            mx.zeros((1, 6, 768), dtype=mx.float32),
            (("EXACT", "STRUCTURAL", "MISS", "HELD",
              "FOREIGN_RELEASE", "QUARANTINED_NO_HIT"),),
            (0, INITIAL_MOTIF_CAPACITY + 2),
            (None,),
        )

        report = motif_read_report(1, read)

        self.assertEqual(report.site_index, 1)
        self.assertEqual(report.exact_count, 1)
        self.assertEqual(report.structural_count, 1)
        self.assertEqual(report.miss_count, 4)
        self.assertEqual(report.participating_rows, ((0, 0), (1, 2)))

    def test_report_rejects_unknown_read_site(self):
        read = MotifReadResult(
            mx.zeros((1, 1, 768), dtype=mx.float32),
            (("MISS",),), (), (None,),
        )
        with self.assertRaises(BilqisError):
            motif_read_report(2, read)
