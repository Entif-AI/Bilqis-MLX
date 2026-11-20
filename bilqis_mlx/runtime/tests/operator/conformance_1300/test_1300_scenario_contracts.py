"""Cheap contracts for #1300 scenario orchestration helpers."""
from __future__ import annotations

from types import SimpleNamespace
import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.runtime.tests.operator.conformance_1300_support.rollback import (
    boolean_literal_indices,
    collapse_semantic_pair,
)
from bilqis_mlx.runtime.tests.operator.conformance_1300_support.constants import (
    FALSE_SYMBOL,
    TRUE_SYMBOL,
)
from bilqis_mlx.semantics.abi import load_historical_graph
from bilqis_mlx.runtime.tests.operator.conformance_1300_support.scenario import (
    assert_structural_admission_transition,
)


def _state(generation: int, optimizer_step: int):
    return SimpleNamespace(
        generation=generation,
        retained_state=SimpleNamespace(optimizer_step=optimizer_step),
    )


class StructuralAdmissionTransitionTests(unittest.TestCase):
    def test_generation_may_advance_without_optimizer_step(self):
        assert_structural_admission_transition(
            self, _state(3, 2), _state(4, 2),
        )

    def test_generation_must_advance(self):
        with self.assertRaises(AssertionError):
            assert_structural_admission_transition(
                self, _state(3, 2), _state(3, 2),
            )

    def test_optimizer_step_must_not_regress(self):
        with self.assertRaises(AssertionError):
            assert_structural_admission_transition(
                self, _state(3, 2), _state(4, 1),
            )


class DestructiveCandidateContractTests(unittest.TestCase):
    def test_boolean_literal_indices_resolve_from_historical_abi(self):
        graph = load_historical_graph()
        false_index, true_index = boolean_literal_indices()

        self.assertEqual(graph["tokens"][false_index], FALSE_SYMBOL)
        self.assertEqual(graph["tokens"][true_index], TRUE_SYMBOL)
        self.assertNotEqual(false_index, true_index)

    def test_semantic_pair_collapse_changes_only_the_target_row(self):
        bank = mx.array(
            [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
            dtype=mx.float32,
        )

        changed = collapse_semantic_pair({"identity.bank.0": bank}, 0, 1)

        np.testing.assert_array_equal(
            np.asarray(changed["identity.bank.0"][0]),
            np.asarray(bank[0]),
        )
        np.testing.assert_array_equal(
            np.asarray(changed["identity.bank.0"][1]),
            np.asarray(bank[0]),
        )
        np.testing.assert_array_equal(
            np.asarray(changed["identity.bank.0"][2]),
            np.asarray(bank[2]),
        )
        np.testing.assert_array_equal(np.asarray(bank[1]), np.asarray([3.0, 4.0]))


class ColdResumeProbeContractTests(unittest.TestCase):
    def test_legal_next_probe_imports_current_priority_contract_owner(self):
        from bilqis_mlx.runtime.tests.operator.conformance_1300_support import (
            cold_legal_next_probe,
        )

        self.assertTrue(callable(cold_legal_next_probe.require_priority_lawful_frontier))
