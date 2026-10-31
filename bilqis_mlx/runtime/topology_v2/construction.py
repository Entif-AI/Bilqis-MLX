"""B01 construction ownership; historical tensor and initializer contracts retained."""
from __future__ import annotations
from bilqis_mlx.runtime.model_topology import DEFAULT_OPTIMIZER
from .spec import IDENTITY_ESTABLISHED_AGE, ModelTopologySpecV2, initializer_seed
from .records import GenerationExtents, ParameterGroup
from .ledger import bamf_parameter_census
from .initialization import initialize_bamf_parameter
from .validation import validate_bamf_parameters
from .serialization import bamf_storage_key


def create_unbound_bamf_state(spec: ModelTopologySpecV2, extents: GenerationExtents,
                              *, run_seed: int):
    """Construct disposable unbound tensors and zero moments, without admitting rows.

    Source-bound identity and allocated motif rows require their respective
    owners. This state is not a releasable model or a trainable optimizer.
    """
    import mlx.core as mx

    census = bamf_parameter_census(spec, extents)
    declared = census.parameters
    initializer_seed(run_seed, "validation")
    parameters = {item.name: mx.array(initialize_bamf_parameter(item, run_seed=run_seed), dtype=mx.float32)
                  for item in declared}
    state = {
        "step": mx.array(0, dtype=mx.uint64),
        "learning_rate": mx.array(DEFAULT_OPTIMIZER["learning_rate"], dtype=mx.float32),
        **{item.name: {"m": mx.zeros(item.shape, dtype=mx.float32),
                       "v": mx.zeros(item.shape, dtype=mx.float32)} for item in declared},
    }
    mx.eval(parameters, state)
    validate_bamf_parameters(spec, extents, parameters)
    manifest = {
        "schema": "bilqis.mlx.bamf-initialization/v1",
        "initialization_status": "UNBOUND",
        "topology_digest": spec.digest,
        "shape_policy_digest": spec.shape_policy_digest,
        "generation_extents_digest": extents.digest,
        "generation_extents": extents.to_record(),
        "run_seed": run_seed,
        "parameter_count": census.total,
        "parameter_subtotals": {kind.value: count for kind, count in census.subtotals.items()},
        "identity_row_group_policy": {
            "before_age": ParameterGroup.FAST.value,
            "from_age": ParameterGroup.SLOW.value,
            "established_at": IDENTITY_ESTABLISHED_AGE,
            "age_unit": "accepted-participating-candidates",
        },
        "optimizer": {"algorithm": "AdamW", "learning_rate": DEFAULT_OPTIMIZER["learning_rate"],
                      "betas": list(DEFAULT_OPTIMIZER["betas"]), "eps": DEFAULT_OPTIMIZER["eps"],
                      "weight_decay": DEFAULT_OPTIMIZER["weight_decay"], "bias_correction": True},
        "parameters": [{"name": item.name, "shape": list(item.shape), "dtype": item.dtype,
                        "parameters": item.parameter_count, "category": item.category.value,
                        "initializer": item.initializer.value, "group": item.group.value,
                        "decay": item.decay,
                        "storage_keys": {part: bamf_storage_key(item.name, part)
                                         for part in ("weight", "m", "v")}}
                       for item in declared],
        "serialization_schema": "bilqis.mlx.bamf-named-tensors/v1",
        "constants": ["sinusoidal_positions", "sha256_literal_features", "visibility_masks"],
    }
    return parameters, state, manifest
