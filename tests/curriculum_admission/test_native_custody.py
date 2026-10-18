"""Disposable native-AdamW fork and promotion; never read a human checkpoint."""
import unittest

import numpy as np

from bilqis_mlx.learning_experiment import commit_trial, fork_student


class NativeOptimizerCustodyChecks(unittest.TestCase):
    def test_abandoned_candidate_cannot_mutate_parent_weights_or_native_adamw(self):
        import mlx.core as mx
        import mlx.optimizers as optim

        parent = {"weight": mx.array([1.0, 2.0], dtype=mx.float32)}
        own_adamw = optim.AdamW(learning_rate=0.001)
        own_adamw.update(parent, {"weight": mx.array([0.1, 0.1])})
        mx.eval(parent, own_adamw.state)
        original_weights = np.asarray(parent["weight"]).copy()
        original_step = int(own_adamw.state["step"].item())
        original_moments = {
            key: {name: np.asarray(value).copy() for name, value in states.items()}
            for key, states in own_adamw.state.items() if isinstance(states, dict)
        }

        challenger, challenger_opt = fork_student(mx, parent, own_adamw)
        challenger["weight"] = challenger["weight"] + mx.array([0.5, -0.5])
        challenger_opt.update(challenger, {"weight": mx.array([0.2, 0.2])})
        mx.eval(challenger, challenger_opt.state)

        # No commit_trial call: this is the observed REJECT transaction outcome.
        np.testing.assert_array_equal(np.asarray(parent["weight"]), original_weights)
        self.assertEqual(int(own_adamw.state["step"].item()), original_step)
        for key, states in original_moments.items():
            for name, value in states.items():
                np.testing.assert_array_equal(
                    np.asarray(own_adamw.state[key][name]), value)

        # One admitted promotion must couple the complete new model and AdamW.
        expected_weights = np.asarray(challenger["weight"]).copy()
        expected_step = int(challenger_opt.state["step"].item())
        commit_trial(parent, own_adamw, challenger, challenger_opt)
        np.testing.assert_array_equal(np.asarray(parent["weight"]), expected_weights)
        self.assertEqual(int(own_adamw.state["step"].item()), expected_step)
        self.assertGreater(expected_step, original_step)


if __name__ == "__main__":
    unittest.main()
