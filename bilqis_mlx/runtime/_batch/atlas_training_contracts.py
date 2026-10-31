"""Structural extraction from atlas_training_adapter.py; behavior preserved."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.source_execution import SourceExecutionContext

@dataclass(frozen=True)
class BamfModelInput:
    prefix: Any
    features: tuple
    eligibility_digest: str
    answer_plan: tuple

@dataclass(frozen=True)
class BamfTarget:
    kind: str
    value: Any
    token_id: Any
    mask: bool | tuple[bool, ...]

@dataclass(frozen=True)
class BamfTargetEvidence:
    gold: Any
    answer_plan: Any
    auxiliary_labels: Any

@dataclass(frozen=True)
class BamfDeliveryProvenance:
    row_id: str
    source_id: str | None
    capability_id: str
    operation_id: str | None
    teacher_strategy: tuple
    requested_count: int
    delivered_count: int
    rehearsal: str | None
    optimizer_step_seed: int
    source_family_id: str | None = None
    episode_id: str | None = None

@dataclass(frozen=True)
class BamfTrainingRow:
    model_input: BamfModelInput
    target: BamfTarget
    native_target: BamfTarget | None
    provenance: BamfDeliveryProvenance
    auxiliaries: tuple = ()
    rule_policy: tuple = ()

@dataclass(frozen=True)
class BamfTrainingBatch:
    release_sha256: str
    generation_binding: str
    delivered_content_sha256: str
    rows: tuple[BamfTrainingRow, ...]

def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_TRAINING_ADAPTER.INVALID, reason=reason)

def _freeze(value):
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return tuple((key, _freeze(value[key])) for key in sorted(value))
    _invalid('UNSUPPORTED_SOURCE_OR_PROVENANCE_VALUE')

def require_current_release(batch: BamfTrainingBatch, source_context: SourceExecutionContext, *,
                            generation_binding: str) -> None:
    """Refuse a prepared batch after its Factory release or semantic graph changes."""
    if not isinstance(batch, BamfTrainingBatch) or not isinstance(source_context, SourceExecutionContext):
        _invalid('SOURCE_CONTEXT_REQUIRED')
    source_context.release.verify()
    source_context.release.verify_semantic_catalog(source_context.graph)
    if (batch.release_sha256 != source_context.release.release_sha256 or
            not isinstance(generation_binding, str) or not generation_binding or
            batch.generation_binding != generation_binding):
        _invalid('STALE_FACTORY_RELEASE')

@dataclass(frozen=True)
class PaddedMicrobatch:
    row_indices: tuple[int, ...]
    positions: tuple
    padding_mask: tuple
