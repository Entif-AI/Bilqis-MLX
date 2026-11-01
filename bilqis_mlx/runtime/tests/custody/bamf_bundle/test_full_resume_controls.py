"""Bounded mutation controls for the opt-in cold-read proof harness."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bilqis_mlx.runtime.tests.custody.bamf_bundle import test_full_resume as harness


class FullResumeControlTests(unittest.TestCase):
    def check_mutation_is_detected(self, fault):
        state = {
            "parameter_count": 79_469_798, "parameter_tensor_count": 214,
            "serialized_tensor_count": 856, "teacher_next_seed": 42,
            "teacher_cursor": "lesson:7", "optimizer_step": 12,
            "backbone_output_finite": True,
            "status": "UNBOUND_NUMERICAL_CUSTODY_ONLY",
            "optimizer_hyperparameters": {"learning_rate": 0.001},
            "transition": {"invalidate_derived_caches": False},
        }

        def save(candidate, destination):
            destination.mkdir()
            (destination / "manifest.json").write_text("original")
            if fault == "save":
                state["optimizer_hyperparameters"]["learning_rate"] = 0.5
            return {"manifest_sha256": "a" * 64}

        def read(root, digest):
            if fault == "read_change":
                (root / "manifest.json").write_text("changed")
            elif fault == "read_add":
                (root / "unexpected.json").write_text("added")
            elif fault == "transition":
                state["transition"]["invalidate_derived_caches"] = True
            return state

        def child(*args, **kwargs):
            return SimpleNamespace(stdout=json.dumps(state))

        with patch.object(harness, "full_candidate", return_value=object()), \
                patch.object(harness, "observe_student", return_value=state), \
                patch.object(harness, "save_bamf_bundle", side_effect=save), \
                patch.object(harness, "observe_bundle", side_effect=read), \
                patch.object(harness.subprocess, "run", side_effect=child):
            proof = harness.FullResumeTests()
            with self.assertRaises(AssertionError):
                proof.test_complete_tree_and_numerical_output_match_clean_process()

    def test_saver_cannot_mutate_original_expected_state(self):
        self.check_mutation_is_detected("save")

    def test_first_read_cannot_change_or_add_bundle_files(self):
        for fault in ("read_change", "read_add"):
            with self.subTest(fault=fault):
                self.check_mutation_is_detected(fault)

    def test_loader_cannot_drift_cache_transition_metadata(self):
        self.check_mutation_is_detected("transition")
