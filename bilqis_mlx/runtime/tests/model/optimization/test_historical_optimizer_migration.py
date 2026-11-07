"""B12.3 exact-state historical count migration behavior."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import torch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.historical_optimizer_digests import historical_model_state_digest
from bilqis_mlx.runtime.historical_optimizer_migration import migrate_historical_bamf_optimizer
from bilqis_mlx.runtime.tests.model.optimization.historical_optimizer_fixtures import (
    historical_attestation, historical_fixture, mint_capability,
)


class HistoricalOptimizerMigrationTests(unittest.TestCase):
    def test_shared_scalar_maps_to_b01_count_geometry(self):
        fixture = historical_fixture("shared")
        with TemporaryDirectory() as temporary:
            checkpoint = Path(temporary) / "fixture.pt"
            checkpoint.write_bytes(b"audited synthetic bamf-v2 fixture")
            attestation = historical_attestation(fixture, checkpoint)
            with patch(
                    "bilqis_mlx.runtime.historical_optimizer_contract._HISTORICAL_UPDATE_ATTESTATIONS",
                    {"fixture": attestation}), patch(
                    "bilqis_mlx.runtime.model_topology_v2.expected_bamf_shapes",
                    return_value=fixture["declared"]):
                capability = mint_capability(fixture, checkpoint, attestation)
                state, receipt = migrate_historical_bamf_optimizer(
                    fixture["native"], fixture["weights"],
                    parameter_order=fixture["order"], spec=fixture["spec"],
                    extents=fixture["extents"], capability=capability)
        np.testing.assert_array_equal(
            np.asarray(state.update_counts["features.local_slot"]),
            np.array([3, 3], dtype=np.uint64))
        self.assertEqual(state.update_counts["blocks.0.query"].shape, ())
        self.assertEqual(int(state.update_counts["blocks.0.query"]), 3)
        self.assertEqual(receipt["native_step"], 3)
        self.assertTrue(receipt["historical_all_parameters_updated_together"])

    def test_capability_is_bound_to_exact_numerical_state(self):
        fixture = historical_fixture("shared")
        with TemporaryDirectory() as temporary:
            checkpoint = Path(temporary) / "fixture.pt"
            checkpoint.write_bytes(b"anti replay fixture")
            attestation = historical_attestation(fixture, checkpoint)
            with patch(
                    "bilqis_mlx.runtime.historical_optimizer_contract._HISTORICAL_UPDATE_ATTESTATIONS",
                    {"fixture": attestation}), patch(
                    "bilqis_mlx.runtime.model_topology_v2.expected_bamf_shapes",
                    return_value=fixture["declared"]):
                capability = mint_capability(fixture, checkpoint, attestation)
                changed = dict(fixture["weights"])
                changed["blocks.0.query"] = changed["blocks.0.query"] + 1
                with self.assertRaises(BilqisError):
                    migrate_historical_bamf_optimizer(
                        fixture["native"], changed,
                        parameter_order=fixture["order"], spec=fixture["spec"],
                        extents=fixture["extents"], capability=capability)

    def test_mutated_capability_cannot_bypass_code_owned_attestation(self):
        fixture = historical_fixture("shared")
        with TemporaryDirectory() as temporary:
            checkpoint = Path(temporary) / "fixture.pt"
            checkpoint.write_bytes(b"capability mutation fixture")
            attestation = historical_attestation(fixture, checkpoint)
            with patch(
                    "bilqis_mlx.runtime.historical_optimizer_contract._HISTORICAL_UPDATE_ATTESTATIONS",
                    {"fixture": attestation}), patch(
                    "bilqis_mlx.runtime.model_topology_v2.expected_bamf_shapes",
                    return_value=fixture["declared"]):
                capability = mint_capability(fixture, checkpoint, attestation)
                changed = dict(fixture["weights"])
                changed["blocks.0.query"] = (
                    changed["blocks.0.query"]
                    + torch.ones_like(changed["blocks.0.query"]))
                object.__setattr__(
                    capability, "model_state_sha256",
                    historical_model_state_digest(
                        changed, parameter_order=fixture["order"]))
                with self.assertRaises(BilqisError):
                    migrate_historical_bamf_optimizer(
                        fixture["native"], changed,
                        parameter_order=fixture["order"], spec=fixture["spec"],
                        extents=fixture["extents"], capability=capability)


if __name__ == "__main__":
    unittest.main()
