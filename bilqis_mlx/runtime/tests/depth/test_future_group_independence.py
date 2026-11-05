"""Paired depth-boundary executions and a deliberate future-read mutant."""
from dataclasses import replace
import unittest

import numpy as np

from bilqis_mlx.runtime.block_attnres import _depth_components
from bilqis_mlx.runtime.tests.depth.depth_helpers import (
    _features, _hidden, _params, _summaries,
)


class FutureGroupIndependenceTests(unittest.TestCase):
    def setUp(self):
        self.current = _hidden([[1, 3, 2], [2, 4, 1]])

    def _boundary_outputs(self, sources, *, future_read=None):
        outputs = []
        for boundary in (1, 2, 3):
            current = self.current
            if future_read is not None and boundary < future_read:
                current = current + sources[future_read].hidden
            output, _, _ = _depth_components(
                current, sources[:boundary + 1],
                _features(boundary), _params(boundary))
            outputs.append(np.asarray(output))
        return tuple(outputs)

    def _assert_future_independence(self, execute, future_group):
        sources = _summaries(3)
        changed = list(sources)
        changed[future_group] = replace(
            sources[future_group],
            hidden=sources[future_group].hidden.at[:].add(100))
        baseline = execute(sources)
        altered = execute(tuple(changed))
        for boundary in range(1, future_group):
            np.testing.assert_array_equal(
                baseline[boundary - 1], altered[boundary - 1])
        self.assertFalse(np.array_equal(
            baseline[future_group - 1], altered[future_group - 1]),
            "changed future state must participate at its own boundary")

    def test_paired_executions_ignore_future_groups_until_their_boundary(self):
        for future_group in (2, 3):
            with self.subTest(future_group=future_group):
                self._assert_future_independence(self._boundary_outputs, future_group)

    def test_independence_witness_rejects_an_intentional_future_read(self):
        for future_group in (2, 3):
            def execute(sources):
                return self._boundary_outputs(sources, future_read=future_group)

            with self.subTest(future_group=future_group), self.assertRaises(AssertionError):
                self._assert_future_independence(execute, future_group)
