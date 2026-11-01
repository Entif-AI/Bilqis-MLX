"""Retention integration contracts; original evidence and boundaries preserved."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bilqis_mlx import trainer as trainer
from bilqis_mlx.learning.mentor_epoch import begin_epoch, qualify_candidate, active_adviser_checkpoints
from tests.integration.retention.fixtures import _exam, _pointer


class MentorEpochTests(unittest.TestCase):
    def setUp(self):
        self.graduated = _pointer("a")
        self.extended_baseline = _pointer("b")
        self.prior_scores = {"A.ONE": {"correct": 12, "total": 12},
                             "B.XOR": {"correct": 12, "total": 12}}
        self.epoch = begin_epoch(
            previous_graduate=self.graduated,
            admitted_baseline=self.extended_baseline,
            introduced_grade="C", source_graph_sha256="d" * 64,
            previous_capabilities=tuple(self.prior_scores),
            previous_graduation_exam={
                "checkpoint_sha256": self.graduated["sha256"],
                "rubric_sha256": "b" * 64, "cohort_sha256": "a" * 64,
                "scores": self.prior_scores})

    def test_epoch_archives_history_without_historical_adviser_votes(self):
        self.assertEqual(self.epoch["previous_graduate"], self.graduated)
        self.assertEqual(self.epoch["baseline"], self.extended_baseline)
        self.assertEqual(active_adviser_checkpoints(self.epoch), ())
        self.assertEqual(self.epoch["qualified"], [])

    def test_epoch_does_not_start_from_separately_mastered_grade_best_scores(self):
        imperfect = {**self.prior_scores, "B.XOR": {"correct": 11, "total": 12}}
        with self.assertRaisesRegex(ValueError, "COMPLETE_PREVIOUS_GRADUATION"):
            begin_epoch(previous_graduate=self.graduated,
                        admitted_baseline=self.extended_baseline,
                        introduced_grade="C", source_graph_sha256="d" * 64,
                        previous_capabilities=tuple(self.prior_scores),
                        previous_graduation_exam={
                            "checkpoint_sha256": self.graduated["sha256"],
                            "rubric_sha256": "b" * 64,
                            "cohort_sha256": "a" * 64, "scores": imperfect})

    def test_new_adviser_must_gain_current_capability_without_large_mature_loss(self):
        candidate = _pointer("f")
        baseline = _exam(self.extended_baseline,
                         {"A.ONE": 12, "B.XOR": 12, "C.COUNT": 3})
        modest = _exam(candidate, {"A.ONE": 11, "B.XOR": 12, "C.COUNT": 6})
        trial = qualify_candidate(self.epoch, candidate, baseline, modest,
                                  mature_loss_budget=1)
        self.assertEqual(trial["decision"], "QUALIFIED")
        # Paired improvement is historical evidence, not a championship.
        self.assertEqual(active_adviser_checkpoints(trial["epoch"]), ())
        self.assertEqual(active_adviser_checkpoints(
            trial["epoch"], cohort_sha256="f" * 64),
            ())
        tied = qualify_candidate(trial["epoch"], _pointer("9"), baseline,
                                 _exam(_pointer("9"),
                                       {"A.ONE": 11, "B.XOR": 12, "C.COUNT": 6}),
                                 mature_loss_budget=1)
        self.assertEqual(tied["decision"], "HOLD_NO_BETTER_SAME_SCOPE_REFERENCE")
        harmful = _exam(candidate, {"A.ONE": 9, "B.XOR": 12, "C.COUNT": 10})
        rejected = qualify_candidate(self.epoch, candidate, baseline, harmful,
                                     mature_loss_budget=1)
        self.assertEqual(rejected["decision"], "HOLD_MATURE_LOSS")
        self.assertEqual(active_adviser_checkpoints(rejected["epoch"]), ())
        changed = _exam(candidate, {"A.ONE": 12, "B.XOR": 12, "C.COUNT": 3})
        no_gain = qualify_candidate(self.epoch, candidate, baseline, changed,
                                    mature_loss_budget=1)
        self.assertEqual(no_gain["decision"], "HOLD_NO_NEW_GRADE_GAIN")

    def test_cross_cohort_cannot_promote_adviser_and_never_changes_student(self):
        candidate = _pointer("f")
        old = _exam(self.extended_baseline,
                    {"A.ONE": 12, "B.XOR": 12, "C.COUNT": 3})
        new = _exam(candidate, {"A.ONE": 12, "B.XOR": 12, "C.COUNT": 8},
                    cohort="f" * 64)
        with self.assertRaisesRegex(ValueError, "MISMATCHED_EXAMINATION"):
            qualify_candidate(self.epoch, candidate, old, new,
                              mature_loss_budget=1)
        self.assertEqual(self.epoch["qualified"], [])

    def test_opted_in_epoch_uses_no_unearned_baseline_or_archived_soup_votes(self):
        graph = {"tokens": ["PAD", "A"], "nodes": [],
                 "row_contract_sha256": {}}
        identity = {"schema": "bilqis.mlx.championship-school-identity/v1",
                    "sha256": "9" * 64}
        epoch = {**self.epoch,
                 "source_graph_sha256": trainer._fingerprint(graph),
                 "championship_school_identity": identity}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            blob = root / "bundles" / "b" / "model-and-own-adamw.safetensors"
            blob.parent.mkdir(parents=True)
            blob.write_bytes(b"inert-mentor-test-blob")
            receipt = {"mentor_epoch": epoch,
                       "championship_school_identity": identity,
                       "grade_soups": {"B": {"vote_count": 6}}}
            with (patch('bilqis_mlx.learning.lesson_guidance._frozen_confidence_champions',
                               return_value=()) as fresh_champs,
                  patch('bilqis_mlx.learning.lesson_guidance._frozen_grade_soup_votes',
                               return_value=((), ())) as fresh_soups,
                  patch('bilqis_mlx.learning.lesson_guidance._cached_frozen_champion',
                               return_value=({"synthetic": "weights"}, graph))):
                champions, soups, receipts = trainer._mentor_sources_for_visit(
                    root, receipt, "C", graph, 3)
            fresh_champs.assert_not_called()
            fresh_soups.assert_not_called()
        self.assertEqual(soups, ())
        self.assertEqual(receipts, ())
        self.assertEqual(champions, ())

    def test_epoch_references_survive_checkpoint_retirement(self):
        record = {"generation": 4, "mentor_epoch": {**self.epoch,
                  "qualified": [{"checkpoint": _pointer("f")}]},
                  "school": {"active_grades": ["A", "B", "C"], "grade_index": 2,
                             "current_student": _pointer("c"), "champions": {}},
                  "capability_best": {}, "grade_soups": {}}
        with (patch('bilqis_mlx.runtime.checkpoints._boundary_delivery_events', return_value=()),
              patch('bilqis_mlx.runtime.checkpoints._quarantine_newer_uncommitted_bundles'),
              patch('bilqis_mlx.learning.capability_frontier.retire_bundles', return_value=()) as retire,
              patch('bilqis_mlx.learning.grade_soup.retire_stale_soups', return_value=()) as retire_soups):
            trainer._publish_boundary(Path("/not-created"), record, (), ())
        self.assertTrue({"bundles/a", "bundles/b", "bundles/f"} <=
                        retire.call_args.args[1])
        retire_soups.assert_called_once_with(
            Path("/not-created"), self.epoch["active_grade_soups"])

    def test_archived_epoch_soup_receipts_do_not_require_retired_tensor_bytes(self):
        archived_soup = {"grade": "A", "filename": "soups/archived.safetensors"}
        current_soup = {"grade": "B", "filename": "soups/current.safetensors"}
        receipt = {
            "grade_soups": {},
            "championship_epoch_history": [
                {**self.epoch, "active_grade_soups": {"A": archived_soup}}],
            "mentor_epoch": {**self.epoch, "active_grade_soups": {"B": current_soup}},
        }
        with patch('bilqis_mlx.learning.grade_soup.verify_frozen_soup') as verify:
            trainer._verify_frozen_soup_custody(Path("/run"), receipt)
        verify.assert_called_once_with(Path("/run"), current_soup)

    def test_current_epoch_soup_still_requires_its_tensor_bytes(self):
        current_soup = {"grade": "B", "filename": "soups/current.safetensors"}
        receipt = {"grade_soups": {},
                   "mentor_epoch": {**self.epoch,
                                    "active_grade_soups": {"B": current_soup}}}
        with (patch(
                "bilqis_mlx.learning.grade_soup.verify_frozen_soup",
                side_effect=ValueError("GRADE_SOUP_SAVED_ARTIFACT_MISSING")),
              self.assertRaisesRegex(ValueError, "GRADE_SOUP_SAVED_ARTIFACT_MISSING")):
            trainer._verify_frozen_soup_custody(Path("/run"), receipt)
