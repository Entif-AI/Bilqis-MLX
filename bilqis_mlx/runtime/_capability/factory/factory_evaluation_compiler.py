"""Compile one Factory-owned evaluation row through the accepted A01/A05 path."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.learning.frame_encoder import CompiledEncoderInput
from bilqis_mlx.learning.source_atoms import SourceAtomRow
from bilqis_mlx.runtime.atlas_model_contracts import (
    BamfCompiledBatch, bind_candidate_active_semantic_rows,
)
from bilqis_mlx.runtime.bamf_bundle import (
    BamfBundleCandidate, authenticate_bamf_execution_feature_context,
)
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextPolicy, SourceFrontier, TaskScope,
)
from bilqis_mlx.semantics.frame_compiler import (
    compile_prefix_rows, validate_partial_visible_forest,
)
from bilqis_mlx.source_adapters.atoms.admission import (
    authorize_public_formal_prefix, public_formal_atom_context,
)
from bilqis_mlx.source_adapters.atoms.authority import canonical_graph_for

from .capability_evaluation import _invalid


_PRINCIPAL = "bamf-c05-evaluator"
_TENANT = "bamf-c05"
_PURPOSE = "C05_EVALUATION"
_JURISDICTION = "LOCAL"


def _evaluation_context(release: str, capability: str, prefix_end: int):
    task = TaskScope(
        _PRINCIPAL, _TENANT, _PURPOSE, release, _JURISDICTION,
        capability, 0, 0, prefix_end,
    )
    frontier = SourceFrontier(1, 1, ())
    policy = ContextPolicy(
        "bamf-c05-public-formal/v1", 1, 1,
        (_PURPOSE,), (PUBLIC_FORMAL,), (_JURISDICTION,), (capability,),
        (PUBLIC_FORMAL,), (), (),
    )
    return task, frontier, policy


def compile_factory_evaluation_batch(
    source_context: SourceExecutionContext,
    candidate: BamfBundleCandidate,
    artifact_path: str,
    row: dict,
    *,
    source_seed: int,
    source_each: int,
) -> BamfCompiledBatch:
    """Produce B11 input without constructing or exposing evaluator gold."""
    if (type(source_context) is not SourceExecutionContext
            or not isinstance(candidate, BamfBundleCandidate)
            or not isinstance(row, dict)
            or not isinstance(row.get("tokens"), list) or not row["tokens"]
            or not isinstance(row.get("capability"), str) or not row["capability"]
            or type(source_seed) is not int or source_seed < 0
            or type(source_each) is not int or source_each < 1
            or source_context.source_root is None):
        _invalid("BAMF_C05_EVALUATION_COMPILE_INPUT_INVALID")
    source_context.release.verify()
    source_context.release.verify_semantic_catalog(source_context.graph)
    authenticated = authenticate_bamf_execution_feature_context(
        candidate, artifact_path, source_context.run_dir)
    execution = source_context.release.execution_plan.capability_map[
        row["capability"]]
    profile_parameters = (dict(execution.provider_parameters)
                          if execution.provider_parameters else None)
    source_graph = canonical_graph_for(
        row.get("generator"), source_context.source_root)
    task, frontier, policy = _evaluation_context(
        authenticated.features.semantic_release,
        row["capability"], len(row["tokens"]),
    )
    ast, config = public_formal_atom_context(
        authenticated.selection, row, source_graph,
        source_root=source_context.source_root,
        source_seed=source_seed, source_each=source_each,
        course=source_context.release.curriculum,
        source_profile_parameters=profile_parameters,
        task=task, frontier=frontier, policy=policy,
    )
    rows = compile_prefix_rows(
        ((ast, len(ast.atoms), config),), authenticated.features.semantic_release)
    config = authorize_public_formal_prefix(ast, rows.rows[0], config)
    receipt = validate_partial_visible_forest(rows.rows[0], ast, config)
    compiled = CompiledEncoderInput(
        rows, (config,), authenticated.features, candidate.extents,
        source_asts=(ast,), partial_forest_receipts=(receipt,))
    source = SourceAtomRow(
        authenticated.selection, row, source_graph,
        Path(source_context.source_root), source_seed, source_each,
        source_context.release.curriculum, profile_parameters)
    batch = BamfCompiledBatch(
        compiled, (source,), authenticated.schema,
        bind_candidate_active_semantic_rows(candidate, authenticated))
    batch.__post_init__()
    source_context.register_compiled_batch(batch)
    return batch


__all__ = ("compile_factory_evaluation_batch",)
