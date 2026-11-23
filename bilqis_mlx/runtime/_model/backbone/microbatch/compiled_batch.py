"""Compilation and compatibility ownership for B11 logical microbatches."""
from __future__ import annotations

from dataclasses import dataclass, field

from bilqis_mlx.learning.frame_encoder import CompiledEncoderInput
from bilqis_mlx.runtime.atlas_artifact_owner import AtlasFeatureArtifactOwner
from bilqis_mlx.semantics.frame_compiler import CompiledFrameRows

from ..atlas_model_contracts import BamfCompiledBatch, _invalid
from .route_kernel import route_microbatch_compatible


_MIN_ROWS = 2


@dataclass(frozen=True)
class _CompiledMicrobatch:
    compiled: CompiledEncoderInput
    sources: tuple
    feature_schema: object
    active_semantic_rows: object
    row_batches: tuple[BamfCompiledBatch, ...]
    atlas_feature_artifact_owner: AtlasFeatureArtifactOwner = field(
        init=False, compare=False)

    def __post_init__(self):
        if (type(self.compiled) is not CompiledEncoderInput
                or type(self.sources) is not tuple
                or len(self.sources) != len(self.compiled.compiled.rows)
                or type(self.row_batches) is not tuple
                or len(self.row_batches) != len(self.sources)
                or len(self.row_batches) < _MIN_ROWS
                or any(type(item) is not BamfCompiledBatch
                       for item in self.row_batches)):
            _invalid("B11_MICROBATCH_COMPILED_INPUT_INVALID")
        object.__setattr__(
            self, "atlas_feature_artifact_owner",
            AtlasFeatureArtifactOwner(self.compiled.features, self.feature_schema))


def _merge_compiled_rows(row_batches):
    rows = tuple(item.compiled.compiled.rows[0] for item in row_batches)
    width = max(len(row.positions) for row in rows)
    compiled_rows = CompiledFrameRows(
        rows,
        tuple(row.positions + (None,) * (width - len(row.positions))
              for row in rows),
        tuple((True,) * len(row.positions) + (False,) * (width - len(row.positions))
              for row in rows))
    first = row_batches[0].compiled
    source_asts = tuple(
        None if item.compiled.source_asts is None else item.compiled.source_asts[0]
        for item in row_batches)
    receipts = tuple(
        None if item.compiled.partial_forest_receipts is None
        else item.compiled.partial_forest_receipts[0]
        for item in row_batches)
    if not any(item is not None for item in source_asts):
        source_asts = receipts = None
    return CompiledEncoderInput(
        compiled_rows,
        tuple(item.compiled.compiler_configs[0] for item in row_batches),
        first.features, first.extents,
        source_asts=source_asts, partial_forest_receipts=receipts)


def microbatch_compatible(
        row_batches, answer_plans=None, targets=None, masks=None) -> bool:
    """Return whether rows can share one B11 source-backbone dispatch safely."""
    if (type(row_batches) is not tuple or len(row_batches) < _MIN_ROWS
            or any(type(item) is not BamfCompiledBatch for item in row_batches)):
        return False
    first = row_batches[0]
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    strict = strict_evidence_enabled()
    for item in row_batches:
        item.__post_init__()
        row = item.compiled.compiled.rows[0]
        if strict:
            item.compiled.packed_frame_artifact_owner.require_row(row)
            item.atlas_feature_artifact_owner.require(item.compiled.features)
        if (item.compiled.features != first.compiled.features
                or item.compiled.extents != first.compiled.extents
                or item.feature_schema != first.feature_schema
                or item.active_semantic_rows != first.active_semantic_rows
                or item.sources[0].selection != first.sources[0].selection):
            return False
    source_authorities = tuple(
        item.source_execution_authority for item in row_batches)
    bound_source_authorities = tuple(
        authority is not None for authority in source_authorities)
    if any(bound_source_authorities):
        if not all(bound_source_authorities):
            return False
        first_owner = source_authorities[0].source_owner_contract
        if any(authority.source_owner_contract != first_owner
               for authority in source_authorities[1:]):
            return False
    if answer_plans is None and targets is None and masks is None:
        return True
    if answer_plans is None or targets is None or masks is None:
        return False
    if any(plan.snapshot != answer_plans[0].snapshot for plan in answer_plans):
        return False
    return route_microbatch_compatible(
        row_batches, answer_plans, targets, masks)


def _compiled_microbatch(row_batches):
    if not microbatch_compatible(row_batches):
        _invalid("B11_MICROBATCH_ROWS_INCOMPATIBLE")
    merged = _merge_compiled_rows(row_batches)
    first = row_batches[0]
    result = _CompiledMicrobatch(
        merged, tuple(item.sources[0] for item in row_batches),
        first.feature_schema, first.active_semantic_rows, row_batches)
    result.__post_init__()
    return result


def _microbatch_salience_labels(row_batches, salience_supervision):
    if salience_supervision is None:
        return ()
    from ..salience_training import SalienceSupervision
    if type(salience_supervision) is not SalienceSupervision:
        _invalid("BAMF_SALIENCE_SUPERVISION_REQUIRED")
    return tuple(
        salience_supervision.labels_for(row_batch) for row_batch in row_batches)


__all__ = (
    "_MIN_ROWS", "_compiled_microbatch", "_microbatch_salience_labels",
    "microbatch_compatible",
)

