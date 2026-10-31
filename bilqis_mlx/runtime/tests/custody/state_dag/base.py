import os
import tempfile
import unittest
from pathlib import Path

class StateDagCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "states").mkdir()
        self.previous_plane = os.environ.get("BILQIS_DATA_PLANE")
        os.environ["BILQIS_DATA_PLANE"] = str(self.root / "plane.sqlite3")
        from bilqis_mlx.data_plane import close_data_planes
        close_data_planes()

    def tearDown(self):
        from bilqis_mlx.data_plane import close_data_planes
        close_data_planes()
        if self.previous_plane is None:
            os.environ.pop("BILQIS_DATA_PLANE", None)
        else:
            os.environ["BILQIS_DATA_PLANE"] = self.previous_plane
        self.temp.cleanup()

    def receipt(self, generation=7):
        misses = [
            {"id": "b" * 64, "capability": "C.NUMBER", "gold": 1},
            {"id": "a" * 64, "capability": "C.COUNT", "gold": 0},
        ]
        misses.sort(key=lambda row: (row["capability"], row["id"]))
        return {
            "schema": "school/v1", "generation": generation,
            "school": {"grade": "C", "queue": ["C.COUNT"]},
            "teacher_misses": misses,
            "teacher_miss_exposures": {row["id"]: 2 for row in misses},
            "championship_epoch_history": [{"schema": "epoch/v1", "n": 1}],
            "large": {"payload": "x" * 40000},
        }
