"""B09.1a exact rank-eight adapters, B01 groups and accepted row ages."""
from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from unittest import TestCase

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_plasticity import (
    AdapterParameters, IdentityRowAge, adapter_forward,
    adapter_parameter_view, advance_accepted_row_ages, group_eligibility,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, ParameterGroup,
    bamf_parameter_census, expected_bamf_shapes,
)


@lru_cache(maxsize=1)
def _ledger():
    spec = ModelTopologySpecV2()
    extents = GenerationExtents(1, 1, "a"*64, "b"*64, "c"*64)
    parameters = {
        item.name: mx.zeros(item.shape, dtype=mx.float32)
        for item in expected_bamf_shapes(spec, extents)
    }
    return spec, extents, parameters


def _params(group_index=0, *, activate_B=False):
    spec, extents, base = _ledger()
    parameters = dict(base)
    for index in range(spec.depth_groups):
        prefix = f"plastic.group.{index}."
        parameters[prefix+"norm"] = mx.ones((768,), dtype=mx.float32)
        A = mx.zeros((8, 768), dtype=mx.float32)
        A[0, 0] = 1.0
        parameters[prefix+"A"] = A
        B = mx.zeros((768, 8), dtype=mx.float32)
        if activate_B:
            B[0, 0] = 2.0
        parameters[prefix+"B"] = B
    return spec, extents, parameters, adapter_parameter_view(
        parameters, spec=spec, extents=extents, group_index=group_index)


class PlasticAdapterTests(TestCase):
    def test_three_zero_B_adapters_are_exact_identity_but_B_remains_trainable(self):
        hidden = mx.zeros((1, 2, 768), dtype=mx.float32)
        hidden[0, 0, 0] = 1.0
        for group in range(3):
            _spec, _extents, _tree, params = _params(group)
            output = adapter_forward(hidden, params)
            np.testing.assert_array_equal(
                np.asarray(output), np.asarray(hidden))
            def loss(B):
                return mx.sum(adapter_forward(
                    hidden, replace(params, B=B)))
            gradient = mx.grad(loss)(params.B)
            self.assertTrue(bool(mx.all(mx.isfinite(gradient))))
            self.assertGreater(float(mx.sum(mx.abs(gradient))), 0)

    def test_nonzero_B_matches_literal_rank8_silu_equation_and_trains_A(self):
        hidden = mx.zeros((1, 1, 768), dtype=mx.float32)
        hidden[0, 0, 0] = 1.0
        _spec, _extents, _tree, params = _params(1, activate_B=True)
        output = adapter_forward(hidden, params)
        normed = mx.fast.rms_norm(
            hidden, params.norm, ModelTopologySpecV2.rms_norm_epsilon)
        projected = normed @ params.A.T
        expected = hidden + (
            (projected * mx.sigmoid(projected)) @ params.B.T) / 8
        np.testing.assert_allclose(
            np.asarray(output), np.asarray(expected), rtol=0, atol=1e-6)
        self.assertGreater(float(output[0, 0, 0]), 1.0)
        gradient = mx.grad(lambda A: mx.sum(
            adapter_forward(hidden, replace(params, A=A))))(params.A)
        self.assertTrue(bool(mx.all(mx.isfinite(gradient))))
        self.assertGreater(float(mx.sum(mx.abs(gradient))), 0)

    def test_parameter_view_borrows_exact_B01_prefix_without_write_through(self):
        spec, extents, parameters, view = _params(2)
        self.assertEqual(view.group_index, 2)
        view.B[0, 0] = 7.0
        mx.eval(view.B, parameters["plastic.group.2.B"])
        self.assertEqual(float(view.B[0, 0]), 7.0)
        self.assertEqual(float(parameters["plastic.group.2.B"][0, 0]), 0.0)
        with self.assertRaises(BilqisError):
            adapter_parameter_view(
                parameters, spec=spec, extents=extents, group_index=3)
        altered = dict(parameters)
        altered["plastic.group.1.A"] = mx.zeros((8, 767), dtype=mx.float32)
        with self.assertRaises(BilqisError):
            adapter_parameter_view(
                altered, spec=spec, extents=extents, group_index=1)

    def test_fast_group_is_exact_B01_and_new_identity_rows_are_separate(self):
        spec, extents, _parameters = _ledger()
        census = bamf_parameter_census(spec, extents)
        ages = (
            IdentityRowAge(0, 0, 0),
            IdentityRowAge(0, 1, 7),
            IdentityRowAge(0, 2, 8),
        )
        fast = group_eligibility("FAST", census, ages)
        expected_fast = tuple(
            item.name for item in census.parameters
            if item.group is ParameterGroup.FAST)
        self.assertEqual(fast.eligible_parameter_names, expected_fast)
        self.assertTrue(any(name.startswith("motif.page.") for name in expected_fast))
        self.assertTrue(any(name.startswith("motif.site.") for name in expected_fast))
        self.assertTrue(any(name.startswith("plastic.group.") for name in expected_fast))
        self.assertFalse(any(name.startswith("blocks.") for name in expected_fast))
        self.assertEqual(fast.fast_identity_rows, ((0, 0), (0, 1)))
        self.assertEqual(fast.established_identity_rows, ((0, 2),))
        self.assertIn("identity.bank.0", fast.frozen_parameter_names)
        for mode in ("FOUNDATION", "FULL"):
            full = group_eligibility(mode, census, ages)
            self.assertEqual(
                full.eligible_parameter_names,
                tuple(item.name for item in census.parameters))
            self.assertEqual(full.frozen_parameter_names, ())

    def test_row_age_moves_once_per_accepted_candidate_not_per_optimizer_step(self):
        parent = (
            IdentityRowAge(0, 0, 0),
            IdentityRowAge(0, 1, 7),
            IdentityRowAge(0, 2, 8),
        )
        rejected = advance_accepted_row_ages(
            parent, ((0, 0), (0, 1)), accepted=False)
        self.assertIs(rejected, parent)
        accepted = advance_accepted_row_ages(
            parent, ((0, 0), (0, 1)), accepted=True)
        self.assertEqual(
            tuple(item.accepted_age for item in accepted), (1, 8, 8))
        self.assertEqual(
            tuple(item.accepted_age for item in parent), (0, 7, 8))
        census = bamf_parameter_census(*_ledger()[:2])
        eligibility = group_eligibility("FAST", census, accepted)
        self.assertEqual(eligibility.fast_identity_rows, ((0, 0),))
        self.assertEqual(
            eligibility.established_identity_rows, ((0, 1), (0, 2)))
        next_candidate = advance_accepted_row_ages(
            accepted, ((0, 0),), accepted=True)
        self.assertEqual(
            tuple(item.accepted_age for item in next_candidate), (2, 8, 8))

    def test_invalid_modes_rows_and_adapter_inputs_fail_closed(self):
        spec, extents, _parameters, view = _params()
        census = bamf_parameter_census(spec, extents)
        ages = (IdentityRowAge(0, 0, 0),)
        with self.assertRaises(BilqisError):
            group_eligibility("ADAPTIVE", census, ages)
        with self.assertRaises(BilqisError):
            group_eligibility("FAST", census, (
                IdentityRowAge(0, 1, 0), IdentityRowAge(0, 0, 0)))
        with self.assertRaises(BilqisError):
            advance_accepted_row_ages(
                ages, ((0, 9),), accepted=True)
        with self.assertRaises(BilqisError):
            advance_accepted_row_ages(
                ages, ((0, 0), (0, 0)), accepted=True)
        with self.assertRaises(BilqisError):
            adapter_forward(mx.zeros((1, 1, 767), dtype=mx.float32), view)
        with self.assertRaises(BilqisError):
            adapter_forward(mx.zeros((1, 1, 768), dtype=mx.float32),
                            replace(view, B=mx.zeros((768, 7), dtype=mx.float32)))


class PlasticityCadenceTests(TestCase):
    def test_foundation_and_rejection_preserve_cadence(self):
        from bilqis_mlx.learning.atlas_plasticity import (
            PlasticityPolicy, next_update_mode, advance_candidate_policy,
        )
        parent = PlasticityPolicy(row_ages=(IdentityRowAge(0, 1, 0),))
        self.assertEqual(next_update_mode(parent, teacher_requests_full=False), "FULL")
        self.assertIs(advance_candidate_policy(parent, teacher_requests_full=False,
                      accepted=False, participating_rows=((0, 1),)), parent)
        actual = advance_candidate_policy(parent, teacher_requests_full=False,
                     accepted=True, participating_rows=((0, 1),))
        self.assertEqual(actual.mode, "FOUNDATION")
        self.assertEqual(actual.accepted_fast_since_full, 0)
        self.assertEqual(actual.row_ages[0].accepted_age, 1)
        self.assertEqual(parent.row_ages[0].accepted_age, 0)

    def test_eight_accepted_fast_then_full_across_cold_readback(self):
        import json
        from bilqis_mlx.learning.atlas_plasticity import (
            PlasticityPolicy, next_update_mode, advance_candidate_policy,
        )
        state = PlasticityPolicy(mode="ADAPTIVE", row_ages=(IdentityRowAge(0, 1, 0),))
        for count in range(8):
            self.assertEqual(next_update_mode(state, teacher_requests_full=False), "FAST")
            self.assertIs(advance_candidate_policy(state, teacher_requests_full=False,
                          accepted=False, participating_rows=((0, 1),)), state)
            state = advance_candidate_policy(state, teacher_requests_full=False,
                        accepted=True, participating_rows=((0, 1),))
            state = PlasticityPolicy.from_record(json.loads(json.dumps(state.to_record())))
            self.assertEqual(state.accepted_fast_since_full, count + 1)
            self.assertEqual(state.row_ages[0].accepted_age, count + 1)
        self.assertEqual(next_update_mode(state, teacher_requests_full=False), "FULL")
        self.assertIs(advance_candidate_policy(state, teacher_requests_full=False,
                      accepted=False, participating_rows=()), state)
        state = advance_candidate_policy(state, teacher_requests_full=False,
                    accepted=True, participating_rows=((0, 1),))
        self.assertEqual(state.accepted_fast_since_full, 0)
        self.assertEqual(state.row_ages[0].accepted_age, 8)
        self.assertEqual(next_update_mode(state, teacher_requests_full=False), "FAST")

    def test_teacher_full_and_idle_rows(self):
        from bilqis_mlx.learning.atlas_plasticity import (
            PlasticityPolicy, next_update_mode, advance_candidate_policy,
        )
        parent = PlasticityPolicy(mode="ADAPTIVE", accepted_fast_since_full=3,
                                  row_ages=(IdentityRowAge(0, 1, 7), IdentityRowAge(0, 2, 0)))
        self.assertEqual(next_update_mode(parent, teacher_requests_full=True), "FULL")
        self.assertIs(advance_candidate_policy(parent, teacher_requests_full=True,
                      accepted=False, participating_rows=((0, 1),)), parent)
        actual = advance_candidate_policy(parent, teacher_requests_full=True,
                     accepted=True, participating_rows=((0, 1),))
        self.assertEqual(actual.accepted_fast_since_full, 0)
        self.assertEqual(tuple(row.accepted_age for row in actual.row_ages), (8, 0))
        self.assertEqual(actual.mode, "ADAPTIVE")

    def test_policy_records_fail_closed_without_inferred_defaults(self):
        from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy, next_update_mode
        valid = PlasticityPolicy().to_record()
        for key in valid:
            changed = dict(valid)
            del changed[key]
            with self.assertRaises(BilqisError):
                PlasticityPolicy.from_record(changed)
        for patch in ({"mode": "FAST"}, {"accepted_fast_since_full": True},
                      {"accepted_fast_since_full": -1}, {"policy_version": "other"},
                      {"extra": 1}, {"row_ages": [{"bank_index": 0}]}):
            with self.assertRaises(BilqisError):
                PlasticityPolicy.from_record(dict(valid, **patch))
        with self.assertRaises(BilqisError):
            PlasticityPolicy(accepted_fast_since_full=1)
        with self.assertRaises(BilqisError):
            next_update_mode(PlasticityPolicy(), teacher_requests_full=1)

    def test_overdue_counter_uses_literal_greater_equal_contract(self):
        from bilqis_mlx.learning.atlas_plasticity import (
            PlasticityPolicy, next_update_mode, advance_candidate_policy,
        )
        parent = PlasticityPolicy.from_record(
            PlasticityPolicy(mode="ADAPTIVE", accepted_fast_since_full=9).to_record())
        self.assertEqual(next_update_mode(parent, teacher_requests_full=False), "FULL")
        self.assertIs(advance_candidate_policy(parent, teacher_requests_full=False,
                      accepted=False, participating_rows=()), parent)
        actual = advance_candidate_policy(parent, teacher_requests_full=False,
                     accepted=True, participating_rows=())
        self.assertEqual(actual.accepted_fast_since_full, 0)
