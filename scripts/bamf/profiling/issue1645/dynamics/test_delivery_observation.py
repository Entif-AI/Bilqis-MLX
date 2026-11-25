"""Delivered rows and actual supervision, not a selected distill policy."""
from types import SimpleNamespace
import unittest

from bilqis_mlx.runtime.atlas_training_contracts import BamfTarget, BamfLearningRowMetadata, BamfTrainingRow
from bilqis_mlx.runtime.source_execution import source_content_digest
from scripts.bamf.profiling.issue1645.dynamics.delivery_observation import describe_delivery, observe_native_call


class DeliveryObservation(unittest.TestCase):
    def setUp(self):
        self.raw = {"id": "r", "capability": "A.LINK", "gold": "TRUE", "tokens": [1, 2]}
        visit = SimpleNamespace(run_seed=1, visit_id="visit", capability_id="A.LINK")
        meta = BamfLearningRowMetadata("r", "source", "A.LINK", None, (), 1, 1, None,
                                      23, visit, "family", "episode")
        row = BamfTrainingRow(None, BamfTarget("binary", True, 1, True), None, meta)
        compiled = SimpleNamespace(sources=(SimpleNamespace(
            source_row=self.raw, source_seed=17, source_each=1),))
        self.prepared = SimpleNamespace(training_batch=SimpleNamespace(rows=(row,)),
                                        compiled_rows=(compiled,))

    def test_ordinary_missing_authority_stays_missing(self):
        result = describe_delivery(self.prepared, None)
        row = result["rows"][0]
        self.assertIsNone(row["authoritative_source_sha256"])
        self.assertIsNone(row["immediate_dependencies"])
        self.assertEqual(row["observed_source_sha256"], source_content_digest((self.raw,)))
        self.assertEqual(row["source_seed"], 17)
        self.assertEqual(row["optimizer_step_seed"], 23)
        self.assertEqual(row["target"]["value"], True)
        self.assertEqual(result["mentor_supervision_status"], "ABSENT")
        self.assertIsNone(result["mentor_supervision"])

    def test_native_call_observes_actual_mentor_record(self):
        record = {"rows": [{"row_id": "r", "source_row_sha256": source_content_digest((self.raw,)),
                           "influence": .01}]}
        mentor = SimpleNamespace(to_record=lambda: record)
        observation = {}
        received = []
        def owner(*args, **kwargs):
            received.append(kwargs["mentor_supervision"])
            return "gradient"
        self.assertEqual(observe_native_call(owner, observation)(mentor_supervision=mentor), "gradient")
        self.assertEqual(received, [mentor])
        result = describe_delivery(self.prepared, observation["mentor_supervision"])
        self.assertEqual(result["mentor_supervision"], record)
        self.assertEqual(result["mentor_supervision_status"], "DELIVERED")
        record["rows"][0]["source_row_sha256"] = "bad"
        with self.assertRaisesRegex(ValueError, "mentor delivery source drift"):
            describe_delivery(self.prepared, record)

    def test_wrong_compiled_source_row_rejected(self):
        self.raw["id"] = "foreign"
        with self.assertRaisesRegex(ValueError, "prepared row identity drift"):
            describe_delivery(self.prepared, None)
