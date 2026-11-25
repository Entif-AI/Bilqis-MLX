"""Numerical regression tests for the read-only diagnostic, not learner evidence."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.runtime.atlas_optimizer_contracts import AdamWHyperparameters, AdamWStateTree
from scripts.bamf.profiling.issue1645.dynamics.authentic_dynamics import probe_seed
from scripts.bamf.profiling.issue1645.dynamics.displacement_analysis import write_update, interference_matrix


class AuthenticDynamics(unittest.TestCase):
    def test_actual_update_and_epsilon_matrix(self):
        mx.set_default_device(mx.cpu)
        names = ("readout.control", "identity.bank.0")
        def tree(first, second, dtype=mx.float32):
            return dict(zip(names, (mx.array(first, dtype=dtype),
                                    mx.array(second, dtype=dtype)), strict=True))
        p = tree([0., 1.], [[1.], [2.]])
        m = tree([-2., 0.], [[.2], [.3]])
        v = tree([4., 1.], [[.1], [.2]])
        n = tree(10, [9, 3], mx.uint64)
        parent = AdamWStateTree(p, m, v, n)
        g = tree([1., 0.], [[.1], [100.]])
        mask = tree(True, [True, False], mx.bool_)
        hp = AdamWHyperparameters(.0007, (.88, .97), 1e-7, .03)
        with TemporaryDirectory() as root:
            root = Path(root)
            d = root / "target"
            r = write_update(d, parent, g, mask, dict.fromkeys(names, True),
                             {names[0]: (True, ()), names[1]: (False, (0,))}, hp, max_norm=1.)
            mx.save_safetensors(str(d / "protected.safetensors"),
                               tree([1., 0.], [[0.], [0.]]))
            pair = interference_matrix(root, ("target",))["target->target"]
            self.assertLess(pair["all"]["raw_negative_gradient_dot"], 0)
            self.assertGreater(pair["all"]["native_delta_dot"], 0)
            self.assertEqual(r["leaves"][names[1]]["selected_rows"], [0])
            self.assertGreater(r["masked_unclipped_norm"], 1.)
            self.assertLess(r["masked_unclipped_norm"], 1.1)
            for eps in r["epsilon_candidates"]:
                self.assertEqual(pair["tied_identity"][f"epsilon_{eps}_delta_dot"],
                                 pair["tied_identity"]["native_delta_dot"])
                self.assertNotEqual(pair["dedicated_readout"][f"epsilon_{eps}_delta_dot"],
                                    pair["dedicated_readout"]["native_delta_dot"])
            self.assertAlmostEqual(pair["all"]["native_delta_dot"],
                                   sum(pair["all"][key] for key in
                                       ("old_moment_dot", "decay_dot", "current_gradient_and_rounding_dot")))
        np.testing.assert_array_equal(np.asarray(parent.parameters[names[1]]), [[1.], [2.]])

    def test_seed_does_not_depend_on_score(self):
        self.assertEqual(probe_seed("m", "A.PARENT", "target"), probe_seed("m", "A.PARENT", "target"))
        self.assertNotEqual(probe_seed("m", "A.PARENT", "target"), probe_seed("m", "A.PARENT", "protected"))
