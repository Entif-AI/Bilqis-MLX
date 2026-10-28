"""Frozen BAMF architecture identity, independent of generation extents."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import hashlib
import json
from typing import Mapping

from bilqis_mlx.errors import ErrorBus, SCHOOL
from .model_topology import ModelTopologySpec, SCHEMA as LEGACY_SCHEMA


SCHEMA = "bilqis.mlx.model-topology/v2"
BAMF_ARCHITECTURE_ID = "bamf-atlas-v2"
LEGACY_ARCHITECTURE_ID = "bilqis.mlx.causal-tied-fp32/v1"


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
