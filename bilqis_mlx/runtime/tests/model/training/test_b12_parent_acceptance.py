"""Parent B12 acceptance seams spanning B09 participation and B12 AdamW."""
from __future__ import annotations

from unittest import TestCase

import mlx.core as mx
import numpy as np

from bilqis_mlx.learning.atlas_engram_reads import MotifReadResult
from bilqis_mlx.learning.atlas_participation import (
    ActiveAdmittedRows,
    RoleReadParticipation,
    SemanticDenominator,
    StepParticipationInputs,
    _parameter_update_mask,
    optimizer_participation_mask,
    step_participation,
)
from bilqis_mlx.learning.atlas_plasticity import GroupEligibility
from bilqis_mlx.runtime.atlas_optimizer import (
    AdamWHyperparameters,
    AdamWStateTree,
    _adamw_update,
)


HP = AdamWHyperparameters(.001, (.9, .95), 1e-8, .01)


def _optimizer(name: str, values: mx.array, counts: mx.array) -> AdamWStateTree:
    return AdamWStateTree(
        {name: values},
        {name: mx.zeros_like(values)},
        {name: mx.zeros_like(values)},
        {name: counts},
    )


def _motif(slot: int) -> MotifReadResult:
    return MotifReadResult(
        mx.zeros((1, 1, 768), dtype=mx.float32),
        (("EXACT",),),
        (slot,),
        ("a" * 64,),
    )


class B12ParentAcceptanceTests(TestCase):
    def test_output_only_semantic_denominator_row_updates_through_b12(self):
        name = "identity.bank.0"
        parent = _optimizer(
            name,
            mx.array([[1., 2.], [3., 4.]], dtype=mx.float32),
            mx.array([4, 0], dtype=mx.uint64),
        )
        eligibility = GroupEligibility(
            "FULL", (name,), (), ((0, 0), (0, 1)), (), ((0, 0), (0, 1)))
        participation = step_participation(
            StepParticipationInputs(),
            SemanticDenominator(identity_rows=((0, 1),)),
            (),
            RoleReadParticipation(),
        )
        mask = _parameter_update_mask(
            eligibility, participation,
            ActiveAdmittedRows(identity_rows=((0, 0), (0, 1))),
        )
        booleans = optimizer_participation_mask(mask, parent.update_counts)
        actual = _adamw_update(
            parent,
            {name: mx.array([[9., 9.], [1., -2.]], dtype=mx.float32)},
            booleans,
            HP,
            decay={name: False},
            max_norm=1.,
        )

        np.testing.assert_array_equal(np.asarray(booleans[name]), [False, True])
        self.assertEqual(int(actual.update_counts[name][1]), 1)
        self.assertFalse(bool(mx.all(actual.parameters[name][1] == parent.parameters[name][1])))
        for field in ("parameters", "m", "v", "update_counts"):
            np.testing.assert_array_equal(
                np.asarray(getattr(actual, field)[name][0]),
                np.asarray(getattr(parent, field)[name][0]),
            )

    def test_unused_motif_row_is_byte_identical_after_b12_update(self):
        name = "motif.page.0"
        parent = _optimizer(
            name,
            mx.array([[1., 2.], [3., 4.]], dtype=mx.float32),
            mx.array([0, 5], dtype=mx.uint64),
        )
        eligibility = GroupEligibility("FULL", (name,), (), (), (), ())
        participation = step_participation(
            StepParticipationInputs(),
            SemanticDenominator(),
            (_motif(0),),
            RoleReadParticipation(),
        )
        mask = _parameter_update_mask(
            eligibility, participation,
            ActiveAdmittedRows(motif_slots=(0, 1)),
        )
        booleans = optimizer_participation_mask(mask, parent.update_counts)
        actual = _adamw_update(
            parent,
            {name: mx.array([[1., -1.], [1e9, -1e9]], dtype=mx.float32)},
            booleans,
            HP,
            decay={name: True},
            max_norm=1.,
        )

        np.testing.assert_array_equal(np.asarray(booleans[name]), [True, False])
        self.assertEqual(int(actual.update_counts[name][0]), 1)
        for field in ("parameters", "m", "v", "update_counts"):
            np.testing.assert_array_equal(
                np.asarray(getattr(actual, field)[name][1]),
                np.asarray(getattr(parent, field)[name][1]),
            )


if __name__ == "__main__":
    import unittest
    unittest.main()
