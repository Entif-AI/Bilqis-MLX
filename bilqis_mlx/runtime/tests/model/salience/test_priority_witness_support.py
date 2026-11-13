from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bilqis_mlx.runtime.tests.model.salience.priority_witness_support import (
    _current_candidate_frontier,
)


class PriorityWitnessSupportTests(unittest.TestCase):
    def test_current_frontier_is_generated_into_disposable_custody(self):
        root = Path(__file__).resolve().parents[5]
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'candidate-frontier'
            frontier = _current_candidate_frontier(root, output)

            self.assertEqual(len(frontier.candidates), 240)
            self.assertGreater(len(frontier.senses), 0)
            self.assertTrue((output / 'frontier_manifest.json').is_file())
            self.assertNotEqual(output, root / 'lib/ithkuil/_curriculum')
