"""#1576 stable numerical compilation boundary regressions."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.runtime.atlas_model_microbatch import _materialize_gradient
from bilqis_mlx.runtime.microbatch.compiled_route import (
    _reset_compiled_route_cache_for_tests,
    learning_first_compiled_route,
    stable_route_compile_key,
)
from bilqis_mlx.runtime.microbatch.route_kernel import RouteMicrobatchKernel


def _decision(name="route", values=("LEFT", "RIGHT")):
    return SimpleNamespace(
        decision_id=name,
        kind=SimpleNamespace(value="OPERATOR"),
        legal_values=values,
        depends_on=(),
        occurrence=0,
    )


def _fixtures(*, release="a" * 64, extent="b" * 64, decisions=None):
    decisions = (_decision(),) if decisions is None else decisions
    extents = SimpleNamespace(digest=extent)
    features = SimpleNamespace(semantic_release=release)
    compiled = SimpleNamespace(
        features=features,
        extents=extents,
        compiled=SimpleNamespace(rows=(SimpleNamespace(positions=(0, 1)),)),
    )
    rows = tuple(SimpleNamespace(compiled=compiled) for _ in range(2))
    plans = tuple(SimpleNamespace(
        decisions=decisions,
        execution_order=tuple(item.decision_id for item in decisions),
    ) for _ in rows)
    targets = tuple((SimpleNamespace(decision_id="route", value="LEFT"),) for _ in rows)
    masks = tuple({"route": True} for _ in rows)
    kernel = RouteMicrobatchKernel(
        lengths=mx.array((2, 2), dtype=mx.int32),
        operator_masks=(mx.array((True, True), dtype=mx.bool_),),
        operand_masks=(mx.array((False, False), dtype=mx.bool_),),
        occurrences=(mx.zeros((2, 384), dtype=mx.float32),),
        feedback=(mx.zeros((2, 384), dtype=mx.float32),),
        candidate_vectors=(mx.zeros((2, 2, 384), dtype=mx.float32),),
        candidate_masks=(mx.ones((2, 2), dtype=mx.bool_),),
        target_indices=(mx.zeros((2,), dtype=mx.int32),),
        operator_counts=mx.ones((2,), dtype=mx.int32),
        operand_counts=mx.zeros((2,), dtype=mx.int32),
        salience_targets=(),
        has_salience=False,
        features=features,
        extents=extents,
        dependency_masks=(mx.zeros((2, 0), dtype=mx.bool_),),
    )
    backend = SimpleNamespace(topology=ModelTopologySpecV2())
    return backend, rows, plans, targets, masks, kernel


def test_compile_key_ignores_irrelevant_python_identity_objects():
    left = _fixtures()
    right = _fixtures()
    assert stable_route_compile_key(*left) == stable_route_compile_key(*right)


def test_compile_key_invalidates_release_extent_shape_and_route():
    base = _fixtures()
    base_key = stable_route_compile_key(*base)
    release_key = stable_route_compile_key(*_fixtures(release="c" * 64))
    extent_key = stable_route_compile_key(*_fixtures(extent="d" * 64))
    route_key = stable_route_compile_key(
        *_fixtures(decisions=(_decision(values=("LEFT", "RIGHT", "HOLD")),)))
    backend, rows, plans, targets, masks, kernel = _fixtures()
    shaped = replace(
        kernel, candidate_vectors=(mx.zeros((2, 3, 384), dtype=mx.float32),))
    shape_key = stable_route_compile_key(
        backend, rows, plans, targets, masks, shaped)
    assert len({base_key, release_key, extent_key, route_key, shape_key}) == 5


def test_compile_cache_reuses_same_stable_key_and_rebuilds_on_route_change():
    _reset_compiled_route_cache_for_tests()
    first = _fixtures()
    changed = _fixtures(decisions=(_decision(values=("LEFT", "RIGHT", "HOLD")),))
    sentinel = object()
    with patch.dict("os.environ", {"BILQIS_MLX_COMPILE_STABLE_KERNEL": "1"}), patch(
            "bilqis_mlx.runtime.microbatch.compiled_route._compile_route",
            return_value=sentinel) as compile_route:
        compiled, state = learning_first_compiled_route(*first)
        reused, reused_state = learning_first_compiled_route(*_fixtures())
        rebuilt, rebuilt_state = learning_first_compiled_route(*changed)
    assert compiled is sentinel and reused is sentinel and rebuilt is sentinel
    assert (state, reused_state, rebuilt_state) == ("miss", "hit", "miss")
    assert compile_route.call_count == 2


def test_compilation_toggle_is_disabled_by_default():
    _reset_compiled_route_cache_for_tests()
    with patch.dict("os.environ", {}, clear=True):
        compiled, state = learning_first_compiled_route(*_fixtures())
    assert compiled is None
    assert state == "disabled"


def test_compiled_inner_route_remains_inside_one_outer_materialization_barrier():
    params = {"x": mx.array(2.0, dtype=mx.float32)}
    compiled_square = mx.compile(lambda current: current["x"] * current["x"])
    with patch.object(mx, "eval", wraps=mx.eval) as evaluate:
        loss, gradients, *_ = _materialize_gradient(
            lambda current: compiled_square(current),
            params, False, {}, None, (), (), (), (), None, None, ())
    assert float(loss) == 4.0
    assert float(gradients["x"]) == 4.0
    assert evaluate.call_count == 1
