"""B09.2 literal per-step participation and pre-clipping masks."""
from __future__ import annotations

from unittest import TestCase

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_engram_reads import MotifReadResult
from bilqis_mlx.learning.atlas_plasticity import (
    ActiveAdmittedRows, GroupEligibility, IdentityRowAge,
    ParameterMask, RoleReadParticipation, SemanticDenominator,
    StepParticipationInputs, UpdateMask, advance_accepted_row_ages,
    group_eligibility, mask_gradients, optimizer_participation_mask,
    parameter_update_mask, step_participation,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, bamf_parameter_census,
)
from bilqis_mlx.runtime.atlas_optimizer import (
    AdamWHyperparameters, AdamWStateTree, _adamw_update,
)


def _motif(*slots):
    return MotifReadResult(
        mx.zeros((1, 1, 768), dtype=mx.float32), (("EXACT",),),
        tuple(sorted(slots)), ("a" * 64,))


def _eligibility():
    # FAST keeps the identity tensor globally slow while exposing only young
    # rows through fast_identity_rows. This is the row-level B09 exception.
    return GroupEligibility(
        "FAST",
        ("features.role", "features.type", "motif.page.0",
         "plastic.group.0.A"),
        ("blocks.0.attn.qkv", "identity.bank.0"),
        ((0, 0), (0, 1), (0, 2)),
        ((0, 0), (0, 1)),
        ((0, 2),),
    )


def _active():
    return ActiveAdmittedRows(
        identity_rows=((0, 0), (0, 1), (0, 2)),
        motif_slots=(0, 1, 2),
        feature_rows=(("role", 2), ("role", 3), ("type", 4)),
        local_slot_rows=(0, 1, 2),
    )


class ParticipationTests(TestCase):
    def test_update_mask_materializes_exact_b12_boolean_geometry(self):
        eligibility = GroupEligibility(
            "FULL", ("dense", "identity.bank.0"), (),
            ((0, 0), (0, 1), (0, 2)), (),
            ((0, 0), (0, 1), (0, 2)))
        participation = step_participation(
            StepParticipationInputs(
                visible_identity_rows=((0, 0), (0, 2)),
                executed_parameter_names=("dense",)),
            SemanticDenominator(), (), RoleReadParticipation())
        mask = parameter_update_mask(
            eligibility, participation,
            ActiveAdmittedRows(identity_rows=((0, 0), (0, 1), (0, 2))))
        actual = optimizer_participation_mask(mask, {
            "dense": mx.array(4, dtype=mx.uint64),
            "identity.bank.0": mx.array([2, 3, 4], dtype=mx.uint64),
        })
        self.assertTrue(bool(actual["dense"]))
        np.testing.assert_array_equal(
            np.asarray(actual["identity.bank.0"]),
            np.array([True, False, True]),
        )

    def test_b09_bridge_drives_b12_zero_gradient_count_and_decay(self):
        eligibility = GroupEligibility(
            "FULL", ("identity.bank.0",), (),
            ((0, 0), (0, 1)), (), ((0, 0), (0, 1)))
        participation = step_participation(
            StepParticipationInputs(visible_identity_rows=((0, 0),)),
            SemanticDenominator(), (), RoleReadParticipation())
        mask = parameter_update_mask(
            eligibility, participation,
            ActiveAdmittedRows(identity_rows=((0, 0), (0, 1))))
        parameters = {
            "identity.bank.0": mx.array([[1., 2.], [3., 4.]], dtype=mx.float32),
        }
        parent = AdamWStateTree(
            parameters,
            {name: mx.zeros_like(value) for name, value in parameters.items()},
            {name: mx.zeros_like(value) for name, value in parameters.items()},
            {"identity.bank.0": mx.array([0, 3], dtype=mx.uint64)},
        )
        booleans = optimizer_participation_mask(mask, parent.update_counts)
        actual = _adamw_update(
            parent,
            {"identity.bank.0": mx.zeros((2, 2), dtype=mx.float32)},
            booleans,
            AdamWHyperparameters(.001, (.9, .95), 1e-8, .01),
            decay={"identity.bank.0": True}, loss_bearing=True,
        )
        np.testing.assert_array_equal(
            np.asarray(booleans["identity.bank.0"]),
            np.array([True, False]),
        )
        np.testing.assert_array_equal(
            np.asarray(actual.update_counts["identity.bank.0"]),
            np.array([1, 3], dtype=np.uint64),
        )
        self.assertFalse(bool(mx.all(
            actual.parameters["identity.bank.0"][0]
            == parent.parameters["identity.bank.0"][0])))
        np.testing.assert_array_equal(
            np.asarray(actual.parameters["identity.bank.0"][1]),
            np.asarray(parent.parameters["identity.bank.0"][1]),
        )

    def test_local_slot_participation_remains_row_local_through_b12(self):
        eligibility = GroupEligibility(
            "FULL", ("features.local_slot",), (), (), (), ())
        participation = step_participation(
            StepParticipationInputs(
                local_slot_rows=(1,),
                executed_parameter_names=("features.local_slot",)),
            SemanticDenominator(), (), RoleReadParticipation())
        mask = parameter_update_mask(
            eligibility, participation,
            ActiveAdmittedRows(local_slot_rows=(0, 1, 2)))
        parameters = {
            "features.local_slot": mx.array(
                [[1., 2.], [3., 4.], [5., 6.]], dtype=mx.float32),
        }
        parent = AdamWStateTree(
            parameters,
            {"features.local_slot": mx.zeros((3, 2), dtype=mx.float32)},
            {"features.local_slot": mx.zeros((3, 2), dtype=mx.float32)},
            {"features.local_slot": mx.array([0, 7, 11], dtype=mx.uint64)},
        )
        booleans = optimizer_participation_mask(mask, parent.update_counts)
        actual = _adamw_update(
            parent,
            {"features.local_slot": mx.zeros((3, 2), dtype=mx.float32)},
            booleans,
            AdamWHyperparameters(.001, (.9, .95), 1e-8, .01),
            decay={"features.local_slot": True}, loss_bearing=True,
        )
        self.assertEqual(mask.parameter("features.local_slot").row_indices, (1,))
        self.assertFalse(mask.parameter("features.local_slot").whole_parameter)
        np.testing.assert_array_equal(
            np.asarray(booleans["features.local_slot"]),
            np.array([False, True, False]),
        )
        np.testing.assert_array_equal(
            np.asarray(actual.update_counts["features.local_slot"]),
            np.array([0, 8, 11], dtype=np.uint64),
        )
        np.testing.assert_array_equal(
            np.asarray(actual.parameters["features.local_slot"][0]),
            np.asarray(parent.parameters["features.local_slot"][0]),
        )
        self.assertFalse(bool(mx.all(
            actual.parameters["features.local_slot"][1]
            == parent.parameters["features.local_slot"][1])))
        np.testing.assert_array_equal(
            np.asarray(actual.parameters["features.local_slot"][2]),
            np.asarray(parent.parameters["features.local_slot"][2]),
        )

    def test_two_optimizer_steps_derive_distinct_literal_row_masks(self):
        first = step_participation(
            StepParticipationInputs(
                visible_identity_rows=((0, 0),),
                executed_parameter_names=("plastic.group.0.A",)),
            SemanticDenominator(
                identity_rows=((0, 1),), feature_rows=(("role", 2),)),
            (_motif(0),), RoleReadParticipation((("type", 4),)))
        second = step_participation(
            StepParticipationInputs(
                feedback_identity_rows=((0, 2),),
                executed_parameter_names=("blocks.0.attn.qkv",)),
            SemanticDenominator(feature_rows=(("role", 3),)),
            (_motif(2),), RoleReadParticipation())

        first_mask = parameter_update_mask(_eligibility(), first, _active())
        second_mask = parameter_update_mask(_eligibility(), second, _active())
        self.assertEqual(first_mask.parameter("identity.bank.0").row_indices, (0, 1))
        self.assertEqual(second_mask.parameter("identity.bank.0").row_indices, ())
        self.assertEqual(first_mask.parameter("motif.page.0").row_indices, (0,))
        self.assertEqual(second_mask.parameter("motif.page.0").row_indices, (2,))
        self.assertEqual(first_mask.parameter("features.role").row_indices, (2,))
        self.assertEqual(second_mask.parameter("features.role").row_indices, (3,))
        self.assertTrue(first_mask.parameter("plastic.group.0.A").whole_parameter)
        self.assertFalse(second_mask.parameter("plastic.group.0.A").whole_parameter)
        self.assertFalse(first_mask.parameter("blocks.0.attn.qkv").whole_parameter)
        self.assertFalse(second_mask.parameter("blocks.0.attn.qkv").whole_parameter)
        self.assertNotEqual(first_mask, second_mask)

    def test_active_admitted_and_fast_age_are_both_required(self):
        participation = step_participation(
            StepParticipationInputs(visible_identity_rows=((0, 0), (0, 2))),
            SemanticDenominator(), (), RoleReadParticipation())
        mask = parameter_update_mask(_eligibility(), participation, _active())
        self.assertEqual(mask.parameter("identity.bank.0").row_indices, (0,))

        inactive = ActiveAdmittedRows(
            identity_rows=((0, 2),), motif_slots=(), feature_rows=())
        mask = parameter_update_mask(_eligibility(), participation, inactive)
        self.assertEqual(mask.parameter("identity.bank.0").row_indices, ())

    def test_actual_B01_fast_eligibility_exposes_only_young_identity_rows(self):
        spec = ModelTopologySpecV2()
        extents = GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)
        census = bamf_parameter_census(spec, extents)
        eligibility = group_eligibility(
            "FAST", census,
            (IdentityRowAge(0, 0, 0), IdentityRowAge(0, 1, 8)))
        participation = step_participation(
            StepParticipationInputs(visible_identity_rows=((0, 0), (0, 1))),
            SemanticDenominator(), (), RoleReadParticipation())
        active = ActiveAdmittedRows(identity_rows=((0, 0), (0, 1)))
        mask = parameter_update_mask(eligibility, participation, active)
        self.assertIn("identity.bank.0", eligibility.frozen_parameter_names)
        self.assertEqual(mask.parameter("identity.bank.0").row_indices, (0,))

    def test_mask_is_applied_before_clipping_and_huge_inactive_gradient_vanishes(self):
        participation = step_participation(
            StepParticipationInputs(
                visible_identity_rows=((0, 0),),
                executed_parameter_names=("plastic.group.0.A",)),
            SemanticDenominator(), (), RoleReadParticipation())
        mask = parameter_update_mask(_eligibility(), participation, _active())
        gradients = {
            "blocks.0.attn.qkv": mx.full((2, 2), 1e9, dtype=mx.float32),
            "features.role": mx.full((5, 2), 1e9, dtype=mx.float32),
            "features.type": mx.full((6, 2), 1e9, dtype=mx.float32),
            "identity.bank.0": mx.array(
                [[0.0, 0.0], [1e9, 1e9], [1e9, 1e9]], dtype=mx.float32),
            "motif.page.0": mx.full((3, 2), 1e9, dtype=mx.float32),
            "plastic.group.0.A": mx.ones((2, 2), dtype=mx.float32),
        }
        masked = mask_gradients(gradients, mask)
        self.assertEqual(float(mx.sum(mx.abs(masked["blocks.0.attn.qkv"]))), 0.0)
        self.assertEqual(float(mx.sum(mx.abs(masked["features.role"]))), 0.0)
        self.assertEqual(float(mx.sum(mx.abs(masked["motif.page.0"]))), 0.0)
        np.testing.assert_array_equal(
            np.asarray(masked["identity.bank.0"]), np.zeros((3, 2), dtype=np.float32))
        np.testing.assert_array_equal(
            np.asarray(masked["plastic.group.0.A"]), np.ones((2, 2), dtype=np.float32))
        # A participating numerical-zero row is still legally participating;
        # B12 must advance its count even though the masked gradient is zero.
        self.assertEqual(mask.parameter("identity.bank.0").row_indices, (0,))

    def test_no_loss_target_skips_the_complete_step(self):
        participation = step_participation(
            StepParticipationInputs(
                visible_identity_rows=((0, 0),),
                executed_parameter_names=("plastic.group.0.A",),
                loss_bearing_target=False),
            SemanticDenominator(identity_rows=((0, 1),)),
            (_motif(0),), RoleReadParticipation((("role", 2),)))
        self.assertEqual(participation.identity_rows, ())
        self.assertEqual(participation.motif_slots, ())
        self.assertEqual(participation.feature_rows, ())
        self.assertEqual(participation.local_slot_rows, ())
        mask = parameter_update_mask(_eligibility(), participation, _active())
        self.assertFalse(mask.has_loss_bearing_target)
        self.assertFalse(any(item.whole_parameter or item.row_indices
                             for item in mask.parameters))

    def test_accepted_candidate_ages_union_of_actual_masked_rows_once(self):
        parent = (
            IdentityRowAge(0, 0, 0), IdentityRowAge(0, 1, 7),
            IdentityRowAge(0, 2, 0),
        )
        first = step_participation(
            StepParticipationInputs(visible_identity_rows=((0, 0),)),
            SemanticDenominator(identity_rows=((0, 1),)), (),
            RoleReadParticipation())
        second = step_participation(
            StepParticipationInputs(feedback_identity_rows=((0, 0),)),
            SemanticDenominator(), (), RoleReadParticipation())
        rows = tuple(sorted(set(
            parameter_update_mask(_eligibility(), first, _active()).participating_identity_rows
            + parameter_update_mask(_eligibility(), second, _active()).participating_identity_rows)))
        accepted = advance_accepted_row_ages(parent, rows, accepted=True)
        rejected = advance_accepted_row_ages(parent, rows, accepted=False)
        self.assertEqual(tuple(item.accepted_age for item in accepted), (1, 8, 0))
        self.assertIs(rejected, parent)

    def test_invalid_unsorted_and_unadmitted_evidence_fails_closed(self):
        with self.assertRaises(BilqisError):
            StepParticipationInputs(visible_identity_rows=((0, 1), (0, 0)))
        with self.assertRaises(BilqisError):
            SemanticDenominator(feature_rows=(("bogus", 1),))
        with self.assertRaises(BilqisError):
            ActiveAdmittedRows(motif_slots=(2, 1))
