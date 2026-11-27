import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.bamf.memory.check_trainer_memory_plateau import check_observation


class TrainerMemoryPlateauCheckTests(unittest.TestCase):
    def _write(self, root: Path, values):
        path = root / "trainer-observed.json"
        path.write_text(json.dumps({
            "schema": "bilqis.bamf.trainer-observed/v7",
            "visits": [{
                "candidate_steps": [
                    {"candidate_step": index, "physical_footprint_bytes": value}
                    for index, value in enumerate(values, start=1)
                ],
            }],
        }))
        return path

    def test_stable_observation_passes(self):
        with TemporaryDirectory() as directory:
            path = self._write(Path(directory), (
                2_000_000_000, 2_200_000_000, 2_150_000_000, 2_180_000_000,
                2_160_000_000, 2_190_000_000, 2_170_000_000, 2_180_000_000))
            self.assertTrue(check_observation(path).plateau)

    def test_ratcheting_observation_fails(self):
        with TemporaryDirectory() as directory:
            path = self._write(Path(directory), (
                2_000_000_000, 2_500_000_000, 3_000_000_000, 3_500_000_000,
                4_000_000_000, 4_500_000_000, 5_000_000_000, 5_500_000_000))
            result = check_observation(path)
            self.assertFalse(result.plateau)
            self.assertIn("positive retained-memory slope", result.reasons)


if __name__ == "__main__":
    unittest.main()
