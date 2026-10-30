"""Persisted motif-read record identities survive physical extraction."""
import pickle
import unittest

from bilqis_mlx.learning.atlas_engram_reads import (
    MotifReadPosition, MotifReadResult,
)


class ReadRecordTests(unittest.TestCase):
    def test_public_records_keep_original_pickle_module(self):
        for record in (MotifReadPosition, MotifReadResult):
            with self.subTest(record=record):
                self.assertEqual(
                    record.__module__, "bilqis_mlx.learning.atlas_engram_reads")
                self.assertIs(pickle.loads(pickle.dumps(record)), record)
