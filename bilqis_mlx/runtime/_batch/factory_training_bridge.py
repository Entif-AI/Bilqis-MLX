"""Join source-owned Factory delivery to C02 inputs and B11 row execution."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from bilqis_mlx.factory.generation import runtime_adapter_for_release
from bilqis_mlx.factory.teaching import DeliveredTeaching
from bilqis_mlx.learning.frame_encoder import CompiledEncoderInput
from bilqis_mlx.learning.source_atoms import SourceAtomRow
from bilqis_mlx.runtime.atlas_model_contracts import BamfCompiledBatch
from bilqis_mlx.runtime.atlas_training_authority import bind_compiled_training_batch
from bilqis_mlx.runtime.bamf_bundle import (
    BamfBundleCandidate, authenticate_bamf_candidate_feature_context,
)
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.semantics.atlas_features.formal import source_family_for_adapter
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ApprovedContextProjection, ContextPolicy, SourceFrontier,
    TaskScope, project_context,
)
from bilqis_mlx.semantics.frame_adapters import (
    bind_registered_source_row, public_formal_context,
)
from bilqis_mlx.semantics.frame_compiler import (
    CompiledFrameRows, FrameCompilerConfig, validate_partial_visible_forest,
)
from bilqis_mlx.semantics.frame_schema import SourceSpan
from bilqis_mlx.semantics.released_frame_schemas import (
    _load_pinned_released_frame_schemas,
)
from bilqis_mlx.source_adapters.atoms.admission import public_formal_atom_context
from bilqis_mlx.source_adapters.atoms.authority import canonical_graph_for

from .atlas_training_adapter import compile_training_batch
from .atlas_training_contracts import BamfTrainingBatch, _invalid
from .factory_training_context import (
    public_training_context, schemas_cover_tree, training_answer_plan,
)


@dataclass(frozen=True)
class PreparedFactoryTrainingBatch:
    """One source-owned C02 delivery plus exact row-scoped B11 inputs."""

    training_batch: BamfTrainingBatch
    compiled_rows: tuple[BamfCompiledBatch, ...]

    def __post_init__(self) -> None:
        if (type(self.training_batch) is not BamfTrainingBatch
                or type(self.compiled_rows) is not tuple
                or len(self.compiled_rows) != len(self.training_batch.rows)
                or any(type(item) is not BamfCompiledBatch
                       for item in self.compiled_rows)):
            _invalid("FACTORY_TRAINING_BRIDGE_INVALID")


def prepare_factory_training_batch(
    source_context: SourceExecutionContext,
    candidate: BamfBundleCandidate,
    atlas_artifact_path: str,
    feature_artifact_path: str,
    delivered_rows,
    generation_binding: str,
    *,
    capability: str,
    delivery: DeliveredTeaching,
    requested_count: int,
    source_seed: int,
    source_each: int,
    optimizer_step_seed: int = 0,
    teacher_strategy: dict,
    rehearsal_by_id: dict | None = None,
) -> PreparedFactoryTrainingBatch:
    """Compile one real Factory draw once, then bind each C02 row into B11.

    The bridge owns composition only. A05/A06/A13 remain source authority, B11
    remains the neural owner, and C16 remains the durable-student launch owner.
    """
    rows = tuple(delivered_rows) if isinstance(delivered_rows, (tuple, list)) else ()
    if (type(source_context) is not SourceExecutionContext
            or not isinstance(candidate, BamfBundleCandidate)
            or not rows or any(type(row) is not dict for row in rows)
            or not isinstance(capability, str) or not capability
            or not isinstance(delivery, DeliveredTeaching)
            or type(requested_count) is not int or requested_count < len(rows)
            or type(source_seed) is not int or source_seed < 0
            or type(source_each) is not int or source_each != len(rows)
            or type(optimizer_step_seed) is not int or optimizer_step_seed < 0
            or not isinstance(teacher_strategy, dict)
            or not isinstance(generation_binding, str) or not generation_binding
            or source_context.source_root is None):
        _invalid("FACTORY_TRAINING_BRIDGE_INPUT_INVALID")
    authenticated = authenticate_bamf_candidate_feature_context(
        candidate, atlas_artifact_path)
    execution = source_context.release.execution_plan.capability_map[capability]
    adapter = runtime_adapter_for_release(
        source_context.source_root, source_context.graph, source_context.release,
        source_context.source_registry, execution)
    family = source_family_for_adapter(adapter.descriptor.adapter_id)
    manifest = _load_pinned_released_frame_schemas(
        family, authenticated.selection).manifest
    schema_ids = frozenset(body.schema_id for body in manifest.bodies)
    profile = (dict(execution.provider_parameters)
               if execution.provider_parameters else None)
    source_asts = []
    projections = []
    source_graphs = []
    configs = []
    tasks = []
    frontiers = []
    policies = []
    for row in rows:
        if row.get("capability") != capability:
            _invalid("FACTORY_TRAINING_CAPABILITY_MISMATCH")
        source_graph = canonical_graph_for(
            row.get("generator"), source_context.source_root)
        task, frontier, policy = public_training_context(
            authenticated.features.semantic_release, capability,
            len(row.get("tokens", ())))
        projection, frame_frontier = public_formal_context(
            adapter, row, authenticated.snapshot,
            source_root=source_context.source_root, graph=source_graph,
            task_scope=task, source_frontier=frontier, policy=policy,
            source_seed=source_seed, source_each=source_each,
            source_profile_parameters=profile,
            course=source_context.release.curriculum)
        if type(projection) is not ApprovedContextProjection:
            _invalid("FACTORY_TRAINING_CONTEXT_HELD")
        end = len(row["tokens"])
        tree = bind_registered_source_row(
            adapter, row, authenticated.snapshot,
            source_root=source_context.source_root, graph=source_graph,
            source_span=SourceSpan(0, end), causal_prefix_end=end,
            course=source_context.release.curriculum)
        if schemas_cover_tree(tree, schema_ids):
            atom_ast, atom_config = public_formal_atom_context(
                authenticated.selection, row, source_graph,
                source_root=source_context.source_root, source_seed=source_seed,
                source_each=source_each, task=task, frontier=frame_frontier,
                policy=policy, course=source_context.release.curriculum,
                source_profile_parameters=profile)
            ast = replace(atom_ast, frames=(tree,))
            current = atom_config.frontier
            config = FrameCompilerConfig(
                tuple(body.parse() for body in manifest.bodies), manifest.schema_map,
                None, task, current, policy)
            approved = project_context(
                projection.envelopes, task, current, policy)
        else:
            atom_ast, atom_config = public_formal_atom_context(
                authenticated.selection, row, source_graph,
                source_root=source_context.source_root, source_seed=source_seed,
                source_each=source_each, task=task, frontier=frontier,
                policy=policy, course=source_context.release.curriculum,
                source_profile_parameters=profile)
            ast, approved, config, current = (
                atom_ast, None, atom_config, atom_config.frontier)
        source_asts.append(ast)
        source_graphs.append(source_graph)
        projections.append(approved)
        configs.append(config)
        tasks.append(task)
        frontiers.append(current)
        policies.append(policy)
    projections = tuple(projections)
    by_tokens = dict(zip((tuple(row["tokens"]) for row in rows), source_asts))
    if len(by_tokens) != len(rows):
        _invalid("FACTORY_TRAINING_AMBIGUOUS_SOURCE_PREFIX")
    by_ast = dict(zip((id(ast) for ast in source_asts), projections))
    training = compile_training_batch(
        rows, source_context, {"context": 1024}, delivery=delivery,
        delivery_capability=capability,
        delivery_release_sha256=source_context.release.release_sha256,
        teacher_strategy=teacher_strategy,
        requested_count=requested_count, optimizer_step_seed=optimizer_step_seed,
        source_authority=source_context.bind_rows(
            rows, seed=source_seed, capability=capability, each=source_each),
        rehearsal_by_id=(rehearsal_by_id or {}),
        visible_ends={row["id"]: len(row["tokens"]) for row in rows},
        source_ast_for=lambda tokens: by_tokens[tuple(tokens)],
        compiler_config=tuple(configs), feature_artifact_path=feature_artifact_path,
        answer_plan_for=lambda prefix, release, cap, kind: training_answer_plan(
            prefix, release, kind, generation_binding),
        frames_for_ast=lambda ast: (() if by_ast[id(ast)] is None
                                    else by_ast[id(ast)].envelopes),
        task_scope=tuple(tasks), source_frontier=tuple(frontiers),
        eligibility_policy=tuple(policies),
        generation_binding=generation_binding,
        atlas_selection=authenticated.selection)
    compiled_rows = []
    for index, (row, ast, projection, source_graph, config) in enumerate(zip(
            rows, source_asts, projections, source_graphs, configs)):
        approved_config = (config if projection is None
                           else replace(config, approved=projection))
        prefix = training.rows[index].model_input.prefix
        compiled_frame_rows = CompiledFrameRows(
            (prefix,), (prefix.positions,), ((True,) * len(prefix.positions),))
        if projection is None:
            compiled = CompiledEncoderInput(
                compiled_frame_rows, (approved_config,), authenticated.features,
                candidate.extents)
        else:
            receipt = validate_partial_visible_forest(prefix, ast, approved_config)
            compiled = CompiledEncoderInput(
                compiled_frame_rows, (approved_config,), authenticated.features,
                candidate.extents, source_asts=(ast,),
                partial_forest_receipts=(receipt,))
        source = SourceAtomRow(
            authenticated.selection, row, source_graph,
            Path(source_context.source_root), source_seed, source_each,
            source_context.release.curriculum, profile)
        compiled_rows.append(bind_compiled_training_batch(
            training, compiled, (source,), authenticated.schema,
            row_index=index))
    prepared = PreparedFactoryTrainingBatch(training, tuple(compiled_rows))
    prepared.__post_init__()
    return prepared


__all__ = ("PreparedFactoryTrainingBatch", "prepare_factory_training_batch")
