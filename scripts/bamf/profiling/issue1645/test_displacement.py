"""Small numerical diagnostics against the unchanged B12 owner, not training."""
import unittest
import numpy as np
import mlx.core as mx
from bilqis_mlx.runtime.optimizer_step import adamw_leaf_update, adamw_selected_rows_update

mx.set_default_device(mx.cpu)

HP = dict(learning_rate=0.0007, betas=(.88, .97), eps=1e-7, weight_decay=.03)


def actual(theta, m, v, counts, gradient, mask, **overrides):
    args = [mx.array(x, dtype=mx.float32) for x in (theta, m, v)]
    out = adamw_leaf_update(*args, mx.array(counts, dtype=mx.uint64),
        mx.array(gradient, dtype=mx.float32), mx.array(mask, dtype=mx.bool_),
        **(HP | overrides))
    mx.eval(*out)
    return tuple(np.array(x) for x in out)


class DisplacementWitness(unittest.TestCase):
    def test_actual_update_can_conflict_when_raw_gradients_agree(self):
        theta = np.array([0., 0.], dtype=np.float32)
        gradient = np.array([1., 0.], dtype=np.float32)
        preserve = np.array([1., 0.], dtype=np.float32)
        next_theta, _, _, count = actual(theta, [-2., 0.], [4., 1.], 10,
                                         gradient, True)
        self.assertGreater(float(preserve @ gradient), 0.)
        self.assertGreater(float(preserve @ (next_theta - theta)), 0.)
        self.assertEqual(int(count), 11)

    def test_selected_rows_equivalent_to_full_mask(self):
        theta = np.array([[2., -1.], [3., 4.], [-.3, .8]], np.float32)
        m = np.array([[.1, -.2], [.9, -.8], [.01, .2]], np.float32)
        v = np.array([[.2, .4], [.7, .6], [.01, .3]], np.float32)
        counts = [10, 19, 1]
        g = [[.1, .2], [3., -5.], [-.1, .2]]
        mask = [True, False, True]
        expected = actual(theta, m, v, counts, g, mask)
        result = adamw_selected_rows_update(
            *(mx.array(x, dtype=mx.float32) for x in (theta, m, v)),
            mx.array(counts, dtype=mx.uint64), mx.array(g, dtype=mx.float32),
            mx.array(mask, dtype=mx.bool_), [0, 2], **HP)
        mx.eval(*result)
        for got, want in zip(result, expected, strict=True):
            np.testing.assert_allclose(np.array(got), want, rtol=2e-6, atol=1e-7)
        for got, original in zip(result[:3], (theta,m,v), strict=True):
            np.testing.assert_array_equal(np.array(got)[1], original[1])
        np.testing.assert_array_equal(np.array(result[3]), [11, 19, 2])

    def test_weight_decay_is_part_of_actual_displacement(self):
        theta = np.array([2., -3.], dtype=np.float32)
        next_theta, _, _, count = actual(theta, [0., 0.], [0., 0.], 10,
                                         [0., 0.], True)
        np.testing.assert_allclose(next_theta, theta * (1 - HP['learning_rate'] * HP['weight_decay']), atol=1e-7)
        self.assertEqual(int(count), 11)

    def test_epsilon_changes_participating_small_moments_not_frozen_rows(self):
        theta = [[0.], [2.]]
        args = (theta, [[0.], [.2]], [[0.], [.3]], [0, 10], [[1e-6], [1.]], [True, False])
        low, lm, lv, lc = actual(*args)
        high, hm, hv, hc = actual(*args, eps=1e-4)
        self.assertLess(abs(float(high[0, 0])), abs(float(low[0, 0])) / 50)
        for arr in (low, high):
            self.assertEqual(float(arr[1, 0]), 2.)
        np.testing.assert_array_equal(lc, [1, 10])
        np.testing.assert_array_equal(hc, lc)
        np.testing.assert_array_equal(hm, lm)
        np.testing.assert_array_equal(hv, lv)


if __name__ == '__main__':
    mx.set_default_device(mx.cpu)
    unittest.main()
