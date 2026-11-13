"""Synthetic BAMF-v2 historical optimizer fixtures for B12.3."""
import hashlib
from unittest.mock import patch

import torch

from bilqis_mlx.runtime.historical_optimizer_contract import (
    HISTORICAL_ATTESTATION_SCHEMA, HISTORICAL_FULL_TREE_CONTRACT,
    mint_historical_bamf_migration_capability,
)
from bilqis_mlx.runtime.historical_optimizer_digests import (
    historical_count_geometry_digest, historical_model_state_digest,
    historical_optimizer_state_digest,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    BAMF_ARCHITECTURE_ID, GenerationExtents, Initializer,
    ModelTopologySpecV2, ParameterGroup, ParameterSpec,
)


def historical_fixture(mode="shared"):
    first = torch.nn.Parameter(torch.tensor([[1., 2.], [3., 4.]], dtype=torch.float32))
    second = torch.nn.Parameter(torch.tensor([[5., 6.], [7., 8.]], dtype=torch.float32))
    optimizer = torch.optim.AdamW(
        [first, second], lr=.001, betas=(.9, .95), eps=1e-8,
        weight_decay=.01, foreach=False)
    if mode == "shared":
        for _ in range(3):
            first.grad = torch.ones_like(first)
            second.grad = torch.ones_like(second)
            optimizer.step()
        global_step = 3
    elif mode == "divergent":
        first.grad = torch.ones_like(first)
        second.grad = torch.ones_like(second)
        optimizer.step()
        first.grad = torch.ones_like(first)
        second.grad = None
        optimizer.step()
        global_step = 2
    elif mode == "disjoint":
        first.grad = torch.ones_like(first)
        second.grad = None
        optimizer.step()
        first.grad = None
        second.grad = torch.ones_like(second)
        optimizer.step()
        global_step = 2
    else:
        raise ValueError(mode)
    declared = (
        ParameterSpec(
            "features.local_slot", (2, 2), Initializer.EMBEDDING,
            ParameterGroup.FAST, True),
        ParameterSpec(
            "blocks.0.query", (2, 2), Initializer.MATRIX,
            ParameterGroup.SLOW, True),
    )
    return {
        "native": optimizer.state_dict(),
        "weights": {
            "features.local_slot": first.detach(),
            "blocks.0.query": second.detach(),
        },
        "order": ("features.local_slot", "blocks.0.query"),
        "declared": declared,
        "spec": ModelTopologySpecV2(),
        "extents": GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64),
        "global_step": global_step,
    }


def historical_attestation(fixture, checkpoint, *, update_contract=None):
    return {
        "schema": HISTORICAL_ATTESTATION_SCHEMA,
        "architecture_id": BAMF_ARCHITECTURE_ID,
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "model_state_sha256": historical_model_state_digest(
            fixture["weights"], parameter_order=fixture["order"]),
        "optimizer_state_sha256": historical_optimizer_state_digest(
            fixture["native"], fixture["weights"],
            parameter_order=fixture["order"]),
        "count_geometry_sha256": historical_count_geometry_digest(fixture["declared"]),
        "global_optimizer_step": fixture["global_step"],
        "update_contract": update_contract or HISTORICAL_FULL_TREE_CONTRACT,
    }


def mint_capability(fixture, checkpoint, attestation):
    with patch(
            "bilqis_mlx.runtime.model_topology_v2.expected_bamf_shapes",
            return_value=fixture["declared"]), patch(
            "bilqis_mlx.runtime.historical_optimizer_contract._HISTORICAL_UPDATE_ATTESTATIONS",
            {"fixture": attestation}):
        return mint_historical_bamf_migration_capability(
            checkpoint, fixture["native"], fixture["weights"],
            parameter_order=fixture["order"], spec=fixture["spec"],
            extents=fixture["extents"], attestation_id="fixture")
