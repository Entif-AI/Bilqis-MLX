"""Immutable structural model identity for one Bilqis run.

Topology deliberately excludes semantic release, provider and checkpoint identity.
It describes only the tensor geometry needed to reconstruct a student.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Mapping

from bilqis_mlx.errors import ErrorBus, SCHOOL


SCHEMA = "bilqis.mlx.model-topology/v1"
DEFAULT_OPTIMIZER = MappingProxyType({
    "learning_rate": 0.0003,
    "betas": (0.9, 0.95),
    "eps": 1e-8,
    "weight_decay": 0.1,
})


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class ModelTopologySpec:
    """Version-one structural contract; fields are all exact tensor dimensions."""

    layers: int
    heads: int
    width: int
    ffn_dimension: int
    context: int

    def __post_init__(self) -> None:
        values = asdict(self)
        if (any(type(value) is not int or value <= 0 for value in values.values()) or
                self.width % self.heads != 0):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical({"schema": SCHEMA, **asdict(self)}).encode()).hexdigest()

    def to_record(self) -> dict:
        return {"schema": SCHEMA, **asdict(self), "digest": self.digest}

    record = to_record

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> "ModelTopologySpec":
        fields = ("layers", "heads", "width", "ffn_dimension", "context")
        if not isinstance(record, Mapping) or set(record) != {"schema", "digest", *fields}:
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.RECORD_INVALID)
        if record.get("schema") != SCHEMA:
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.RECORD_INVALID)
        try:
            topology = cls(**{field: record[field] for field in fields})
        except (KeyError, TypeError):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.RECORD_INVALID)
        if record.get("digest") != topology.digest:
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.RECORD_INVALID)
        return topology


# Exact read-only topology of the pinned historical parent checkpoint.
CURRENT_DEFAULT_TOPOLOGY = ModelTopologySpec(
    layers=6, heads=24, width=384, ffn_dimension=1536, context=96,
)


def topology_from_config(config: Mapping[str, object]) -> ModelTopologySpec:
    """Translate the historical model config once; reject partial or coerced input."""
    if not isinstance(config, Mapping):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    try:
        width = config["width"]
        ffn_dimension = config.get("ffn_dimension")
        expansion = config.get("expansion")
        if type(width) is not int:
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
        if ffn_dimension is None:
            if type(expansion) is not int:
                ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
            ffn_dimension = width * expansion
        if type(ffn_dimension) is not int or (
                expansion is not None and (type(expansion) is not int or
                                           ffn_dimension != width * expansion)):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
        return ModelTopologySpec(
            layers=config["layers"], heads=config["heads"], width=width,
            ffn_dimension=ffn_dimension, context=config["context"],
        )
    except KeyError:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def resolve_topology(config: Mapping[str, object], record: Mapping[str, object] | None = None,
                     requested: ModelTopologySpec | None = None) -> ModelTopologySpec:
    """Resolve one topology before allocation or checkpoint handling.

    Existing runs receive their persisted record; historical compatibility runs
    derive the immutable default from their saved model configuration.
    """
    if requested is not None and not isinstance(requested, ModelTopologySpec):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    derived = topology_from_config(config)
    persisted = ModelTopologySpec.from_record(record) if record is not None else None
    if persisted is not None and persisted != derived:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.MISMATCH)
    if requested is not None and requested != (persisted or derived):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.MISMATCH)
    return persisted or requested or derived


def expected_parameter_shapes(topology: ModelTopologySpec, vocab_size: int) -> dict[str, tuple[int, ...]]:
    if type(vocab_size) is not int or vocab_size <= 0:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    expected = {
        "embedding.weight": (vocab_size, topology.width),
        "position.weight": (topology.context, topology.width),
        "norm.weight": (topology.width,),
    }
    for index in range(topology.layers):
        prefix = f"blocks.{index}."
        expected.update({
            prefix + "n1.weight": (topology.width,),
            prefix + "n2.weight": (topology.width,),
            prefix + "qkv.weight": (3 * topology.width, topology.width),
            prefix + "proj.weight": (topology.width, topology.width),
            prefix + "up.weight": (topology.ffn_dimension, topology.width),
            prefix + "down.weight": (topology.width, topology.ffn_dimension),
        })
    return expected


def validate_parameter_shapes(parameters: Mapping[str, object], topology: ModelTopologySpec,
                              vocab_size: int) -> None:
    """Fail before runtime use when a checkpoint's tensors disagree with topology."""
    expected = expected_parameter_shapes(topology, vocab_size)
    if not isinstance(parameters, Mapping) or set(parameters) != set(expected):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID)
    try:
        actual = {name: tuple(value.shape) for name, value in parameters.items()}
    except AttributeError:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID)
    if actual != expected:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID)


def create_student(topology: ModelTopologySpec, vocab_size: int, *, seed: int,
                   optimizer_config: Mapping[str, object] | None = None):
    """Create a deterministic disposable FP32 student and its zeroed AdamW state.

    This is construction only. It neither reads nor changes a retained student.
    """
    if type(seed) is not int:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    expected = expected_parameter_shapes(topology, vocab_size)
    options = dict(DEFAULT_OPTIMIZER)
    if optimizer_config is not None:
        if not isinstance(optimizer_config, Mapping):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
        options.update(optimizer_config)
        if "lr" in optimizer_config:
            options["learning_rate"] = optimizer_config["lr"]
    try:
        learning_rate = float(options["learning_rate"])
        betas = tuple(options["betas"])
        eps = float(options["eps"])
        weight_decay = float(options["weight_decay"])
        if (len(betas) != 2 or not 0 < learning_rate or not 0 < eps or
                not 0 <= weight_decay or any(not 0 < float(beta) < 1 for beta in betas)):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)

    import mlx.core as mx
    import mlx.optimizers as optim
    import numpy as np

    rng = np.random.default_rng(seed)
    parameters = {}
    for name, shape in expected.items():
        if name.endswith("n1.weight") or name.endswith("n2.weight") or name == "norm.weight":
            array = np.ones(shape, dtype=np.float32)
        else:
            array = rng.normal(0.0, 0.02, size=shape).astype(np.float32)
        parameters[name] = mx.array(array, dtype=mx.float32)
    optimizer = optim.AdamW(learning_rate=learning_rate, betas=list(betas), eps=eps,
                            weight_decay=weight_decay, bias_correction=True)
    optimizer.state = {
        "step": mx.array(0, dtype=mx.uint64),
        "learning_rate": mx.array(learning_rate, dtype=mx.float32),
        **{name: {"m": mx.zeros(shape, dtype=mx.float32),
                  "v": mx.zeros(shape, dtype=mx.float32)}
           for name, shape in expected.items()},
    }
    mx.eval(parameters, optimizer.state)
    validate_parameter_shapes(parameters, topology, vocab_size)
    return parameters, optimizer
