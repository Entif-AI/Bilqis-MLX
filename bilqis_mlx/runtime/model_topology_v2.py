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
EXTENTS_SCHEMA = "bilqis.mlx.generation-extents/v1"
PROVENANCE_SCHEMA = "bilqis.mlx.generation-provenance/v1"
IDENTITY_ESTABLISHED_AGE = 8
ADAPTER_FACTOR_SUFFIXES = frozenset(("A", "B"))


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


# Fixed structural dimensions belong to the selected topology and tensor ledger.
MATRIX_RANK = 2
FEATURE_NONE_ROW = 1
FEATURE_RESERVED_ROWS = FEATURE_NONE_ROW + 1
FEATURE_ROWS = 512
FEATURE_DIM = 128
GRAPH_FEATURE_DIM = 64
MOTIF_CHANNELS = 128
SHA256_HEX_LENGTH = hashlib.sha256().digest_size * 2
IDENTITY_BANK_SHAPE = (ModelTopologySpecV2.semantic_bank_rows, ModelTopologySpecV2.width)
MOTIF_PAGE_SHAPE = (ModelTopologySpecV2.motif_page_rows, MOTIF_CHANNELS)


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


class ParameterCategory(str, Enum):
    DENSE_MATRICES = "DENSE_MATRICES"
    SEMANTIC_TABLES = "SEMANTIC_TABLES"
    MOTIF_TABLES = "MOTIF_TABLES"
    ADAPTER_MATRICES = "ADAPTER_MATRICES"
    AUXILIARY = "AUXILIARY"


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
                type(self.motif_page_count) is not int or
                not 1 <= self.motif_page_count <= ModelTopologySpecV2.max_motif_pages):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
        for value in (self.active_semantic_digest, self.motif_key_map_digest, self.factor_map_digest):
            if (not isinstance(value, str) or len(value) != SHA256_HEX_LENGTH or
                    any(character not in "0123456789abcdef" for character in value)):
                ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)

    @property
    def digest(self) -> str:
        return _digest({"schema": EXTENTS_SCHEMA, **asdict(self)})

    def to_record(self) -> dict:
        return {"schema": EXTENTS_SCHEMA, **asdict(self), "digest": self.digest}

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> "GenerationExtents":
        return _generation_from_record(cls, record, EXTENTS_SCHEMA)


@dataclass(frozen=True)
class GenerationProvenance:
    """Source/release and teacher bindings; validation does not grant admission."""

    source_identity: str
    release_digest: str
    teacher_identity: str
    teacher_epoch: int

    def __post_init__(self) -> None:
        for identity in (self.source_identity, self.teacher_identity):
            if not isinstance(identity, str) or not identity.strip():
                ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
        if (not isinstance(self.release_digest, str) or len(self.release_digest) != SHA256_HEX_LENGTH or
                any(character not in "0123456789abcdef" for character in self.release_digest) or
                type(self.teacher_epoch) is not int or self.teacher_epoch < 0):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)

    @property
    def digest(self) -> str:
        return _digest({"schema": PROVENANCE_SCHEMA, **asdict(self)})

    def to_record(self) -> dict:
        return {"schema": PROVENANCE_SCHEMA, **asdict(self), "digest": self.digest}

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> "GenerationProvenance":
        return _generation_from_record(cls, record, PROVENANCE_SCHEMA)


def _generation_from_record(cls, record: Mapping[str, object], schema: str):
    names = {field.name for field in fields(cls)}
    if (not isinstance(record, Mapping) or set(record) != names | {"schema", "digest"} or
            record.get("schema") != schema):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.RECORD_INVALID)
    generation = cls(**{name: record[name] for name in names})
    if record.get("digest") != generation.digest:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.RECORD_INVALID)
    return generation


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
        if ((self.initializer is Initializer.MATRIX and len(self.shape) != MATRIX_RANK) or
                (self.initializer is Initializer.CONV_IDENTITY and
                 (len(self.shape) != MATRIX_RANK or self.shape[1] != ModelTopologySpecV2.convolution_kernel)) or
                (self.initializer is Initializer.FEATURE_TABLE and
                 (len(self.shape) != MATRIX_RANK or self.shape[0] < FEATURE_RESERVED_ROWS)) or
                (self.initializer is Initializer.IDENTITY_BANK and self.shape != IDENTITY_BANK_SHAPE) or
                (self.initializer is Initializer.MOTIF_PAGE and self.shape != MOTIF_PAGE_SHAPE)):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)

    @property
    def parameter_count(self) -> int:
        return math.prod(self.shape)

    @property
    def category(self) -> ParameterCategory:
        if self.initializer is Initializer.IDENTITY_BANK:
            return ParameterCategory.SEMANTIC_TABLES
        if self.initializer is Initializer.MOTIF_PAGE:
            return ParameterCategory.MOTIF_TABLES
        suffix = self.name.rsplit(".", 1)[-1]
        if self.name.startswith("blocks.") and suffix in (
                "query", "key", "value", "output", "ffn_in", "ffn_out"):
            return ParameterCategory.DENSE_MATRICES
        if self.name.startswith("plastic.group.") and suffix in ADAPTER_FACTOR_SUFFIXES:
            return ParameterCategory.ADAPTER_MATRICES
        return ParameterCategory.AUXILIARY


@dataclass(frozen=True)
class ParameterCensus:
    topology_digest: str
    extents_digest: str
    parameters: tuple[ParameterSpec, ...]

    def __post_init__(self) -> None:
        if (type(self.parameters) is not tuple or not self.parameters or
                any(type(item) is not ParameterSpec for item in self.parameters) or
                len({item.name for item in self.parameters}) != len(self.parameters)):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
        for value in (self.topology_digest, self.extents_digest):
            if (not isinstance(value, str) or len(value) != SHA256_HEX_LENGTH or
                    any(character not in "0123456789abcdef" for character in value)):
                ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)

    @property
    def total(self) -> int:
        return sum(item.parameter_count for item in self.parameters)

    @property
    def subtotals(self) -> dict[ParameterCategory, int]:
        result = dict.fromkeys(ParameterCategory, 0)
        for item in self.parameters:
            result[item.category] += item.parameter_count
        return result

    def to_record(self) -> dict:
        return {
            "schema": "bilqis.mlx.bamf-parameter-census/v1",
            "topology_digest": self.topology_digest,
            "generation_extents_digest": self.extents_digest,
            "total_parameters": self.total,
            "subtotals": {kind.value: count for kind, count in self.subtotals.items()},
            "parameters": [{"name": item.name, "shape": list(item.shape),
                            "parameters": item.parameter_count, "category": item.category.value,
                            "dtype": item.dtype, "group": item.group.value}
                           for item in self.parameters],
        }
def _parameter(name, shape, initializer, group=ParameterGroup.SLOW, decay=True):
    return ParameterSpec(name, shape, initializer, group, decay)


def _input_parameters() -> tuple[ParameterSpec, ...]:
    M, E, O = Initializer.MATRIX, Initializer.EMBEDDING, Initializer.ONE
    return (
        *(_parameter(f"features.{kind}", (FEATURE_ROWS, FEATURE_DIM), Initializer.FEATURE_TABLE)
          for kind in ("type", "role", "schema")),
        *(_parameter(f"features.project_{kind}", (768, FEATURE_DIM), M)
          for kind in ("type", "role", "schema")),
        _parameter("features.project_graph", (768, GRAPH_FEATURE_DIM), M),
        _parameter("features.gates", (4,), Initializer.MINUS_TWO, decay=False),
        _parameter("features.local_slot", (16, 768), E),
        _parameter("features.norm", (768,), O, decay=False),
        _parameter("frame.query_schema", (192, 128), M),
        *(_parameter(f"frame.member_{kind}", (192, 768), M) for kind in ("key", "value")),
        *(_parameter(f"frame.interact_{kind}", (192, 192), M)
          for kind in ("query", "key", "value", "output")),
        _parameter("frame.interact_norm", (192,), O, decay=False),
        _parameter("frame.project_output", (768, 192), M),
        _parameter("frame.project_summary", (768, 128), M),
        _parameter("frame.pool_gate", (1,), Initializer.MINUS_TWO, decay=False),
        _parameter("frame.empty_seed", (768,), E),
        _parameter("frame.norm", (768,), O, decay=False),
    )


def _block_parameters(index: int) -> tuple[ParameterSpec, ...]:
    M, O = Initializer.MATRIX, Initializer.ONE
    prefix = f"blocks.{index}."
    return (
        *(_parameter(prefix + name, (768,), O, decay=False) for name in ("attn_norm", "ffn_norm")),
        _parameter(prefix + "query", (384, 768), M),
        _parameter(prefix + "key", (192, 768), M),
        _parameter(prefix + "value", (192, 768), M),
        _parameter(prefix + "output", (768, 384), M),
        _parameter(prefix + "conv_q", (384, 3), Initializer.CONV_IDENTITY),
        _parameter(prefix + "conv_k", (192, 3), Initializer.CONV_IDENTITY),
        _parameter(prefix + "conv_v", (192, 3), Initializer.CONV_IDENTITY),
        _parameter(prefix + "ffn_in", (3072, 768), M),
        _parameter(prefix + "ffn_out", (768, 3072), M),
    )


def _depth_parameters(groups: int) -> tuple[ParameterSpec, ...]:
    M, O, Z = Initializer.MATRIX, Initializer.ONE, Initializer.ZERO
    return (
        _parameter("depth.norm", (768,), O, decay=False),
        *(_parameter(f"depth.{kind}", (128, 768), M) for kind in ("query", "key", "value")),
        _parameter("depth.output", (768, 128), M),
        *(item for index in range(groups) for item in (
            _parameter(f"depth.gate.{index}.vector", (768,), Z),
            _parameter(f"depth.gate.{index}.bias", (1,), Initializer.LOG_ONE_NINTH, decay=False),
        )),
    )


def _motif_site_parameters(index: int) -> tuple[ParameterSpec, ...]:
    fast = ParameterGroup.FAST
    prefix = f"motif.site.{index}."
    return (
        _parameter(prefix + "projection", (768, 128), Initializer.MATRIX, fast),
        _parameter(prefix + "norm", (768,), Initializer.ONE, fast, False),
        _parameter(prefix + "gate_hidden", (768,), Initializer.ZERO, fast),
        _parameter(prefix + "gate_feature", (128,), Initializer.ZERO, fast),
        _parameter(prefix + "bias", (1,), Initializer.MINUS_FOUR, fast, False),
    )


def _plastic_parameters(index: int) -> tuple[ParameterSpec, ...]:
    fast = ParameterGroup.FAST
    prefix = f"plastic.group.{index}."
    return (
        _parameter(prefix + "norm", (768,), Initializer.ONE, fast, False),
        _parameter(prefix + "A", (8, 768), Initializer.MATRIX, fast),
        _parameter(prefix + "B", (768, 8), Initializer.ZERO, fast),
    )


def _output_parameters() -> tuple[ParameterSpec, ...]:
    M, O, Z = Initializer.MATRIX, Initializer.ONE, Initializer.ZERO
    return (
        _parameter("refine.norm", (768,), O, decay=False),
        *(_parameter(f"refine.{kind}", (192, 768), M) for kind in ("query", "key", "value")),
        _parameter("refine.output", (768, 192), M),
        _parameter("refine.gate_vector", (768,), Z),
        _parameter("refine.bias", (1,), Initializer.LOG_ONE_NINTH, decay=False),
        _parameter("refine.route", (3, 768), M),
        _parameter("refine.route_bias", (3,), Z, decay=False),
        *(_parameter(f"readout.{kind}_norm", (768,), O, decay=False) for kind in ("state", "output")),
        *(_parameter(f"readout.{kind}", (192, 768), M) for kind in ("query", "key", "value")),
        _parameter("readout.output", (768, 192), M),
        _parameter("readout.feedback", (768, 768), M),
        _parameter("readout.role_query", (128, 768), M),
        *(item for kind, count in (("control", 4), ("epistemic", 5)) for item in (
            _parameter(f"readout.{kind}", (count, 768), M),
            _parameter(f"readout.{kind}_bias", (count,), Z, decay=False),
        )),
        *(item for kind in ("impact", "exigency", "novelty") for item in (
            _parameter(f"readout.salience.{kind}", (5, 768), M),
            _parameter(f"readout.salience_bias.{kind}", (5,), Z, decay=False),
        )),
    )


def expected_bamf_shapes(spec: ModelTopologySpecV2,
                         extents: GenerationExtents) -> tuple[ParameterSpec, ...]:
    """Expand the normative tensor ledger in stable serialization order."""
    if type(spec) is not ModelTopologySpecV2 or type(extents) is not GenerationExtents:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    return (
        *(_parameter(f"identity.bank.{bank}", IDENTITY_BANK_SHAPE, Initializer.IDENTITY_BANK,
                     ParameterGroup.IDENTITY_ROW_AGE) for bank in range(extents.semantic_bank_count)),
        *_input_parameters(),
        *(item for index in range(spec.layers) for item in _block_parameters(index)),
        *_depth_parameters(spec.depth_groups),
        *(_parameter(f"motif.page.{page}", MOTIF_PAGE_SHAPE, Initializer.MOTIF_PAGE,
                     ParameterGroup.FAST) for page in range(extents.motif_page_count)),
        *(item for index in range(2) for item in _motif_site_parameters(index)),
        *(item for index in range(spec.depth_groups) for item in _plastic_parameters(index)),
        *_output_parameters(),
    )


def bamf_parameter_census(spec: ModelTopologySpecV2, extents: GenerationExtents) -> ParameterCensus:
    declared = expected_bamf_shapes(spec, extents)
    return ParameterCensus(spec.digest, extents.digest, declared)


def print_bamf_parameter_census(spec: ModelTopologySpecV2, extents: GenerationExtents) -> ParameterCensus:
    """Print every declared tensor, category subtotal and the exact final count."""
    census = bamf_parameter_census(spec, extents)
    for item in census.parameters:
        shape = "x".join(str(value) for value in item.shape)
        print(f"TENSOR {item.name} shape={shape} parameters={item.parameter_count} category={item.category.value}")
    for category, count in census.subtotals.items():
        print(f"SUBTOTAL {category.value} {count}")
    print(f"TOTAL_PARAMETERS {census.total}")
    return census


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
        value[FEATURE_NONE_ROW] = 0
    return value


def project_identity_source_factor(
    parameters: Mapping[str, object], *,
    type_rows: tuple[int, ...],
    type_overflow: tuple[tuple[float, ...] | None, ...],
    graph64: tuple[float, ...],
    extents: GenerationExtents,
    predecessor_feature_digest: str,
):
    """Project source-attested prospective identity features without B02 authority.

    A02 uses this read-only staging primitive before identity-row activation. The
    caller must bind the source feature plan to the accepted predecessor feature
    digest. Role/schema/local context deliberately stays outside identity seeding.
    """
    import mlx.core as mx
    import numpy as np

    if (not isinstance(parameters, Mapping)
            or not isinstance(extents, GenerationExtents)
            or not isinstance(predecessor_feature_digest, str)
            or len(predecessor_feature_digest) != SHA256_HEX_LENGTH
            or any(character not in "0123456789abcdef"
                   for character in predecessor_feature_digest)
            or extents.factor_map_digest != predecessor_feature_digest):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    expected = {
        "features.type": (FEATURE_ROWS, FEATURE_DIM),
        "features.project_type": (ModelTopologySpecV2.width, FEATURE_DIM),
        "features.project_graph": (ModelTopologySpecV2.width, GRAPH_FEATURE_DIM),
        "features.gates": (4,),
    }
    for name, shape in expected.items():
        value = parameters.get(name)
        if (not isinstance(value, mx.array) or value.dtype != mx.float32
                or value.shape != shape):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    if (not isinstance(type_rows, tuple) or not isinstance(type_overflow, tuple)
            or len(type_rows) != len(type_overflow)
            or not isinstance(graph64, tuple) or len(graph64) != GRAPH_FEATURE_DIM
            or any(type(row) is not int or not 0 <= row < FEATURE_ROWS for row in type_rows)):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    try:
        graph = np.asarray(graph64, dtype=np.float32)
    except (TypeError, ValueError, OverflowError):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    if graph.shape != (GRAPH_FEATURE_DIM,) or not np.isfinite(graph).all():
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)

    type_vectors = []
    for row, overflow in zip(type_rows, type_overflow):
        value = parameters["features.type"][row]
        if overflow is not None:
            try:
                overflow_array = np.asarray(overflow, dtype=np.float32)
            except (TypeError, ValueError, OverflowError):
                ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
            if (row != 0 or overflow_array.shape != (FEATURE_DIM,)
                    or not np.isfinite(overflow_array).all()):
                ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
            value = value + mx.array(overflow_array, dtype=mx.float32)
        type_vectors.append(value)
    type_mean = (mx.mean(mx.stack(type_vectors), axis=0) if type_vectors
                 else parameters["features.type"][FEATURE_NONE_ROW])
    gates = mx.sigmoid(parameters["features.gates"])
    factor = (
        gates[0] * (type_mean @ parameters["features.project_type"].T)
        + gates[3] * (mx.array(graph, dtype=mx.float32)
                      @ parameters["features.project_graph"].T)
    )
    mx.eval(factor)
    result = np.asarray(factor, dtype=np.float32)
    if result.shape != (ModelTopologySpecV2.width,) or not np.isfinite(result).all():
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    return result


def initialize_bamf_row(parameter: ParameterSpec, *, run_seed: int, row_id: str, factor=None):
    """Compute a row value; source admission and allocation remain upstream."""
    import numpy as np

    if (type(parameter) is not ParameterSpec or len(parameter.shape) != MATRIX_RANK or
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
