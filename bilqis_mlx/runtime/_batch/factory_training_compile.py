"""Compile validated Factory training rows for strict and learning-first paths."""
from __future__ import annotations

from bilqis_mlx.factory.teaching import content_digest

from .atlas_training_adapter import compile_training_batch
from .atlas_training_contracts import _invalid
from .factory_training_context import training_answer_plan
from .learning_first_compiler import compile_learning_first_training_batch


def _compile_factory_training(
        rows, source_context, candidate, delivery, capability, teacher_strategy,
        requested_count, optimizer_step_seed, visit_provenance, source_authority,
        rehearsal_by_id, fresh_support_by_id, rehearsal_authorities, source_rows,
        feature_artifact_path, generation_binding,
        authenticated, manifest, prepared_model_sources):
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    if not strict_evidence_enabled():
        return compile_learning_first_training_batch(
            rows, source_context, candidate.topology,
            delivery_capability=capability,
            teacher_strategy=teacher_strategy,
            requested_count=requested_count,
            optimizer_step_seed=optimizer_step_seed,
            visit_provenance=visit_provenance,
            rehearsal_by_id=(rehearsal_by_id or {}),
            fresh_support_by_id=(fresh_support_by_id or {}),
            generation_binding=generation_binding,
            prepared_model_sources=prepared_model_sources,
            delivered_content_sha256=content_digest(rows))
    by_tokens = {tuple(item.row["tokens"]): item.ast for item in source_rows}
    if len(by_tokens) != len(rows):
        _invalid("FACTORY_TRAINING_AMBIGUOUS_SOURCE_PREFIX")
    by_ast = {id(item.ast): item.projection for item in source_rows}
    return compile_training_batch(
        rows, source_context, candidate.topology, delivery=delivery,
        delivery_capability=capability,
        delivery_release_sha256=source_context.release.release_sha256,
        teacher_strategy=teacher_strategy,
        requested_count=requested_count, optimizer_step_seed=optimizer_step_seed,
        visit_provenance=visit_provenance,
        source_authority=source_authority,
        rehearsal_by_id=(rehearsal_by_id or {}),
        rehearsal_authorities=(rehearsal_authorities or {}),
        visible_ends={row["id"]: len(row["tokens"]) for row in rows},
        source_ast_for=lambda tokens: by_tokens[tuple(tokens)],
        compiler_config=tuple(item.config for item in source_rows),
        feature_artifact_path=feature_artifact_path,
        answer_plan_for=lambda prefix, release, cap, kind: training_answer_plan(
            prefix, release, kind, generation_binding),
        frames_for_ast=lambda ast: (() if by_ast[id(ast)] is None
                                    else by_ast[id(ast)].envelopes),
        task_scope=tuple(item.task for item in source_rows),
        source_frontier=tuple(item.frontier for item in source_rows),
        eligibility_policy=tuple(item.policy for item in source_rows),
        semantic_context=authenticated,
        released_manifest=tuple(getattr(item, "manifest", manifest) for item in source_rows),
        generation_binding=generation_binding,
        atlas_selection=authenticated.selection,
        prepared_model_sources=prepared_model_sources)


__all__ = ("_compile_factory_training",)
