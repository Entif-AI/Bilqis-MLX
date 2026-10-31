"""Shared fixtures extracted structurally from test_block_attnres.py."""
from dataclasses import replace
import math
import unittest
import mlx.core as mx
import numpy as np
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_plasticity import AdapterParameters, adapter_forward
from bilqis_mlx.learning.frame_embeddings import FeatureRequest
from bilqis_mlx.learning.tests.test_frame_embeddings import _context_for
from bilqis_mlx.semantics.tests.test_atlas_features import _features as _atlas_features
from bilqis_mlx.semantics.frame_schema import ConceptRef
from bilqis_mlx.runtime.block_attnres import (
    DepthFrameFeatures, DepthParameterView, DepthSummary, PARAMETER_SHAPES,
    _DepthFeatureValues, _depth_components, _group_boundary_numerical,
    depth_parameter_view, depth_select, depth_select_with_diagnostics,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
    initialize_bamf_parameter,
)

RELEASE = "a" * 64

EVIDENCE = "b" * 64

def _array(values):
    return mx.array(np.asarray(values, dtype=np.float32))

def _hidden(values):
    values = np.asarray(values, dtype=np.float32)
    hidden = np.zeros((*values.shape, 768), dtype=np.float32)
    hidden[..., 0] = values
    hidden[..., 1] = values * 0.5 + 1
    hidden[..., 2] = values * -0.25 + 2
    return _array(hidden)

def _params(boundary=1):
    rng = np.random.default_rng(451)
    spec = ModelTopologySpecV2()
    extents = GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)
    ledger = {row.name: row for row in expected_bamf_shapes(spec, extents)}
    parameters = {
        "norm": _array(initialize_bamf_parameter(
            ledger["depth.norm"], run_seed=0)),
        "gate_vector": _array(initialize_bamf_parameter(
            ledger[f"depth.gate.{boundary - 1}.vector"], run_seed=0)),
        "gate_bias": _array(initialize_bamf_parameter(
            ledger[f"depth.gate.{boundary - 1}.bias"], run_seed=0)),
    }
    for name in ("query", "key", "value", "output"):
        shape = ledger[f"depth.{name}"].shape
        parameters[name] = _array(rng.normal(0, 0.1, shape))
    return parameters

def _features(boundary=1):
    return _DepthFeatureValues(
        _hidden([[0.1, 0.2, 0.3], [0.2, 0.1, 0.4]]),
        _hidden([[0.3, 0.1, 0.2], [0.2, 0.4, 0.1]]),
        RELEASE, EVIDENCE, boundary)

def _released_features(boundary=1):
    features = _atlas_features()
    ref = ConceptRef("urn:concept:A", features.semantic_release, 11,
                     ("urn:type:Entity",), "fixture:source")
    requests = []
    for batch in range(2):
        row = []
        for position in range(3):
            context = _context_for(ref, f"fixture:depth:{batch}:{position}")
            row.append(tuple(FeatureRequest.from_context(context, "frame:0", "source:member:"+role)
                             for role in ("left", "right")))
        requests.append(tuple(row))
    return DepthFrameFeatures(tuple(requests), features, boundary)

def _summaries(boundary=1):
    values = (
        _hidden([[1, 2, 3], [2, 3, 1]]),
        _hidden([[3, 1, 2], [1, 2, 4]]),
        _hidden([[2, 4, 1], [4, 1, 2]]),
        _hidden([[4, 3, 2], [2, 1, 3]]),
    )
    return tuple(
        DepthSummary(name, layer, values[index])
        for index, (name, layer) in enumerate(
            (("h0", 0), ("g1", 4), ("g2", 8), ("g3", 12))
        ) if index <= boundary)

def _numpy_oracle(current, summaries, features, params):
    """Independent NumPy FP32 implementation, not a call to the MLX selector."""
    h = np.asarray(current)
    gamma = np.asarray(params["norm"])
    seed = np.asarray(features.frame_seed)
    types = np.asarray(features.type_role)
    q_weight = np.asarray(params["query"])
    k_weight = np.asarray(params["key"])
    v_weight = np.asarray(params["value"])
    out_weight = np.asarray(params["output"])
    gate_vector = np.asarray(params["gate_vector"])
    gate_bias = float(np.asarray(params["gate_bias"])[0])

    def rms(values):
        return values / np.sqrt(np.mean(values * values, axis=-1, keepdims=True)
                                + np.float32(1e-5)) * gamma

    q = rms(h + seed) @ q_weight.T
    sources = [np.asarray(item.hidden) for item in summaries]
    keys = np.stack([rms(item + types) @ k_weight.T for item in sources], axis=2)
    values = np.stack([item @ v_weight.T for item in sources], axis=2)
    scores = np.sum(q[:, :, None] * keys, axis=-1) / np.float32(np.sqrt(128))
    weights = np.exp(scores - scores.max(axis=-1, keepdims=True))
    weights /= weights.sum(axis=-1, keepdims=True)
    mix = np.sum(weights[:, :, :, None] * values, axis=2)
    logits = np.sum(rms(h) * gate_vector, axis=-1, keepdims=True) + gate_bias
    gate = np.float32(0.1) / (1 + np.exp(-logits))
    return h + gate * (mix @ out_weight.T), weights, gate

if __name__ == "__main__":
    unittest.main()
