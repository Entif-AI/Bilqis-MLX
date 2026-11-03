"""Canonical A01/A03/A05/A13 source inputs for public B06 verification."""
from dataclasses import dataclass, replace
import os

from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.semantics.atlas_features import AtlasFeatures, FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas_projection import FrozenAtlasSnapshot
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection, load_pinned_atlas_snapshot
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ApprovedContextProjection, ContextPolicy, SourceFrontier, TaskScope,
)
from bilqis_mlx.semantics.frame_adapters import bind_registered_source_row, public_formal_context
from bilqis_mlx.semantics.frame_compiler import FrameCompilerConfig, StreamingAST
from bilqis_mlx.semantics.frame_schema import FrameInstance, SourceSpan
from bilqis_mlx.semantics.released_frame_schemas import _load_pinned_released_frame_schemas
from bilqis_mlx.semantics.tests.frame_adapters.helpers import SOURCE_ROOT
from bilqis_mlx.source_adapters.atoms.admission import public_formal_atom_context
from bilqis_mlx.source_adapters.school import A_ORACLE, live_source_registry


SEED = 31
EACH = 2
REAL_BUNDLE = os.environ.get("BILQIS_A01_ATLAS_BUNDLE", "")


@dataclass(frozen=True)
class SourceRefinementCase:
    selection: AtlasArtifactSelection
    snapshot: FrozenAtlasSnapshot
    row: dict
    graph: dict
    ast: StreamingAST
    config: FrameCompilerConfig
    schema: FeatureSchema
    features: AtlasFeatures
    projection: ApprovedContextProjection


def source_refinement_case():
    selection = AtlasArtifactSelection(
        REAL_BUNDLE,
        "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7",
        "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306",
        "f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec")
    snapshot = load_pinned_atlas_snapshot(selection)
    adapter = live_source_registry().require("bilqis_mlx.grade_a_probe.make_record", A_ORACLE)
    graph = read_sources(SOURCE_ROOT)[2]
    row = adapter.draw(source_root=SOURCE_ROOT, graph=graph, course=None,
                       capability="A.IDENTITY", seed=SEED, each=EACH)[0]
    visible_end = len(row["tokens"])
    task = TaskScope("fixture:student", "fixture:tenant", "TRAINING",
                     snapshot.release_sha256, "fixture:region", "fixture:scope",
                     observed_frontier=3, effective_time=5, causal_prefix_end=visible_end)
    policy = ContextPolicy(
        "fixture:policy", 1, 1, ("TRAINING",), (PUBLIC_FORMAL,),
        (task.jurisdiction,), (task.scope,), (PUBLIC_FORMAL,),
        ((PUBLIC_FORMAL, PUBLIC_FORMAL),),
        tuple((PUBLIC_FORMAL,) * count for count in range(3, 25)))
    projection, frontier = public_formal_context(
        adapter, row, snapshot, source_root=SOURCE_ROOT, graph=graph,
        task_scope=task, source_frontier=SourceFrontier(1, 1, ()),
        policy=policy, source_seed=SEED, source_each=EACH)
    ast, config = public_formal_atom_context(
        selection, row, graph, source_root=SOURCE_ROOT, source_seed=SEED,
        source_each=EACH, task=task, frontier=frontier, policy=policy)
    tree = bind_registered_source_row(
        adapter, row, snapshot, source_root=SOURCE_ROOT, graph=graph,
        source_span=SourceSpan(0, visible_end), causal_prefix_end=visible_end)
    pinned = _load_pinned_released_frame_schemas("micro", selection)
    config = replace(config, approved=projection, schema_map=pinned.manifest.schema_map,
                     schemas=tuple(body.parse() for body in pinned.manifest.bodies))
    framed = tuple(item for item in projection.envelopes if type(item.frame) is FrameInstance)
    schemas = tuple(sorted({item.frame.frame_schema_id for item in framed}))
    roles = tuple(sorted({binding.role_id for item in framed for binding in item.frame.bindings}))
    schema = FeatureSchema(roles, schemas, source_bindings=tuple(
        (schema_id, adapter.descriptor.adapter_id) for schema_id in schemas))
    return SourceRefinementCase(selection, snapshot, row, graph,
                                replace(ast, frames=(tree,)), config,
                                schema, build_feature_manifest(snapshot, schema), projection)
