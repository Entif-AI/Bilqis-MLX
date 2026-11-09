"""B11 execution contracts shared by forward, loss, and gradient owners."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from weakref import WeakValueDictionary, finalize

import mlx.core as mx

from bilqis_mlx.data_plane import SHA256_HEX_LENGTH
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_readout import LossParts, ModelOutput
from bilqis_mlx.learning.frame_encoder import CompiledEncoderInput
from bilqis_mlx.learning.source_atoms.inputs import SourceAtomRow
from bilqis_mlx.semantics.atlas_features import FeatureSchema
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
from bilqis_mlx.runtime.atlas_artifact_owner import AtlasFeatureArtifactOwner
from bilqis_mlx.runtime.atlas_training_authority import BamfTrainingAuthority
from bilqis_mlx.runtime.atlas_visit_provenance import BamfVisitProvenance


def _invalid(reason: str) -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID, reason=reason)


def _digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == SHA256_HEX_LENGTH
        and all(char in "0123456789abcdef" for char in value)
    )


@dataclass(frozen=True)
class _ForwardRecord:
    generation_binding: str
    custody_run_id: str | None
    custody_generation: int | None
    custody_manifest_sha256: str | None
    visible_identity_rows: tuple[tuple[int, int], ...]
    feature_rows: tuple[tuple[str, int], ...]
    local_slot_rows: tuple[int, ...]
    dense_parameter_names: tuple[str, ...]
    motif_reads: tuple
    role_map: tuple[tuple[str, int], ...]
    training_authority: BamfTrainingAuthority | None


class _ForwardRegistry:
    def __init__(self):
        self.outputs = WeakValueDictionary()
        self.records = {}

    def issue(self, output, record):
        key = id(output)
        self.outputs[key] = output
        self.records[key] = record
        finalize(output, self.records.pop, key, None)
        return output

    def require(self, output):
        record = self.records.get(id(output))
        if self.outputs.get(id(output)) is not output or record is None:
            _invalid("B11_FORWARD_OUTPUT_NOT_ISSUED")
        return record


_FORWARD_ISSUANCE = _ForwardRegistry()
_LOSS_EXECUTION_ISSUER = object()


@dataclass(frozen=True, init=False)
class BamfLossExecution:
    """Exact B11 forward/loss witness accepted by the production B09 binder."""

    output: ModelOutput
    loss: LossParts
    custody_run_id: str | None
    custody_generation: int | None
    custody_manifest_sha256: str | None
    visible_identity_rows: tuple[tuple[int, int], ...]
    feedback_identity_rows: tuple[tuple[int, int], ...]
    semantic_denominator_identity_rows: tuple[tuple[int, int], ...]
    feature_rows: tuple[tuple[str, int], ...]
    semantic_denominator_feature_rows: tuple[tuple[str, int], ...]
    role_read_feature_rows: tuple[tuple[str, int], ...]
    local_slot_rows: tuple[int, ...]
    dense_parameter_names: tuple[str, ...]
    motif_reads: tuple
    training_authority: BamfTrainingAuthority | None
    schema_version: str = "bilqis.mlx.b11-loss-execution/v1"
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid("B11_LOSS_EXECUTION_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self):
        custody = (
            self.custody_run_id,
            self.custody_generation,
            self.custody_manifest_sha256,
        )
        custody_valid = (
            custody == (None, None, None)
            or (
                isinstance(self.custody_run_id, str)
                and bool(self.custody_run_id)
                and type(self.custody_generation) is int
                and self.custody_generation >= 0
                and _digest(self.custody_manifest_sha256)
            )
        )
        if (
            getattr(self, "_issuance", None) is not _LOSS_EXECUTION_ISSUER
            or type(self.output) is not ModelOutput
            or type(self.loss) is not LossParts
            or not custody_valid
            or self.visible_identity_rows
            != tuple(sorted(set(self.visible_identity_rows)))
            or self.feedback_identity_rows
            != tuple(sorted(set(self.feedback_identity_rows)))
            or self.semantic_denominator_identity_rows
            != tuple(sorted(set(self.semantic_denominator_identity_rows)))
            or self.feature_rows != tuple(sorted(set(self.feature_rows)))
            or self.semantic_denominator_feature_rows
            != tuple(sorted(set(self.semantic_denominator_feature_rows)))
            or self.role_read_feature_rows
            != tuple(sorted(set(self.role_read_feature_rows)))
            or self.local_slot_rows != tuple(sorted(set(self.local_slot_rows)))
            or self.dense_parameter_names
            != tuple(sorted(set(self.dense_parameter_names)))
            or type(self.motif_reads) is not tuple
            or (self.training_authority is not None
                and type(self.training_authority) is not BamfTrainingAuthority)
            or self.schema_version != "bilqis.mlx.b11-loss-execution/v1"
        ):
            _invalid("B11_LOSS_EXECUTION_INVALID")


@dataclass(frozen=True, init=False)
class BamfGradientExecution:
    """One exact MLX value-and-grad dispatch over one B11-issued loss."""

    execution: BamfLossExecution
    gradients: Mapping
    loss_total: mx.array
    schema_version: str = "bilqis.mlx.b11-gradient-execution/v1"
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid("B11_GRADIENT_EXECUTION_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self):
        if (
            getattr(self, "_issuance", None) is not _LOSS_EXECUTION_ISSUER
            or type(self.execution) is not BamfLossExecution
            or not isinstance(self.gradients, Mapping)
            or not isinstance(self.loss_total, mx.array)
            or self.loss_total.size != 1
            or not bool(mx.all(mx.isfinite(self.loss_total)))
            or self.schema_version != "bilqis.mlx.b11-gradient-execution/v1"
        ):
            _invalid("B11_GRADIENT_EXECUTION_INVALID")
        require_bamf_loss_execution(self.execution)


def _issue_loss_execution(output, loss, record, participation):
    execution = object.__new__(BamfLossExecution)
    for name, value in (
        ("output", output),
        ("loss", loss),
        ("custody_run_id", record.custody_run_id),
        ("custody_generation", record.custody_generation),
        ("custody_manifest_sha256", record.custody_manifest_sha256),
        ("visible_identity_rows", record.visible_identity_rows),
        ("feedback_identity_rows", participation[0]),
        ("semantic_denominator_identity_rows", participation[1]),
        ("feature_rows", record.feature_rows),
        ("semantic_denominator_feature_rows", participation[2]),
        ("role_read_feature_rows", participation[3]),
        ("local_slot_rows", record.local_slot_rows),
        ("dense_parameter_names", record.dense_parameter_names),
        ("motif_reads", record.motif_reads),
        ("training_authority", record.training_authority),
        ("schema_version", "bilqis.mlx.b11-loss-execution/v1"),
        ("_issuance", _LOSS_EXECUTION_ISSUER),
    ):
        object.__setattr__(execution, name, value)
    execution.__post_init__()
    return execution


def require_bamf_loss_execution(execution):
    if type(execution) is not BamfLossExecution:
        _invalid("B11_LOSS_EXECUTION_REQUIRED")
    execution.__post_init__()
    record = _FORWARD_ISSUANCE.require(execution.output)
    if record.generation_binding != execution.output.generation_binding:
        _invalid("B11_LOSS_EXECUTION_GENERATION_MISMATCH")
    return execution


@dataclass(frozen=True)
class BamfCompiledBatch:
    """One source-qualified compiled row and the source inputs that created it."""

    compiled: CompiledEncoderInput
    sources: tuple[SourceAtomRow, ...]
    feature_schema: FeatureSchema
    training_authority: BamfTrainingAuthority | None = None
    visit_provenance: BamfVisitProvenance | None = None
    task_authority: object | None = None
    schema_version: str = "bilqis.mlx.b11-compiled-batch/v1"
    atlas_feature_artifact_owner: AtlasFeatureArtifactOwner = field(init=False, compare=False)

    def __post_init__(self) -> None:
        if (
            self.schema_version != "bilqis.mlx.b11-compiled-batch/v1"
            or type(self.compiled) is not CompiledEncoderInput
            or type(self.sources) is not tuple
            or len(self.sources) != len(self.compiled.compiled.rows)
            or len(self.sources) != 1
            or any(type(item) is not SourceAtomRow for item in self.sources)
            or type(self.feature_schema) is not FeatureSchema
            or (self.training_authority is not None
                and type(self.training_authority) is not BamfTrainingAuthority)
            or (self.visit_provenance is not None
                and type(self.visit_provenance) is not BamfVisitProvenance)
            or ((self.training_authority is None) != (self.visit_provenance is None))
        ):
            _invalid("B11_COMPILED_BATCH_INVALID")
        self.compiled.__post_init__()
        if self.task_authority is not None:
            from bilqis_mlx.runtime.factory_task_authority import FactoryTaskAuthority
            if type(self.task_authority) is not FactoryTaskAuthority:
                _invalid("B11_FACTORY_TASK_AUTHORITY_INVALID")
            self.task_authority.__post_init__()
            training = self.training_authority
            if (
                self.task_authority.source_row_id != self.sources[0].source_row.get("id")
                or self.task_authority.capability_id
                != self.sources[0].source_row.get("capability")
                or ((training is None)
                    != (self.task_authority.training_authority_sha256 is None))
                or (training is not None
                    and training.digest
                    != self.task_authority.training_authority_sha256)
            ):
                _invalid("B11_FACTORY_TASK_AUTHORITY_MISMATCH")
        if self.training_authority is not None:
            self.visit_provenance.__post_init__()
            if (self.visit_provenance.capability_id
                    != self.training_authority.delivery_capability
                    or self.visit_provenance.visit_id
                    != self.training_authority.visit_id):
                _invalid("B11_VISIT_PROVENANCE_CAPABILITY_MISMATCH")
            row = self.compiled.compiled.rows[0]
            frame_nodes = self.compiled.packed_frame_artifact_owner.require_row(row)
            contextual_kinds = {
                DependencyKind.POLICY, DependencyKind.RIGHTS, DependencyKind.TIME,
            }
            current_context = {
                ref
                for node in frame_nodes
                for ref in node.immediate_dependencies
                if ref.kind in contextual_kinds
            }
            authority_context = {
                ref for ref in self.training_authority.immediate_dependencies
                if ref.kind in contextual_kinds
            }
            if not current_context.issubset(authority_context):
                _invalid("B11_TRAINING_AUTHORITY_CONTEXT_DRIFT")
        owner = getattr(self, "atlas_feature_artifact_owner", None)
        if owner is None:
            object.__setattr__(
                self,
                "atlas_feature_artifact_owner",
                AtlasFeatureArtifactOwner(
                    self.compiled.features, self.feature_schema),
            )
        else:
            owner.require(self.compiled.features)


__all__ = (
    "BamfCompiledBatch",
    "BamfLossExecution",
    "BamfGradientExecution",
    "require_bamf_loss_execution",
)
