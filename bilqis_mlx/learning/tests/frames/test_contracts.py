"""Frame records retain their serialized import paths after extraction."""
import pickle
import unittest

from bilqis_mlx.learning.frame_encoder import (
    AtomicEncoderInput, AtomicFrameEmbedding, AtomicSourceHandle,
    CompiledEmbeddingVectors, CompiledEncoderInput, FrameEncoderInput,
    FrameEncoding, MemberEmbedding,
)


class ImportIdentityTests(unittest.TestCase):
    def test_public_records_keep_historical_pickle_identity(self):
        for record in (
            AtomicEncoderInput, AtomicFrameEmbedding, AtomicSourceHandle,
            CompiledEmbeddingVectors, CompiledEncoderInput, FrameEncoderInput,
            FrameEncoding, MemberEmbedding,
        ):
            with self.subTest(record=record):
                self.assertEqual(
                    record.__module__, "bilqis_mlx.learning.frame_encoder")
                self.assertIs(pickle.loads(pickle.dumps(record)), record)
