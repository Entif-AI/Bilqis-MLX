"""Analytic sensitivity fixtures distinguish scale, history and row-clock effects."""
import numpy as np

from scripts.bamf.profiling.issue1645.dynamics.moment_sensitivity import sensitivities


def test_second_history_and_bias_factors():
    hp = {"learning_rate": .01, "betas": (.5, .75), "eps": 1e-6}
    values, fraction, c1, c2 = sensitivities(
        np.array([[2., 0.], [1., 2.]]), np.array([[3., 0.], [1., 0.]]),
        np.array([[-2., 0.], [1., 2.]]), np.array([[1.], [2.]]), hp)
    assert np.allclose(fraction, [2.25 / 3.25, .75, 0.])
    assert np.allclose(c1, [[2.], [4. / 3.]])
    assert np.allclose(c2, [[2.], [4. / np.sqrt(7.)]])
    assert np.allclose(values["analytic_native"][0], [0., 0.])
    expected = -.01 * (4. / 3.) / (4. / np.sqrt(7.) + 1e-6)
    assert np.isclose(values["analytic_native"][1, 0], expected)
    assert abs(values["no_second_history"][1, 0]) > abs(expected)
    assert np.isclose(values["uncorrected"][1, 0], -.01 / (1 + 1e-6))
    assert np.isclose(values["uniform_denominator"][1, 1], -.01 * 8. / 3.)
