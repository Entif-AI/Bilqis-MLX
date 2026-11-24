"""Exact native MLX witnesses for frozen-prefix value/gradient validity."""
from dataclasses import replace

import mlx.core as mx
import numpy as np

from scripts.experiments.issue1618.frozen_region import FrozenRegion, RegionScope


def prefix(inputs, parameters):
    return mx.tanh(inputs @ parameters["upstream"] @ parameters["prefix"])


def test_exact_reuse_and_gradient_equivalence():
    cache = FrozenRegion()
    scope = RegionScope("admission-1", "candidate-1", "mask-1")
    x = mx.array([[1., 2.]])
    p = {"upstream": mx.eye(2), "prefix": mx.array([[0.2, 0.5], [0.3, 0.1]])}
    for suffix in (mx.array([[0.5], [0.7]]), mx.array([[0.8], [-0.2]])):
        frozen = cache.get(scope, x, p, {"suffix"}, prefix)
        reference = lambda w: mx.sum((prefix(x, p) @ w) ** 2)
        reused = lambda w: mx.sum((frozen @ w) ** 2)
        np.testing.assert_array_equal(reference(suffix), reused(suffix))
        np.testing.assert_array_equal(mx.grad(reference)(suffix), mx.grad(reused)(suffix))
    assert (cache.hits, cache.misses) == (1, 1)


def test_upstream_input_thaw_admission_and_rejection_invalidate():
    cache = FrozenRegion()
    scope = RegionScope("admission-1", "candidate-1", "mask-1")
    x = mx.array([[1., 2.]])
    p = {"upstream": mx.eye(2), "prefix": mx.eye(2)}

    def checked(s=scope, inputs=x, parameters=p):
        value = cache.get(s, inputs, parameters, {"suffix"}, prefix)
        np.testing.assert_array_equal(value, prefix(inputs, parameters))
        return value

    before = checked()
    changed = {**p, "upstream": mx.eye(2) * 2}
    assert not np.array_equal(before, checked(parameters=changed))
    checked(inputs=x + 1, parameters=changed)
    checked(replace(scope, admission="admission-2"), parameters=changed)
    checked(replace(scope, input_contract="mask-2"), parameters=changed)
    assert cache.misses == 5
    # Thaw requires a differentiated path even before bytes have changed.
    assert cache.get(scope, x, p, {"upstream"}, prefix) is None
    gradient = mx.grad(lambda w: mx.sum(prefix(x, {**p, "upstream": w})))(p["upstream"])
    assert np.any(np.asarray(gradient) != 0)
    assert cache.bypasses == 1
    checked()
    cache.invalidate()  # explicit rejection boundary
    checked(replace(scope, candidate_epoch="candidate-2"))
    assert cache.misses == 7 and cache.hits == 0
