"""Real pinned copular source inputs with disposable public-formal policy."""
import os
from pathlib import Path

from bilqis_mlx.live_grade_c import registry_graph
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextPolicy, SourceFrontier, TaskScope,
)
from bilqis_mlx.semantics.frame_compiler import compile_prefix
from bilqis_mlx.source_adapters.atoms.admission import public_formal_atom_context
from bilqis_mlx.source_adapters.atom_binding import build_source_atom_handoff
from bilqis_mlx.source_adapters.copular import CAPABILITY, GENERATOR, ORACLE
from bilqis_mlx.source_adapters.copular_curriculum import expanded_graph
from bilqis_mlx.source_adapters.school import live_source_registry

ROOT = Path(__file__).resolve().parents[4]
REAL_BUNDLE = os.environ.get("BILQIS_A01_ATLAS_BUNDLE", "")
RELEASE = "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306"


def source_case(*, visible_end=None):
    graph = expanded_graph(registry_graph())
    source_row = live_source_registry().require(GENERATOR, ORACLE).draw(
        source_root=ROOT, graph=graph, course=None, capability=CAPABILITY, seed=17, each=1)[0]
    selection = AtlasArtifactSelection(
        REAL_BUNDLE, "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7",
        RELEASE, "f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec")
    end = len(source_row["tokens"]) if visible_end is None else visible_end
    task = TaskScope(
        "disposable:reviewer", "disposable:tenant", "TRAINING", RELEASE,
        "disposable:region", "source:formal", observed_frontier=0,
        effective_time=0, causal_prefix_end=end)
    policy = ContextPolicy(
        "disposable:policy", 1, 1, ("TRAINING",), (PUBLIC_FORMAL,),
        (task.jurisdiction,), (task.scope,), (PUBLIC_FORMAL,), (), ())
    args = dict(source_root=ROOT, source_seed=17, source_each=1)
    ast, config = public_formal_atom_context(
        selection, source_row, graph, task=task, frontier=SourceFrontier(1, 1, ()),
        policy=policy, **args)
    compiled = compile_prefix(ast, end, RELEASE, config)
    handoff = build_source_atom_handoff(compiled, config, selection, source_row, graph, **args)
    return ast, config, compiled, handoff, selection, source_row, graph, args
