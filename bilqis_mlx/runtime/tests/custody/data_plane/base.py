import os
import hashlib
import importlib.util
import subprocess
from pathlib import Path
import tempfile
import unittest
from bilqis_mlx.data_plane import close_data_planes

class DataPlaneCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.previous = os.environ.get("BILQIS_DATA_PLANE")
        os.environ["BILQIS_DATA_PLANE"] = str(self.root / "plane.sqlite3")
        close_data_planes()

    def tearDown(self):
        close_data_planes()
        if self.previous is None:
            os.environ.pop("BILQIS_DATA_PLANE", None)
        else:
            os.environ["BILQIS_DATA_PLANE"] = self.previous
        self.temp.cleanup()


def historical_module(root, revision, relative, name, expected_digest):
    source = subprocess.run(["git", "show", revision + ":" + relative],
                            cwd=Path(__file__).resolve().parents[5],
                            check=True, capture_output=True).stdout
    unittest.TestCase().assertEqual(hashlib.sha256(source).hexdigest(), expected_digest,
                                    "historical writer source drift")
    path = root / (revision + Path(relative).name)
    path.write_bytes(source)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

