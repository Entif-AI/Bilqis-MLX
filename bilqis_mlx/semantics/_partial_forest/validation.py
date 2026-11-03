"""Validation of source-owned partial forest authority."""
from __future__ import annotations
from .. import partial_visible_forest as _facade
from ..frame_compiler import CompiledFrameBatch, FrameCompilerConfig, StreamingAST
from .binding import _bind_visible_frames
from .receipts import PartialVisibleForestReceipt



def _check_binding_inputs(
    compiled, source_ast, compiler_config, expected_receipt,
):
    if (not isinstance(compiled, CompiledFrameBatch)
            or not isinstance(source_ast, StreamingAST)
            or not isinstance(compiler_config, FrameCompilerConfig)
            or (expected_receipt is not None
                and not isinstance(expected_receipt, PartialVisibleForestReceipt))):
        _facade._invalid("BAMF_PREFIX_PARTIAL_INPUT_INVALID")
    compiled.__post_init__()
    if (source_ast.source_instance_id != compiled.source_instance_id
            or compiler_config.task.semantic_release != compiled.semantic_release
            or compiler_config.schema_map.semantic_release != compiled.semantic_release
            or compiler_config.schema_map != compiled.schema_map
            or compiler_config.task.scope != compiled.scope
            or compiled.policy_version != (
                compiler_config.policy.policy_id,
                compiler_config.policy.policy_epoch,
                compiler_config.policy.rights_epoch,
                compiler_config.frontier.correction_generation)):
        _facade._invalid("BAMF_PREFIX_PARTIAL_AUTHORITY_DRIFT")


def validate_partial_visible_forest(
    compiled: CompiledFrameBatch,
    source_ast: StreamingAST,
    compiler_config: FrameCompilerConfig,
    *,
    expected_receipt: PartialVisibleForestReceipt | None = None,
) -> PartialVisibleForestReceipt:
    """Validate a visible prefix without synthesizing or rewriting hidden parents.

    Hidden-parent provenance binds source/context metadata only. Future bindings and
    member content never enter this receipt or the accepted compiler prefix identity.
    """
    _check_binding_inputs(
        compiled, source_ast, compiler_config, expected_receipt)

    visible = _facade.reconstruct(compiled)
    visible_frames = _facade._visible_forest_frames(visible.frames)
    visible_by_occurrence = {
        frame.occurrence_id: frame for frame in visible_frames}
    if len(visible_by_occurrence) != len(visible_frames):
        _facade._invalid("BAMF_PREFIX_PARTIAL_VISIBLE_DUPLICATE")

    source_frames, source_parents = _facade._source_tree_index(source_ast)
    for occurrence_id, source_frame in source_frames.items():
        if source_frame.parent_occurrence_id != source_parents[occurrence_id]:
            _facade._invalid("BAMF_PREFIX_PARTIAL_PARENT_ORPHAN")

    envelopes = {}
    if compiler_config.approved is not None:
        for envelope in compiler_config.approved.envelopes:
            occurrence_id = envelope.frame.occurrence_id
            if occurrence_id in envelopes:
                _facade._invalid("BAMF_PREFIX_PARTIAL_AUTHORITY_DRIFT")
            envelopes[occurrence_id] = envelope
    schemas = {
        (schema.schema_id, schema.revision): schema
        for schema in compiler_config.schemas
    }
    visible_handles, hidden_parents = _bind_visible_frames(
        visible_frames, compiled, source_frames, source_parents,
        envelopes, schemas, compiler_config)

    recompiled = _facade.compile_prefix(
        source_ast, compiled.visible_end,
        compiled.semantic_release, compiler_config)
    if recompiled != compiled:
        _facade._invalid("BAMF_PREFIX_PARTIAL_COMPILATION_DRIFT")

    visible_handles = tuple(sorted(visible_handles))
    hidden_parents = tuple(sorted(
        hidden_parents,
        key=lambda item: (
            item.child_occurrence_id, item.parent_occurrence_id)))
    digest = _facade._partial_forest_digest(
        compiled.source_instance_id,
        compiled.semantic_release,
        compiled.visible_end,
        compiled.cache_key,
        visible.frames,
        visible_handles,
        hidden_parents,
    )
    receipt = PartialVisibleForestReceipt(
        compiled.source_instance_id,
        compiled.semantic_release,
        compiled.visible_end,
        compiled.cache_key,
        visible.frames,
        visible_handles,
        hidden_parents,
        digest,
    )
    if expected_receipt is not None and receipt != expected_receipt:
        _facade._invalid("BAMF_PREFIX_PARTIAL_RECEIPT_DRIFT")
    return receipt
