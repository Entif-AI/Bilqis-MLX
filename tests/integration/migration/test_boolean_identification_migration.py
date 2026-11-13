"""Neural-inert durable enrollment of B.IDBOOLOPS into the revised Grade-B release."""
from bilqis_mlx.state_dag import read_current
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bilqis_mlx.boolean_composite import build_course as build_composite
from bilqis_mlx.boolean_identification import CAPABILITY, RELEASE, build_course
from bilqis_mlx.curriculum import BOOLEAN_OPERATORS
from bilqis_mlx.curriculum.scheduler import start_new
from bilqis_mlx.factory.live_releases import initial_course, boolean_successor
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.trainer import (
    VERSION
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "vendor" / "legacy-v16"


@unittest.skipUnless(os.environ.get("BILQIS_FULL_GRADE_B_TESTS") == "1",
                     "legacy/full Grade B compatibility tests are opt-in")
class BooleanIdentificationMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = json.loads((
            ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        cls.manifest = manifest
        cls.a = initial_course(accepted_grade_a(manifest))
        cls.b = boolean_successor(cls.a, SOURCE)
        cls.old = build_composite(cls.b, SOURCE)
        cls.new = build_course(cls.old, SOURCE)
        _, _, cls.graph, _, _ = read_sources(SOURCE)


    def test_historical_release_remains_readable(self):
        self.assertEqual(self.new.grades[0], self.old.grades[0])
        self.assertTrue(self.new.digest())


if __name__ == "__main__":
    unittest.main()
