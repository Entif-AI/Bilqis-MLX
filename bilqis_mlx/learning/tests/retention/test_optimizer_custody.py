"""Optimizer custody."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, commit_trial, fork_student, np,
)


class OptimizerCustodyTests(CausalTeacherExperimentTests):
    def test_parent_adamw_remains_unchanged_until_trial_committed(self):
        import mlx.core as mx
        import mlx.optimizers as optim
        mx.set_default_device(mx.cpu)
        weights = {"embedding.weight": mx.array(np.arange(12).reshape(3,4).astype(np.float32))}
        parent = optim.AdamW(learning_rate=.00013, bias_correction=True)
        parent.update(weights, {"embedding.weight": mx.zeros_like(weights["embedding.weight"])})
        mx.eval(weights,parent.state)
        parent_weight = np.asarray(weights["embedding.weight"]).copy()
        parent_moment = np.asarray(parent.state["embedding.weight"]["m"]).copy()
        parent_step = int(parent.state["step"].item())
        branch, branch_opt = fork_student(mx, weights, parent)
        branch_opt.update(branch, {"embedding.weight": mx.ones_like(branch["embedding.weight"])})
        mx.eval(branch,branch_opt.state)
        self.assertEqual(int(parent.state["step"].item()), parent_step)
        np.testing.assert_array_equal(np.asarray(weights["embedding.weight"]), parent_weight)
        np.testing.assert_array_equal(np.asarray(parent.state["embedding.weight"]["m"]), parent_moment)
        self.assertNotEqual(int(branch_opt.state["step"].item()), parent_step)
        commit_trial(weights, parent, branch, branch_opt)
        self.assertEqual(int(parent.state["step"].item()), parent_step+1)
        self.assertFalse(np.array_equal(np.asarray(weights["embedding.weight"]), parent_weight))
