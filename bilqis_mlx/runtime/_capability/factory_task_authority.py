"""Factory/source ownership of one gold-blind C04 TaskGoal and binding."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json

from bilqis_mlx.factory.generation import runtime_adapter_for_release
from bilqis_mlx.factory.teaching import content_digest
from bilqis_mlx.runtime.atlas_model_contracts import BamfCompiledBatch
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.semantics.cognitive_dag import TaskGoal
from bilqis_mlx.semantics.cognitive_operators import OperatorBinding
from bilqis_mlx.semantics.domains import contract_digest

from .capability_evaluation import _invalid


_ISSUER = object()
_PRIVATE_SOURCE_KEYS = frozenset((
    "gold", "native_output", "auxiliary_labels", "answer", "label",
    "expected", "expected_answer", "score", "oracle_result",
))


def _source_view(row: dict) -> dict:
    if not isinstance(row, dict):
        _invalid("BAMF_C04_SOURCE_TASK_ROW_INVALID")
    return {key: value for key, value in row.items()
            if key not in _PRIVATE_SOURCE_KEYS}


@dataclass(frozen=True, init=False)
class FactoryTaskAuthority:
    goal: TaskGoal
    binding: OperatorBinding
    release_sha256: str
    generation_binding: str
    capability_id: str
    source_row_id: str
    source_row_sha256: str
    source_binding_sha256: str
    training_authority_sha256: str
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid("BAMF_C04_FACTORY_TASK_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self):
        if (getattr(self, "_issuance", None) is not _ISSUER
                or type(self.goal) is not TaskGoal
                or type(self.binding) is not OperatorBinding
                or not all(isinstance(item, str) and item for item in (
                    self.release_sha256, self.generation_binding,
                    self.capability_id, self.source_row_id,
                    self.source_row_sha256, self.source_binding_sha256,
                    self.training_authority_sha256))
                or self.goal.goal_id != self.source_row_id
                or self.goal.semantic_release != self.binding.task.semantic_release
                or self.goal.scope != self.binding.task.scope
                or contract_digest(self.binding) != self.source_binding_sha256):
            _invalid("BAMF_C04_FACTORY_TASK_AUTHORITY_INVALID")

    @property
    def digest(self) -> str:
        wire = json.dumps({
            "goal": contract_digest(self.goal),
            "binding": self.source_binding_sha256,
            "release": self.release_sha256,
            "generation": self.generation_binding,
            "capability": self.capability_id,
            "row": self.source_row_id,
            "row_sha256": self.source_row_sha256,
            "training_authority": self.training_authority_sha256,
        }, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(wire.encode()).hexdigest()


def factory_task_authority(
    source_context: SourceExecutionContext,
    compiled_batch: BamfCompiledBatch,
) -> FactoryTaskAuthority:
    """Ask only the admitted source owner to lower one exact gold-blind task."""
    if (type(source_context) is not SourceExecutionContext
            or type(compiled_batch) is not BamfCompiledBatch
            or compiled_batch.training_authority is None):
        _invalid("BAMF_C04_FACTORY_TASK_AUTHORITY_REQUIRED")
    source_context.__post_init__()
    compiled_batch.__post_init__()
    authority = compiled_batch.training_authority
    source = compiled_batch.sources[0]
    row = source.source_row
    if (authority.release_sha256 != source_context.release.release_sha256
            or authority.source_row_id != row.get("id")
            or authority.source_row_sha256 != content_digest((row,))
            or authority.delivery_capability != row.get("capability")):
        _invalid("BAMF_C04_FACTORY_TASK_SOURCE_MISMATCH")
    execution = source_context.release.execution_plan.capability_map.get(
        authority.delivery_capability)
    if execution is None:
        _invalid("BAMF_C04_FACTORY_TASK_CAPABILITY_MISSING")
    adapter = runtime_adapter_for_release(
        source_context.source_root, source_context.graph,
        source_context.release, source_context.source_registry, execution,
        drift_code="BAMF_C04_FACTORY_TASK_ADAPTER_DRIFT",
    )
    if adapter.task_goal is None:
        _invalid("BAMF_C04_SOURCE_TASK_LOWERER_REQUIRED")
    lowered = adapter.task_goal(
        _source_view(row),
        source_root=source_context.source_root,
        graph=source_context.graph,
        release=source_context.release,
        capability=execution,
    )
    if (not isinstance(lowered, tuple) or len(lowered) != 2
            or type(lowered[0]) is not TaskGoal
            or type(lowered[1]) is not OperatorBinding):
        _invalid("BAMF_C04_SOURCE_TASK_LOWERING_INVALID")
    goal, binding = lowered
    item = object.__new__(FactoryTaskAuthority)
    for name, value in (
        ("goal", goal), ("binding", binding),
        ("release_sha256", authority.release_sha256),
        ("generation_binding", authority.generation_binding),
        ("capability_id", authority.delivery_capability),
        ("source_row_id", authority.source_row_id),
        ("source_row_sha256", authority.source_row_sha256),
        ("source_binding_sha256", contract_digest(binding)),
        ("training_authority_sha256", authority.digest),
        ("_issuance", _ISSUER),
    ):
        object.__setattr__(item, name, value)
    item.__post_init__()
    return item


__all__ = ("FactoryTaskAuthority", "factory_task_authority")
