"""B12.3 historical scalar migration authority adversaries."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import torch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.historical_optimizer_contract import (
    HISTORICAL_FULL_TREE_CONTRACT, HistoricalAdamWMigrationCapability,
    mint_historical_bamf_migration_capability,
)
from bilqis_mlx.runtime.tests.model.optimization.historical_optimizer_fixtures import (
    historical_attestation, historical_fixture, mint_capability,
)


class HistoricalOptimizerContractTests(unittest.TestCase):
    def test_divergent_parameter_steps_cannot_mint_counts(self):
        fixture = historical_fixture("divergent")
        with TemporaryDirectory() as temporary:
            checkpoint = Path(temporary) / "fixture.pt"
            checkpoint.write_bytes(b"divergent fixture")
            attestation = historical_attestation(fixture, checkpoint)
            with self.assertRaises(BilqisError):
                mint_capability(fixture, checkpoint, attestation)

    def test_equal_counts_from_disjoint_steps_do_not_prove_shared_history(self):
        fixture = historical_fixture("disjoint")
        steps = [int(fixture["native"]["state"][pid]["step"].item())
                 for pid in fixture["native"]["param_groups"][0]["params"]]
        self.assertEqual(steps, [1, 1])
        with TemporaryDirectory() as temporary:
            checkpoint = Path(temporary) / "fixture.pt"
            checkpoint.write_bytes(b"disjoint fixture")
            attestation = historical_attestation(fixture, checkpoint)
            with self.assertRaises(BilqisError):
                mint_capability(fixture, checkpoint, attestation)

    def test_fractional_native_step_is_rejected_without_truncation(self):
        fixture = historical_fixture("shared")
        with TemporaryDirectory() as temporary:
            checkpoint = Path(temporary) / "fixture.pt"
            checkpoint.write_bytes(b"fractional step fixture")
            attestation = historical_attestation(fixture, checkpoint)
            for cell in fixture["native"]["state"].values():
                cell["step"] = torch.tensor(3.9)
            with patch(
                    "bilqis_mlx.runtime.historical_optimizer_contract._HISTORICAL_UPDATE_ATTESTATIONS",
                    {"fixture": attestation}), patch(
                    "bilqis_mlx.runtime.model_topology_v2.expected_bamf_shapes",
                    return_value=fixture["declared"]), self.assertRaises(BilqisError):
                mint_historical_bamf_migration_capability(
                    checkpoint, fixture["native"], fixture["weights"],
                    parameter_order=fixture["order"], spec=fixture["spec"],
                    extents=fixture["extents"], attestation_id="fixture")

    def test_attestation_must_cover_static_full_tree_lineage(self):
        fixture = historical_fixture("shared")
        with TemporaryDirectory() as temporary:
            checkpoint = Path(temporary) / "fixture.pt"
            checkpoint.write_bytes(b"unsupported lineage fixture")
            attestation = historical_attestation(
                fixture, checkpoint,
                update_contract="bilqis.mlx.historical-late-row-lineage/v1")
            self.assertNotEqual(attestation["update_contract"], HISTORICAL_FULL_TREE_CONTRACT)
            with self.assertRaises(BilqisError):
                mint_capability(fixture, checkpoint, attestation)

    def test_capability_cannot_be_caller_constructed(self):
        with self.assertRaises(BilqisError):
            HistoricalAdamWMigrationCapability()


if __name__ == "__main__":
    unittest.main()
