"""Factory delivery observation boundary validation."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.factory_candidate_training import FactoryDeliveryObservation
from bilqis_mlx.runtime.teacher_observation_capture import ObservationCapture, store_sidecar


class FactoryDeliveryObservationTests(unittest.TestCase):
    def test_unprepared_capture_rejects_before_training(self):
        with TemporaryDirectory() as run_dir_value, self.assertRaises(BilqisError) as caught:
            FactoryDeliveryObservation(
                ObservationCapture(Path(run_dir_value), {}),
                1, ({"id": "row:test"},), 1)
        self.assertEqual(
            caught.exception.context["reason"],
            "FACTORY_TRAINING_OBSERVATION_INVALID",
        )

    def test_prepared_capture_is_accepted(self):
        with TemporaryDirectory() as run_dir_value:
            run_dir = Path(run_dir_value)
            capture = ObservationCapture(run_dir, {})
            capture.attempt_id = "fixture-attempt"
            capture.proposal_id = store_sidecar(
                run_dir, {"attempt_id": capture.attempt_id})["sha256"]
            capture.select_option("A.IDENTITY", None)
            observation = FactoryDeliveryObservation(
                capture, 1, ({"id": "row:test"},), 1)
        self.assertIs(observation.capture, capture)


if __name__ == "__main__":
    unittest.main()
