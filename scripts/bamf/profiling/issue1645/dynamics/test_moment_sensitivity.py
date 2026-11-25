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


def test_zero_second_moment_coordinates_and_frozen_cohort():
    import json
    from types import SimpleNamespace
    from scripts.bamf.profiling.issue1645.dynamics.moment_sensitivity import analyze_target

    hp = {"learning_rate": .01, "betas": (.5, .75), "eps": 1e-6}
    leaf = "weight"
    prefix = "p" + leaf.encode().hex()
    parent = {prefix + "_m": np.zeros(2), prefix + "_v": np.zeros(2),
              prefix + "_count": np.array(0)}
    parent = SimpleNamespace(get_tensor=parent.__getitem__)
    probes = {"protected": SimpleNamespace(get_tensor=lambda _: np.ones(2))}
    for active in (True, False):
        decay = np.array([-.01, -.02]) if active else np.zeros(2)
        update = {"mask/" + leaf: np.array(active), "clipped/" + leaf: np.zeros(2),
                  "delta/" + leaf: decay, "decay/" + leaf: decay}
        receipt = {"hyperparameters": hp, "leaves": {leaf: {"selected_clocks": int(active)}}}
        result = {"interference": {"target->protected": {"all": {
            "native_delta_dot": float(decay.sum())}}}}
        metrics = analyze_target("target", SimpleNamespace(get_tensor=update.__getitem__),
                                 parent, probes, receipt, result)
        assert metrics["active_clocks"] == int(active)
        assert metrics["nonzero_second_coordinates"] == 0
        assert metrics["retained_second_fraction_mean"] is None
        assert metrics["retained_second_majority_fraction"] is None
        assert metrics["retained_second_at_least_90pct_fraction"] is None
        assert (metrics["bias_factors_min"] is None) == (not active)
        assert metrics["protected_dots"]["protected"]["no_second_history_matched_norm"] == decay.sum()
        json.dumps(metrics, allow_nan=False)


def test_nonzero_observed_norm_cannot_match_zero_counterfactual():
    from scripts.bamf.profiling.issue1645.dynamics.moment_sensitivity import finish_dots

    row = {"observed_adaptive": 2., "decay": -.5, "no_second_history": 0.,
           "uniform_denominator": 0., "analytic_native": 0., "uncorrected": 0.}
    result = {"interference": {"target->protected": {"all": {"native_delta_dot": 1.5}}}}
    norms = {"observed_adaptive": 4., "no_second_history": 0., "uniform_denominator": 0.}
    finish_dots("target", result, {"protected": row}, norms)
    assert row["no_second_history_matched_norm"] is None
    assert row["uniform_denominator_matched_norm"] is None
    assert row["analytic_native_with_decay"] == -.5
