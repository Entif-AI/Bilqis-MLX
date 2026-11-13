"""Synthetic source-atom fixtures; none grants production source authority."""
from pathlib import Path

from bilqis_mlx.semantics.atlas_projection import AbiEntry, AtlasCounts, FrozenAtlasSnapshot
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
)
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_compiler import (
    FrameCompilerConfig, SourceAtom, StreamingAST, atom_evidence_digest, compile_prefix,
)
from bilqis_mlx.semantics.source_atom_binding import SourceRowWitness

ROOT = Path(__file__).resolve().parents[4]
RELEASE = "a" * 64


def snapshot(tokens: tuple[str, ...]) -> FrozenAtlasSnapshot:
    entries = tuple(
        AbiEntry(index, 0, index, "semantic:" + token, token,
                 "fixture", True, True, "FIXTURE")
        for index, token in enumerate(tokens))
    counts = AtlasCounts(0, 0, 0, len(entries), 1, len(entries), 0, 0, 0, 0)
    return FrozenAtlasSnapshot(
        "bilqis.semantic-atlas-snapshot/v1", "b" * 64, RELEASE, "c" * 64,
        "d" * 64, "e" * 64, "f" * 64, "1" * 64, "2" * 64,
        "3" * 64, "4" * 64, counts, (), entries, (), (), (),
        tuple((entry.semantic_id, entry.index) for entry in entries), ())


def case(tokens: tuple[str, ...], *, visible_end: int | None = None):
    ast = StreamingAST(
        "source:fixture-row",
        tuple(SourceAtom(index, token, "fixture:atom:" + str(index))
              for index, token in enumerate(tokens)), ())
    end = len(tokens) if visible_end is None else visible_end
    task = TaskScope(
        "synthetic:alice", "synthetic:tenant", "TRAINING", RELEASE,
        "synthetic:region", "synthetic:public",
        observed_frontier=3, effective_time=5, causal_prefix_end=len(tokens))
    policy = ContextPolicy(
        "fixture:policy", 1, 1, ("TRAINING",), (PUBLIC_FORMAL,),
        (task.jurisdiction,), (task.scope,), (PUBLIC_FORMAL,), (), ())
    grants = tuple(sorted((SourceGrant(
        atom.source_reference, task.principal_id, task.tenant_id, PUBLIC_FORMAL, RELEASE,
        atom_evidence_digest(ast.source_instance_id, atom, RELEASE),
        ("TRAINING",), (task.jurisdiction,), (task.scope,), 1, 1, 2, 0)
        for atom in ast.atoms), key=lambda item: item.source_handle))
    config = FrameCompilerConfig(
        (), SchemaTagMap.from_schemas(RELEASE, ()), None, task,
        SourceFrontier(1, 1, grants), policy)
    return ast, config, compile_prefix(ast, end, RELEASE, config)


def witness(tokens: tuple[str, ...]) -> SourceRowWitness:
    return SourceRowWitness(
        "source.fixture/v1", "fixture.generator/v1", "fixture.oracle/v1",
        "fixture.capability", "fixture:sense", tuple(range(len(tokens))))
