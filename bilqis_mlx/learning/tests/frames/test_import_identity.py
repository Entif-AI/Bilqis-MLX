"""Physical learning compartments preserve one public module identity."""
import importlib
import pickle
import unittest

from bilqis_mlx.learning.frame_encoder import FrameEncoding
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_compiler import SourceAtom


class ImportIdentityTests(unittest.TestCase):
    def test_moved_modules_use_the_established_logical_name(self):
        for compartment, name in (
                ("atlas", "atlas_engram_parameters"),
                ("championship", "capability_frontier"),
                ("teacher", "teacher_votes"),
                ("core", "student_ops")):
            with self.subTest(module=name):
                canonical = importlib.import_module(
                    "bilqis_mlx.learning." + name)
                self.assertEqual(
                    canonical.__name__, "bilqis_mlx.learning." + name)
                with self.assertRaises(ImportError):
                    importlib.import_module(
                        "bilqis_mlx.learning." + compartment + "." + name)
                self.assertIs(canonical, importlib.import_module(
                    "bilqis_mlx.learning." + name))

    def test_split_records_keep_historical_pickle_class_identities(self):
        for record, module in (
                (FrameEncoding, "bilqis_mlx.learning.frame_encoder"),
                (SchemaTagMap, "bilqis_mlx.semantics.frame_codec"),
                (SourceAtom, "bilqis_mlx.semantics.frame_compiler")):
            with self.subTest(record=record):
                self.assertEqual(record.__module__, module)
                self.assertIs(pickle.loads(pickle.dumps(record)), record)
        atom = SourceAtom(0, "token", "source:atom:0")
        self.assertEqual(pickle.loads(pickle.dumps(atom)), atom)
