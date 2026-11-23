"""Minimal training-row compiler for ADR-153 ordinary BAMF learning."""
from __future__ import annotations

from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2

from bilqis_mlx.runtime.atlas_training_compilation import (
    PreparedModelSourceInput, _answer_plan, _compile_target,
)
from bilqis_mlx.runtime.atlas_training_contracts import (
    BamfLearningRowMetadata, BamfModelInput, BamfTarget, BamfTrainingRow,
    _freeze, _invalid, _issue_training_batch,
)
from bilqis_mlx.runtime.factory_training_context import training_answer_plan
from bilqis_mlx.runtime.source_execution import _source_family


def _native_target(row):
    native = row.get("native_output")
    if not isinstance(native, dict):
        return None
    identity, token_id = native.get("identity"), native.get("token_id")
    if not isinstance(identity, str) or not identity or type(token_id) is not int:
        _invalid("NATIVE_TARGET_REQUIRED")
    return BamfTarget("semantic_token", identity, token_id, True)


def compile_learning_first_training_batch(
        delivered_rows, source_context, topology, *, delivery_capability,
        teacher_strategy, requested_count, optimizer_step_seed,
        visit_provenance, rehearsal_by_id, generation_binding,
        prepared_model_sources, delivered_content_sha256):
    """Compile already-selected numerical lesson inputs without authority replay."""
    rows = tuple(delivered_rows)
    prepared = tuple(prepared_model_sources)
    if not rows:
        _invalid("LEARNING_FIRST_ROWS_REQUIRED")
    if len(rows) != len(prepared):
        _invalid("LEARNING_FIRST_SOURCE_COUNT_MISMATCH")
    if not isinstance(delivered_content_sha256, str) or not delivered_content_sha256:
        _invalid("LEARNING_FIRST_DELIVERY_DIGEST_REQUIRED")
    if any(not all(hasattr(item, name) for name in (
            "row_id", "visible", "prefix", "features", "eligibility_digest"))
           for item in prepared):
        _invalid("LEARNING_FIRST_PREPARED_SOURCE_INVALID")
    capabilities = source_context.release.execution_plan.capability_map
    heads = {head.kind: head for head in source_context.release.answer_heads}
    compiled_rows = []
    for row, source in zip(rows, prepared, strict=True):
        identity = row.get("id")
        capability_id = row.get("capability")
        capability = capabilities.get(capability_id)
        if (not isinstance(identity, str) or not identity
                or capability is None or source.row_id != identity
                or source.visible != tuple(row.get("tokens", ()))):
            _invalid("LEARNING_FIRST_ROW_INVALID")
        kind, gold = row.get("answer_kind", "binary"), row.get("gold")
        families = {
            family.kind: family.values for family in capability.answer_families}
        head = heads.get(kind)
        if head is None or kind not in families:
            _invalid("ANSWER_NOT_RELEASED")
        plan = _answer_plan(
            training_answer_plan(
                source.prefix, source_context.release, kind, generation_binding),
            head, len(source.visible), generation_binding)
        model_input = BamfModelInput(
            source.prefix, source.features, source.eligibility_digest, plan)
        target = _compile_target(
            row, kind=kind, gold=gold, families=families, head=head, plan=plan)
        source_id = row.get("source_id")
        operation_id = row.get("operation_id")
        if operation_id is None and isinstance(row.get("record"), dict):
            operation_id = row["record"].get("operator")
        episode_id = row.get("episode_id")
        if not isinstance(episode_id, str) or not episode_id:
            episode_id = identity
        source_family_id = row.get("source_family_id")
        if source_family_id is None:
            source_family_id = _source_family(capability)
        elif not isinstance(source_family_id, str) or not source_family_id:
            _invalid("LEARNING_FIRST_SOURCE_FAMILY_INVALID")
        metadata = BamfLearningRowMetadata(
            identity, source_id, capability_id, operation_id,
            _freeze(teacher_strategy), requested_count, len(rows),
            (rehearsal_by_id or {}).get(identity), optimizer_step_seed,
            visit_provenance, source_family_id, episode_id)
        compiled_rows.append(BamfTrainingRow(
            model_input, target, _native_target(row), metadata))
    return _issue_training_batch(
        source_context.release.release_sha256, generation_binding,
        delivered_content_sha256, delivery_capability,
        tuple(compiled_rows))


__all__ = ("compile_learning_first_training_batch",)
