"""Evidence projection behavior from the original School50 suite."""
import io
from pathlib import Path
import tempfile
import unittest
from bilqis_mlx.presentation.dashboard import build, ingest
from bilqis_mlx.presentation.tests.school50.fixtures import exam


class EvidenceTests(unittest.TestCase):
    def test_future_constructed_family_probes_have_lineage_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_FAMILY_PROBE_COMMITTED", "grade": "B",
                           "generation": 51, "family": "B.CASE.CONTRAST",
                           "before": {"correct": 3, "total": 10},
                           "after": {"correct": 8, "total": 10},
                           "partition": "independent_validation", "dataset_sha256": "a" * 64,
                           "student_sha256": "b" * 64, "optimizer_step": 132000})
            family = board._section_rows("BRIDGE FAMILIES")[-1]
            self.assertEqual(family["family"], "B.CASE.CONTRAST")
            self.assertEqual(family["before"], "3/10")
            self.assertEqual(family["after"], "8/10")
            self.assertEqual(family["gain"], "+5")
            self.assertFalse(any(row.get("mastered", False)
                                 for row in board.rows["GRADES & MASTERY"]))
            with self.assertRaisesRegex(ValueError, "SOURCE_PROVENANCE_REQUIRED"):
                ingest(board, {"event": "SCHOOL_FAMILY_PROBE_COMMITTED", "grade": "B",
                               "family": "B.CASE.CONTRAST", "before": {"correct": 3, "total": 10},
                               "after": {"correct": 10, "total": 10}})

    def test_generalization_gap_is_observational_not_an_optimizer_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_VISIT_COMMITTED", "grade": "B",
                           "capability": "B.RULE", "generation": 1,
                           "optimizer_step": 150000,
                           "source_training_accuracy_before": 1.,
                           "source_training_accuracy_after": 1.,
                           "teacher_reward": 0., "teacher_policy": "existing"})
            ingest(board, exam("B", 2, "rubric-b", {"B.RULE": (6, 12)},
                               step=150000))
            self.assertTrue(any("GENERALIZATION GAP" in line
                                for line in board.operator_lines))
            self.assertTrue(any("recent source-train" in line.lower()
                                for line in board.operator_lines))
            self.assertEqual(board.rows["GRADES & MASTERY"][-1]["to100"], "6")
