"""Frozen BAMF architecture identity, independent of generation extents."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from enum import Enum
import hashlib
import json
import math
from typing import Mapping

from bilqis_mlx.errors import ErrorBus, SCHOOL
from .model_topology import DEFAULT_OPTIMIZER, ModelTopologySpec, SCHEMA as LEGACY_SCHEMA


SCHEMA = "bilqis.mlx.model-topology/v2"
BAMF_ARCHITECTURE_ID = "bamf-atlas-v2"
LEGACY_ARCHITECTURE_ID = "bilqis.mlx.causal-tied-fp32/v1"
IDENTITY_ESTABLISHED_AGE = 8


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ModelTopologySpecV2:
    """One selected production geometry; mutable bank extents live elsewhere."""

    architecture_id: str = BAMF_ARCHITECTURE_ID
    layers: int = 12
    width: int = 768
    ffn_dimension: int = 3072
    query_heads: int = 16
    kv_heads: int = 8
    head_dimension: int = 24
    context: int = 1024
    rope_dimensions: int = 24
    rope_base: int = 10000
    rope_scale: float = 1.0
    rope_traditional: bool = False
    rms_norm_epsilon: float = 1e-5
    ffn_activation: str = "squared-relu"
    convolution: str = "causal-depthwise"
    convolution_kernel: int = 3
    projection_bias: bool = False
    dtype: str = "float32"
    depth_groups: int = 3
    adapter_rank: int = 8
    semantic_bank_rows: int = 8192
    motif_page_rows: int = 16384
    max_motif_pages: int = 4
    initializer: str = "sha256-pcg64-v2"
    default_run_seed: int = 0
    modules: tuple[str, ...] = (
        "factorized-embeddings", "frame-encoder", "causal-convolution-gqa",
        "block-attention-residual", "motif-memory", "plastic-adapters",
        "constituent-refinement", "typed-readout",
    )

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not type(field.default) or value != field.default:
                ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID, field=field.name)

    @property
    def shape_policy_digest(self) -> str:
        return _digest({
            "schema": "bilqis.mlx.bamf-shape-policy/v1",
            "semantic_bank_rows": self.semantic_bank_rows,
            "semantic_index": "bank*8192+row",
            "semantic_growth": "append-bank-at-admission",
            "motif_page_rows": self.motif_page_rows,
            "max_motif_pages": self.max_motif_pages,
            "motif_growth": "append-page-on-allocation",
        })

    @property
    def digest(self) -> str:
        return _digest({"schema": SCHEMA, **asdict(self),
                        "shape_policy_digest": self.shape_policy_digest})

    def to_record(self) -> dict:
        record = asdict(self)
        record["modules"] = list(self.modules)
        return {"schema": SCHEMA, **record, "shape_policy_digest": self.shape_policy_digest,
                "digest": self.digest}

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> "ModelTopologySpecV2":
        names = {field.name for field in fields(cls)}
        if (not isinstance(record, Mapping) or
                set(record) != names | {"schema", "shape_policy_digest", "digest"} or
                record.get("schema") != SCHEMA or type(record.get("modules")) is not list):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.RECORD_INVALID)
        values = {name: record[name] for name in names}
        values["modules"] = tuple(values["modules"])
        topology = cls(**values)
        if (record.get("shape_policy_digest") != topology.shape_policy_digest or
                record.get("digest") != topology.digest):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.RECORD_INVALID)
        return topology


def deserialize_topology(record: Mapping[str, object]) -> ModelTopologySpec | ModelTopologySpecV2:
    """Select by persisted schema, never by a caller's preferred architecture."""
    if not isinstance(record, Mapping):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.RECORD_INVALID)
    if record.get("schema") == LEGACY_SCHEMA:
        return ModelTopologySpec.from_record(record)
    if record.get("schema") == SCHEMA:
        return ModelTopologySpecV2.from_record(record)
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.RECORD_INVALID)


def initializer_seed(run_seed: int, parameter_path: str, row_id: str = "") -> int:
    """Derive an order-independent PCG64 seed from a stable path and row identity."""
    if (type(run_seed) is not int or not isinstance(parameter_path, str) or
            not parameter_path or not isinstance(row_id, str)):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    content = f"bamf.init.v2|{run_seed}|{parameter_path}|{row_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(content).digest()[:8], "little")


class ParameterGroup(str, Enum):
    FAST = "FAST"
    SLOW = "SLOW"
    IDENTITY_ROW_AGE = "IDENTITY_ROW_AGE"


class Initializer(str, Enum):
    MATRIX = "M"
    EMBEDDING = "E"
    FEATURE_TABLE = "FEATURE_TABLE"
    ZERO = "ZERO"
    ONE = "ONE"
    CONV_IDENTITY = "CONV_IDENTITY"
    MINUS_TWO = "MINUS_TWO"
    MINUS_FOUR = "MINUS_FOUR"
    LOG_ONE_NINTH = "LOG_ONE_NINTH"
    IDENTITY_BANK = "IDENTITY_BANK"
    MOTIF_PAGE = "MOTIF_PAGE"


@dataclass(frozen=True)
class GenerationExtents:
    """Generation-specific table counts and upstream content bindings."""

    semantic_bank_count: int
    motif_page_count: int
    active_semantic_digest: str
    motif_key_map_digest: str
    factor_map_digest: str

    def __post_init__(self) -> None:
        if (type(self.semantic_bank_count) is not int or self.semantic_bank_count < 1 or
                type(self.motif_page_count) is not int or not 1 <= self.motif_page_count <= 4):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
        for value in (self.active_semantic_digest, self.motif_key_map_digest, self.factor_map_digest):
            if (not isinstance(value, str) or len(value) != 64 or
                    any(character not in "0123456789abcdef" for character in value)):
                ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)

    @property
    def digest(self) -> str:
        return _digest({"schema": "bilqis.mlx.generation-extents/v1", **asdict(self)})


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    shape: tuple[int, ...]
    initializer: Initializer
    group: ParameterGroup
    decay: bool
    dtype: str = "float32"

    def __post_init__(self) -> None:
        if (not isinstance(self.name, str) or not self.name or type(self.shape) is not tuple or
                not self.shape or any(type(value) is not int or value <= 0 for value in self.shape) or
                type(self.initializer) is not Initializer or type(self.group) is not ParameterGroup or
                type(self.decay) is not bool or self.dtype != "float32"):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
        if ((self.initializer is Initializer.MATRIX and len(self.shape) != 2) or
                (self.initializer is Initializer.CONV_IDENTITY and
                 (len(self.shape) != 2 or self.shape[1] != 3)) or
                (self.initializer is Initializer.FEATURE_TABLE and
                 (len(self.shape) != 2 or self.shape[0] < 2)) or
                (self.initializer is Initializer.IDENTITY_BANK and self.shape != (8192, 768)) or
                (self.initializer is Initializer.MOTIF_PAGE and self.shape != (16384, 128))):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def expected_bamf_shapes(spec: ModelTopologySpecV2,
                         extents: GenerationExtents) -> tuple[ParameterSpec, ...]:
    """Expand the normative tensor ledger in stable serialization order."""
    if type(spec) is not ModelTopologySpecV2 or type(extents) is not GenerationExtents:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    entries: list[ParameterSpec] = []
    slow, fast, age = ParameterGroup.SLOW, ParameterGroup.FAST, ParameterGroup.IDENTITY_ROW_AGE
    M, E, Z, O = Initializer.MATRIX, Initializer.EMBEDDING, Initializer.ZERO, Initializer.ONE

    def add(name, shape, initializer, group=slow, decay=True):
        entries.append(ParameterSpec(name, shape, initializer, group, decay))

    for bank in range(extents.semantic_bank_count):
        add(f"identity.bank.{bank}", (8192, 768), Initializer.IDENTITY_BANK, age)
    for kind in ("type", "role", "schema"):
        add(f"features.{kind}", (512, 128), Initializer.FEATURE_TABLE)
    for kind in ("type", "role", "schema"):
        add(f"features.project_{kind}", (768, 128), M)
    add("features.project_graph", (768, 64), M)
    add("features.gates", (4,), Initializer.MINUS_TWO, decay=False)
    add("features.local_slot", (16, 768), E)
    add("features.norm", (768,), O, decay=False)
    add("frame.query_schema", (192, 128), M)
    for kind in ("key", "value"):
        add(f"frame.member_{kind}", (192, 768), M)
    for kind in ("query", "key", "value", "output"):
        add(f"frame.interact_{kind}", (192, 192), M)
    add("frame.interact_norm", (192,), O, decay=False)
    add("frame.project_output", (768, 192), M)
    add("frame.project_summary", (768, 128), M)
    add("frame.pool_gate", (1,), Initializer.MINUS_TWO, decay=False)
    add("frame.empty_seed", (768,), E)
    add("frame.norm", (768,), O, decay=False)
    for index in range(spec.layers):
        prefix = f"blocks.{index}."
        for name in ("attn_norm", "ffn_norm"):
            add(prefix + name, (768,), O, decay=False)
        add(prefix + "query", (384, 768), M)
        add(prefix + "key", (192, 768), M)
        add(prefix + "value", (192, 768), M)
        add(prefix + "output", (768, 384), M)
        add(prefix + "conv_q", (384, 3), Initializer.CONV_IDENTITY)
        add(prefix + "conv_k", (192, 3), Initializer.CONV_IDENTITY)
        add(prefix + "conv_v", (192, 3), Initializer.CONV_IDENTITY)
        add(prefix + "ffn_in", (3072, 768), M)
        add(prefix + "ffn_out", (768, 3072), M)
    add("depth.norm", (768,), O, decay=False)
    for kind in ("query", "key", "value"):
        add(f"depth.{kind}", (128, 768), M)
    add("depth.output", (768, 128), M)
    for index in range(spec.depth_groups):
        add(f"depth.gate.{index}.vector", (768,), Z)
        add(f"depth.gate.{index}.bias", (1,), Initializer.LOG_ONE_NINTH, decay=False)
    for page in range(extents.motif_page_count):
        add(f"motif.page.{page}", (16384, 128), Initializer.MOTIF_PAGE, fast)
    for index in range(2):
        prefix = f"motif.site.{index}."
        add(prefix + "projection", (768, 128), M, fast)
        add(prefix + "norm", (768,), O, fast, False)
        add(prefix + "gate_hidden", (768,), Z, fast)
        add(prefix + "gate_feature", (128,), Z, fast)
        add(prefix + "bias", (1,), Initializer.MINUS_FOUR, fast, False)
    for index in range(spec.depth_groups):
        prefix = f"plastic.group.{index}."
        add(prefix + "norm", (768,), O, fast, False)
        add(prefix + "A", (8, 768), M, fast)
        add(prefix + "B", (768, 8), Z, fast)
    add("refine.norm", (768,), O, decay=False)
    for kind in ("query", "key", "value"):
        add(f"refine.{kind}", (192, 768), M)
    add("refine.output", (768, 192), M)
    add("refine.gate_vector", (768,), Z)
    add("refine.bias", (1,), Initializer.LOG_ONE_NINTH, decay=False)
    add("refine.route", (3, 768), M)
    add("refine.route_bias", (3,), Z, decay=False)
    for kind in ("state", "output"):
        add(f"readout.{kind}_norm", (768,), O, decay=False)
    for kind in ("query", "key", "value"):
        add(f"readout.{kind}", (192, 768), M)
    add("readout.output", (768, 192), M)
    add("readout.feedback", (768, 768), M)
    add("readout.role_query", (128, 768), M)
    for kind, count in (("control", 4), ("epistemic", 5)):
        add(f"readout.{kind}", (count, 768), M)
        add(f"readout.{kind}_bias", (count,), Z, decay=False)
    for kind in ("impact", "exigency", "novelty"):
        add(f"readout.salience.{kind}", (5, 768), M)
        add(f"readout.salience_bias.{kind}", (5,), Z, decay=False)
    return tuple(entries)


def initialize_bamf_parameter(parameter: ParameterSpec, *, run_seed: int):
    """Initialize one parameter. Identity and motif tables start unallocated."""
    import numpy as np

    if type(parameter) is not ParameterSpec:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    seed = initializer_seed(run_seed, parameter.name)
    init = parameter.initializer
    if init in (Initializer.ZERO, Initializer.IDENTITY_BANK, Initializer.MOTIF_PAGE):
        return np.zeros(parameter.shape, dtype=np.float32)
    if init == Initializer.ONE:
        return np.ones(parameter.shape, dtype=np.float32)
    if init == Initializer.CONV_IDENTITY:
        value = np.zeros(parameter.shape, dtype=np.float32)
        value[:, 2] = 1.0
        return value
    if init in (Initializer.MINUS_TWO, Initializer.MINUS_FOUR, Initializer.LOG_ONE_NINTH):
        scalar = {Initializer.MINUS_TWO: -2.0, Initializer.MINUS_FOUR: -4.0,
                  Initializer.LOG_ONE_NINTH: math.log(1.0 / 9.0)}[init]
        return np.full(parameter.shape, scalar, dtype=np.float32)
    scale = 1.0 / math.sqrt(parameter.shape[-1]) if init == Initializer.MATRIX else 0.02
    value = (np.random.Generator(np.random.PCG64(seed)).standard_normal(parameter.shape) * scale).astype(np.float32)
    if init == Initializer.FEATURE_TABLE:
        value[1] = 0
    return value


def initialize_bamf_row(parameter: ParameterSpec, *, run_seed: int, row_id: str, factor=None):
    """Compute a row value; source admission and allocation remain upstream."""
    import numpy as np

    if (type(parameter) is not ParameterSpec or len(parameter.shape) != 2 or
            not isinstance(row_id, str) or not row_id):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    seed = initializer_seed(run_seed, parameter.name, row_id)
    noise = np.random.Generator(np.random.PCG64(seed)).standard_normal(parameter.shape[1])
    if parameter.initializer is Initializer.IDENTITY_BANK:
        try:
            factors = np.asarray(factor)
            valid = (factors.dtype == np.float32 and factors.shape == (parameter.shape[1],)
                     and bool(np.isfinite(factors).all()))
        except (TypeError, ValueError):
            valid = False
        if not valid:
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
        return (factors.astype(np.float64) + noise * 0.001).astype(np.float32)
    if parameter.initializer is Initializer.MOTIF_PAGE and factor is None:
        return (noise * 0.02).astype(np.float32)
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def validate_bamf_parameters(spec: ModelTopologySpecV2, extents: GenerationExtents,
                             parameters: Mapping[str, object]) -> None:
    """Check exact names, shapes and FP32 arrays against the declared ledger."""
    import mlx.core as mx

    declared = expected_bamf_shapes(spec, extents)
    if not isinstance(parameters, Mapping) or set(parameters) != {item.name for item in declared}:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID)
    for item in declared:
        value = parameters[item.name]
        if not isinstance(value, mx.array) or value.dtype != mx.float32 or tuple(value.shape) != item.shape:
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID, parameter=item.name)


def create_unbound_bamf_state(spec: ModelTopologySpecV2, extents: GenerationExtents,
                              *, run_seed: int):
    """Construct disposable unbound tensors and zero moments, without admitting rows.

    Source-bound identity and allocated motif rows require their respective
    owners. This state is not a releasable model or a trainable optimizer.
    """
    import mlx.core as mx

    declared = expected_bamf_shapes(spec, extents)
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
        "run_seed": run_seed,
        "parameter_count": sum(math.prod(item.shape) for item in declared),
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
                        "initializer": item.initializer.value, "group": item.group.value,
                        "decay": item.decay,
                        "storage_keys": {part: bamf_storage_key(item.name, part)
                                         for part in ("weight", "m", "v")}}
                       for item in declared],
        "serialization_schema": "bilqis.mlx.bamf-named-tensors/v1",
        "constants": ["sinusoidal_positions", "sha256_literal_features", "visibility_masks"],
    }
    return parameters, state, manifest


def bamf_storage_key(parameter_name: str, part: str) -> str:
    """Encode the stable parameter path without relying on registry position."""
    if not isinstance(parameter_name, str) or not parameter_name or part not in ("weight", "m", "v"):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    try:
        encoded = parameter_name.encode("utf-8").hex()
    except UnicodeEncodeError:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    return f"p{encoded}_{part}"


def bamf_serialization_arrays(spec: ModelTopologySpecV2, extents: GenerationExtents,
                              parameters: Mapping[str, object], state: Mapping[str, object]) -> dict:
    """Produce stable path-derived serialization keys after validating the tree."""
    import mlx.core as mx

    declared = expected_bamf_shapes(spec, extents)
    validate_bamf_parameters(spec, extents, parameters)
    if not isinstance(state, Mapping) or set(state) != {"step", "learning_rate", *(x.name for x in declared)}:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID)
    step, learning_rate = state["step"], state["learning_rate"]
    if (not isinstance(step, mx.array) or step.dtype != mx.uint64 or tuple(step.shape) != () or
            not isinstance(learning_rate, mx.array) or learning_rate.dtype != mx.float32 or
            tuple(learning_rate.shape) != ()):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID)
    arrays = {}
    for item in declared:
        moments = state[item.name]
        if not isinstance(moments, Mapping) or set(moments) != {"m", "v"}:
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID, parameter=item.name)
        for part, value in (("weight", parameters[item.name]), ("m", moments["m"]), ("v", moments["v"])):
            if not isinstance(value, mx.array) or value.dtype != mx.float32 or tuple(value.shape) != item.shape:
                ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID, parameter=item.name)
            arrays[bamf_storage_key(item.name, part)] = value
    arrays["adamw_global_step"] = step
    arrays["adamw_learning_rate"] = learning_rate
    return arrays


def bamf_deserialize_arrays(spec: ModelTopologySpecV2, extents: GenerationExtents,
                            arrays: Mapping[str, object]) -> tuple[dict, dict]:
    """Reconstruct an unbound tree only from its complete declared array set."""
    declared = expected_bamf_shapes(spec, extents)
    expected = {bamf_storage_key(item.name, part)
                for item in declared for part in ("weight", "m", "v")}
    expected.update(("adamw_global_step", "adamw_learning_rate"))
    if not isinstance(arrays, Mapping) or set(arrays) != expected:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID)
    parameters = {item.name: arrays[bamf_storage_key(item.name, "weight")] for item in declared}
    state = {"step": arrays["adamw_global_step"], "learning_rate": arrays["adamw_learning_rate"],
             **{item.name: {"m": arrays[bamf_storage_key(item.name, "m")],
                            "v": arrays[bamf_storage_key(item.name, "v")]} for item in declared}}
    bamf_serialization_arrays(spec, extents, parameters, state)
    return parameters, state
