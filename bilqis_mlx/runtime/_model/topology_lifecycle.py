"""Bind structural topology to run custody independently of curriculum identity."""
from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path

from .model_topology import (ModelTopologySpec, resolve_topology,
                             validate_parameter_shapes, create_student)


INITIALIZATION_SEED = 0


def model_implementation():
    return dict(provider="mlx", implementation="bilqis.mlx.causal-tied-fp32/v1",
                precision="fp32")


def dispatch_model_factory(architecture_id, topology_record, *, legacy_factory,
                           bamf_factory, checkpoint_manifest=None, checkpoint_path=None):
    """Select an architecture before a factory can allocate or inspect arrays.

    V2 checkpoint import remains unavailable until its custody owner implements
    the versioned generation reader. Historical readers remain separate.
    """
    from .model_topology_v2 import (BAMF_ARCHITECTURE_ID, LEGACY_ARCHITECTURE_ID,
                                    ModelTopologySpecV2, deserialize_topology)
    from ..errors import ErrorBus, SCHOOL
    topology = deserialize_topology(topology_record)
    if checkpoint_path is not None:
        if checkpoint_manifest is not None:
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.RECORD_INVALID)
        try:
            checkpoint_manifest = json.loads((Path(checkpoint_path) / "manifest.json").read_text())
        except (OSError, ValueError):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.RECORD_INVALID)
        if not isinstance(checkpoint_manifest, dict):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.RECORD_INVALID)
    if architecture_id == LEGACY_ARCHITECTURE_ID and type(topology) is ModelTopologySpec:
        return legacy_factory(topology)
    if architecture_id == BAMF_ARCHITECTURE_ID and type(topology) is ModelTopologySpecV2:
        if checkpoint_manifest is not None:
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.MISMATCH, reason="v2-checkpoint-reader-unavailable")
        return bamf_factory(topology)
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.MISMATCH)


def construct_unbound_model(architecture_id, topology_record, *, run_seed, vocab_size=None,
                            extents=None, checkpoint_path=None):
    """Construct a disposable unbound tree or inspect an existing v1 bundle.

    The v2 result is not an admitted model or a trainable optimizer. Its backend,
    source bindings and durable generation loader have separate owners.
    """
    from .model_topology_v2 import LEGACY_ARCHITECTURE_ID, create_unbound_bamf_state
    from ..errors import ErrorBus, SCHOOL

    def legacy_factory(topology):
        if extents is not None:
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.MISMATCH)
        if checkpoint_path is not None:
            if vocab_size is not None:
                ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.MISMATCH)
            from .mlx_checkpoint import load_semantically_bound_bundle
            parameters, optimizer, manifest, catalog = load_semantically_bound_bundle(checkpoint_path)
            validate_parameter_shapes(parameters, topology, len(catalog["tokens"]))
            return parameters, optimizer.state, manifest
        parameters, optimizer = create_student(topology, vocab_size, seed=run_seed)
        return parameters, optimizer.state, {
            "schema": "bilqis.mlx.unbound-initialization/v1",
            "architecture_id": LEGACY_ARCHITECTURE_ID,
            "model_topology": topology.to_record(),
            "initialization_status": "UNBOUND",
            "run_seed": run_seed,
        }

    def bamf_factory(topology):
        if vocab_size is not None:
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.MISMATCH)
        return create_unbound_bamf_state(topology, extents, run_seed=run_seed)

    return dispatch_model_factory(architecture_id, topology_record,
                                  legacy_factory=legacy_factory, bamf_factory=bamf_factory,
                                  checkpoint_path=checkpoint_path)


def topology_from_file(path: Path | None):
    if path is None:
        return None
    try:
        record = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        from ..errors import ErrorBus, SCHOOL
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.RECORD_INVALID, detail=str(exc))
    from .model_topology_v2 import deserialize_topology
    return deserialize_topology(record)


def inspect_resume_topology(run_dir, receipt, requested=None):
    """Resolve saved config and checkpoint metadata before any recovery writes."""
    topology = resolve_topology(receipt["config"], receipt.get("model_topology"), requested)
    shapes = receipt.get("parameter_shapes")
    if shapes is not None:
        parameters = {name: SimpleNamespace(shape=tuple(shape)) for name, shape in shapes.items()}
        validate_parameter_shapes(parameters, topology, shapes["embedding.weight"][0])
    directory = Path(run_dir) / receipt["model_bundle"]
    manifest_path = directory / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text())
        if receipt.get("model_topology") is not None and manifest.get("model_topology") is None:
            from ..errors import ErrorBus, SCHOOL
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.MISMATCH)
        resolve_topology(receipt["config"], manifest.get("model_topology"), topology)
        if receipt.get("model_topology") is not None and (
                receipt.get("model_implementation") != model_implementation() or
                manifest.get("model_implementation") != model_implementation()):
            from ..errors import ErrorBus, SCHOOL
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.MISMATCH)
    return topology


def initial_model(checkpoint, requested, historical_loader):
    """Default retains imported weights; another structure starts a fresh student."""
    if requested is None:
        result = historical_loader(checkpoint)
        topology = resolve_topology(result[2])
        validate_parameter_shapes(result[0], topology, len(result[3]["tokens"]))
        return (*result, topology, {"origin": "historical-checkpoint"})
    # Read source metadata without constructing the historical model or changing RNG.
    import torch
    payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    inherited = resolve_topology(payload["config"])
    if requested == inherited:
        return initial_model(checkpoint, None, historical_loader)
    config = {**payload["config"], "layers": requested.layers,
              "heads": requested.heads, "width": requested.width,
              "ffn_dimension": requested.ffn_dimension, "context": requested.context}
    config.pop("expansion", None)
    parameters, optimizer = create_student(requested, len(payload["graph"]["tokens"]),
        seed=INITIALIZATION_SEED, optimizer_config=payload["optimizer"]["param_groups"][0])
    config["precision"] = "fp32"
    # The answer ABI is semantic data, independent of structural dimensions.
    answer_ids = [payload["graph"]["tokens"].index(symbol) for symbol in (
        "cogal.value.false", "cogal.value.true", "micro.state.UNKNOWN",
        "micro.state.CONFLICT", "micro.state.AMBIGUOUS")]
    return (parameters, optimizer, config, payload["graph"], answer_ids,
            requested, {"origin": "fresh-model", "seed": INITIALIZATION_SEED})


def topology_for_checkpoint(receipt):
    """Historical metadata stays readable; typed runs bind every new bundle."""
    record = receipt.get("model_topology")
    return resolve_topology(receipt["config"], record) if record is not None else None


def operator_topology(run_dir, *, resume, requested):
    """Validate operator selection before source preparation and allocation."""
    from .model_topology_v2 import ModelTopologySpecV2
    if isinstance(requested, ModelTopologySpecV2):
        from ..errors import ErrorBus, SCHOOL
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.MISMATCH, reason="v2-runtime-not-yet-integrated")
    if resume:
        from ..state_dag import read_current
        return inspect_resume_topology(run_dir, read_current(run_dir), requested)
    if requested is not None and not isinstance(requested, ModelTopologySpec):
        from ..errors import ErrorBus, SCHOOL
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    return requested
