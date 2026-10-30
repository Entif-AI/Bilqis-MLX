"""Observation policy receipts keep source owners readable after relocation."""
from types import SimpleNamespace
import unittest

from bilqis_mlx.runtime.teacher_observation_capture import policy_epoch


class ObservationSourcePathTests(unittest.TestCase):
    def test_actual_policy_epoch_reads_all_source_owners(self):
        epoch = policy_epoch(
            {}, SimpleNamespace(release_sha256="a" * 64),
            configured_steps=2, batch_size=1, settings=None, enrichment=False)
        self.assertEqual(set(epoch["implementation"]), {
            "runtime/visits.py", "runtime/source_prefetch.py",
            "runtime/teacher_observation_capture.py",
            "learning/teacher_observations.py", "learning/learning_experiment.py",
            "learning/teacher_feedback.py", "learning/source_selection.py",
            "learning/lesson_guidance.py", "runtime/candidate_evidence.py",
            "runtime/state.py", "profiles/retention.py",
            "compatibility/historical_teacher_policy.py",
        })
        for name, digest in epoch["implementation"].items():
            with self.subTest(owner=name):
                self.assertRegex(digest, r"^[0-9a-f]{64}$")
