"""Source-row records and preparation helpers for Factory training."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from bilqis_mlx.learning.frame_encoder import CompiledEncoderInput
from bilqis_mlx.learning.source_atoms import SourceAtomRow
from bilqis_mlx.runtime.b11_source_execution_authority import (
    B11SourceExecutionAuthority, require_b11_source_execution_authority_current,
)
from bilqis_mlx.semantics.context_eligibility import (
    ApprovedContextProjection, ContextPolicy, SourceFrontier, TaskScope,
    project_context,
)
from bilqis_mlx.semantics.frame_adapters import public_formal_context
from bilqis_mlx.semantics.frame_adapters.public_formal import (
    _public_formal_context_from_verified_row,
)
from bilqis_mlx.semantics.frame_compiler import (
    CompiledFrameBatch, CompiledFrameRows, FrameCompilerConfig,
    validate_partial_visible_forest,
)
from bilqis_mlx.semantics.source_atom_binding import SourceRowWitness
from bilqis_mlx.source_adapters.atoms.admission import (
    _public_formal_atom_context_from_witness,
)
from bilqis_mlx.source_adapters.atoms.authority import canonical_graph_for
from bilqis_mlx.source_adapters.atom_binding import (
    _verified_source_row_witness, verify_source_row,
)

from .atlas_training_contracts import _invalid
from .factory_training_context import public_training_context


@dataclass(frozen=True)
class _FactoryMotifPlanningInput:
    source_adapter: object
    row: dict
    atlas_selection: object
    source_root: Path
    source_graph: dict
    task: TaskScope
    frontier: SourceFrontier
    policy: ContextPolicy
    source_seed: int
    source_each: int
    source_profile_parameters: dict | None
    course: object
    formal_projection: ApprovedContextProjection
    formal_frontier: SourceFrontier

    def __post_init__(self) -> None:
        if (not isinstance(self.row, dict)
                or not isinstance(self.source_root, Path)
                or not isinstance(self.source_graph, dict)
                or type(self.task) is not TaskScope
                or type(self.frontier) is not SourceFrontier
                or type(self.policy) is not ContextPolicy
                or type(self.formal_projection) is not ApprovedContextProjection
                or type(self.formal_frontier) is not SourceFrontier
                or type(self.source_seed) is not int or self.source_seed < 0
                or type(self.source_each) is not int or self.source_each < 1
                or (self.source_profile_parameters is not None
                    and not isinstance(self.source_profile_parameters, dict))):
            _invalid("FACTORY_MOTIF_PLANNING_INPUT_INVALID")


@dataclass(frozen=True)
class _FactorySourceRow:
    row: dict
    source_adapter: object
    manifest: object
    profile: object
    source_seed: int
    source_each: int
    source_id: str
    frames: tuple
    ast: object
    projection: object
    source_graph: object
    config: FrameCompilerConfig
    task: TaskScope
    frontier: SourceFrontier
    policy: ContextPolicy
    source_inventory: tuple
    formal_projection: ApprovedContextProjection
    formal_frontier: SourceFrontier
    source_witness: SourceRowWitness
    b11_proof: object | None = None


@dataclass(frozen=True)
class _PreparedB11SourceBinding:
    prefix: CompiledFrameBatch
    config: FrameCompilerConfig
    source: SourceAtomRow
    authority: B11SourceExecutionAuthority
    _compiled_input: CompiledEncoderInput | None = field(
        default=None, init=False, repr=False, compare=False)

    def require_current(self):
        return require_b11_source_execution_authority_current(
            self.authority, self.prefix, self.config, self.source)


def _prepared_b11_compiled_input(
        prepared, features, extents, packed_owner, *, source_ast=None):
    if type(prepared) is not _PreparedB11SourceBinding:
        _invalid("FACTORY_TRAINING_PREPARED_B11_INVALID")
    cached = prepared._compiled_input
    if cached is not None:
        cached_ast = None if cached.source_asts is None else cached.source_asts[0]
        if (cached.compiled.rows[0] is not prepared.prefix
                or cached.compiler_configs[0] is not prepared.config
                or cached.features is not features
                or cached.extents is not extents
                or cached.packed_frame_artifact_owner is not packed_owner
                or cached_ast is not source_ast):
            _invalid("FACTORY_TRAINING_PREPARED_B11_COMPILED_DRIFT")
        cached.__post_init__()
        return cached
    prefix = prepared.prefix
    compiled_rows = CompiledFrameRows(
        (prefix,), (prefix.positions,), ((True,) * len(prefix.positions),))
    from bilqis_mlx.learning.frame_encoder.compiled import (
        _compiled_encoder_input_with_packed_owner,
    )
    if source_ast is None:
        compiled = _compiled_encoder_input_with_packed_owner(
            compiled_rows, (prepared.config,), features, extents, packed_owner)
    else:
        receipt = validate_partial_visible_forest(
            prefix, source_ast, prepared.config)
        compiled = _compiled_encoder_input_with_packed_owner(
            compiled_rows, (prepared.config,), features, extents, packed_owner,
            source_asts=(source_ast,), partial_forest_receipts=(receipt,))
    object.__setattr__(prepared, "_compiled_input", compiled)
    return compiled


def _prepare_source_row(source_context, authenticated, manifest,
                        profile, row, *, capability, source_seed, source_each,
                        prequalified=False):
    if row.get("capability") != capability:
        _invalid("FACTORY_TRAINING_CAPABILITY_MISMATCH")
    source_adapter = source_context.source_registry.resolve_owner(row.get("generator"))
    source_graph = canonical_graph_for(
        row.get("generator"), source_context.source_root, row=row)
    task, frontier, policy = public_training_context(
        authenticated.features.semantic_release, capability, len(row.get("tokens", ())))
    if prequalified:
        projection, frame_frontier = _public_formal_context_from_verified_row(
            source_adapter, row, authenticated.snapshot,
            source_root=source_context.source_root, graph=source_graph,
            task_scope=task, source_frontier=frontier, policy=policy)
        source_witness, reason = _verified_source_row_witness(
            row, expected_adapter_id=source_adapter.descriptor.adapter_id)
    else:
        projection, frame_frontier = public_formal_context(
            source_adapter, row, authenticated.snapshot,
            source_root=source_context.source_root, graph=source_graph,
            task_scope=task, source_frontier=frontier, policy=policy,
            source_seed=source_seed, source_each=source_each,
            source_profile_parameters=profile,
            course=source_context.release.curriculum)
        source_witness, reason = verify_source_row(
            row, source_graph, source_root=source_context.source_root,
            source_seed=source_seed, source_each=source_each,
            course=source_context.release.curriculum,
            source_profile_parameters=profile)
    if type(projection) is not ApprovedContextProjection:
        _invalid("FACTORY_TRAINING_CONTEXT_HELD")
    if source_witness is None:
        _invalid("FACTORY_TRAINING_SOURCE_ROW_HELD:" + str(reason))
    from bilqis_mlx.runtime.factory_training_context import (
        _source_frame_inventory_from_context,
        _source_frame_inventory_from_verified_context,
    )
    source_inventory = (
        _source_frame_inventory_from_verified_context(
            source_context, row, authenticated, manifest)
        if prequalified else
        _source_frame_inventory_from_context(
            source_context, row, authenticated, manifest))
    source_id, frames = source_inventory
    atom_ast, atom_config = _public_formal_atom_context_from_witness(
        authenticated.selection, authenticated.snapshot, row, source_graph,
        source_witness, source_root=source_context.source_root, task=task,
        frontier=(frame_frontier if frames else frontier), policy=policy)
    if frames:
        ast = replace(atom_ast, frames=frames)
        current = atom_config.frontier
        config = atom_config if manifest is None else FrameCompilerConfig(
            tuple(body.parse() for body in manifest.bodies), manifest.schema_map,
            None, task, current, policy)
        approved = project_context(projection.envelopes, task, current, policy)
    else:
        ast, approved, config, current = atom_ast, None, atom_config, atom_config.frontier
    return _FactorySourceRow(
        row, source_adapter, manifest, profile, source_seed, source_each,
        source_id, frames, ast, approved, source_graph, config, task, current,
        policy, source_inventory, projection, frame_frontier, source_witness)


__all__ = (
    "_FactoryMotifPlanningInput", "_FactorySourceRow", "_PreparedB11SourceBinding",
    "_prepare_source_row", "_prepared_b11_compiled_input",
)
