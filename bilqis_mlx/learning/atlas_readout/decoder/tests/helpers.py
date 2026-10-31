"""Synthetic source-typed fixtures; never production admission or learner state."""
from dataclasses import replace
import hashlib
import numpy as np
import mlx.core as mx
from lib.ithkuil.src.skos.publication import json_bytes
from bilqis_mlx.learning.atlas_readout import (
    AnswerPlan, DecisionSpec, DecisionKind, ControlAction, compile_frame_output,
)
from bilqis_mlx.learning.atlas_readout.tests.helpers import frame_release
from bilqis_mlx.learning.frame_embeddings import SemanticBankView
from bilqis_mlx.runtime.model_topology_v2 import (
    ModelTopologySpecV2, GenerationExtents, expected_bamf_shapes,
)
from bilqis_mlx.semantics.atlas_projection import AbiEntry
from bilqis_mlx.semantics.context_eligibility import project_context
from bilqis_mlx.semantics.frame_schema import ConceptRef, SourceSpan
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_compiler import compile_prefix, PositionKind
from bilqis_mlx.semantics.released_frame_schemas import (
    seal_released_frame_schemas, load_released_frame_schemas,
)
from bilqis_mlx.semantics.tests.test_atlas_features import _snapshot
from bilqis_mlx.semantics.tests.test_frame_compiler import _mixed_case, RELEASE


def case(*, epistemic=False):
    from bilqis_mlx.learning.atlas_readout.decoder.inputs import DecoderMemory, ReadoutSemantics
    source = _snapshot(definitions=(("urn:concept:A", ("urn:type:Entity",)),
                                    ("urn:concept:B", ("urn:type:Entity",))))
    reserved = tuple(AbiEntry(i, 0, i, f"urn:fixture:{i}", f"fixture.{i}",
                             "synthetic:source", False, False, "RESERVED") for i in range(11))
    entries = reserved + source.abi_entries
    if epistemic:
        entries += tuple(AbiEntry(13+i,0,13+i,f'urn:fixture:epistemic:{i}',f'fixture.epistemic.{i}',
                                  'synthetic:source',True,True,'FIXTURE') for i in range(3))
    active = tuple(e.index for e in entries if e.active)
    source = replace(source, abi_entries=entries,
                     active_set_sha256=hashlib.sha256(json_bytes(list(active))).hexdigest(),
                     semantic_lookup=tuple(sorted((e.semantic_id, e.index) for e in entries)))
    schema, _, features = frame_release()
    schema = replace(schema, roles=tuple(replace(r, allowed_type_ids=("urn:type:Entity",))
                                         for r in schema.roles))
    manifest = seal_released_frame_schemas((schema,),
        SchemaTagMap.from_schemas(source.release_sha256, (schema,)), source)
    released = load_released_frame_schemas(manifest.canonical_bytes(),
        expected_sha256=manifest.digest, snapshot=source)
    domain = compile_frame_output(schema, released, features)
    extents = GenerationExtents(1, 1, source.active_set_sha256, "b" * 64, features.digest)
    rng = np.random.default_rng(469)
    params = {p.name: mx.array(rng.normal(0,.02,p.shape).astype(np.float32))
              for p in expected_bamf_shapes(ModelTopologySpecV2(), extents)
              if p.name.startswith(("readout.", "features."))}
    for key in ("readout.state_norm", "readout.output_norm"):
        params[key] = mx.ones((768,),dtype=mx.float32)
    weights = mx.zeros((8192,768),dtype=mx.float32)
    for index in active:
        weights = weights.at[index].add(mx.array(rng.normal(0,.1,768).astype(np.float32)))
    params["identity.bank.0"] = weights
    bank = SemanticBankView(0, weights, active, source.release_sha256, source.active_set_sha256)
    binding=None
    if epistemic:
        from bilqis_mlx.factory.answers import (
            AnswerModality,AnswerModalityRegistry,RegisteredAnswerModality,
        )
        from bilqis_mlx.learning.atlas_readout import bind_value_head
        labels=tuple(f'fixture:state:{i}' for i in range(5))
        symbols=tuple(e.symbol for e in entries if e.active)
        mapping=dict(zip(labels,symbols))
        adapter=RegisteredAnswerModality(
            AnswerModality('fixture_epistemic','answer.fixture-epistemic/v1',
                           hashlib.sha256(b'fixture:epistemic/v1').hexdigest()),
            tuple, mapping.__getitem__)
        registry=AnswerModalityRegistry((adapter,))
        binding=bind_value_head('fixture_epistemic',labels,source,registry)
    semantics = ReadoutSemantics(features, (bank,), extents,binding)
    ast, config = _mixed_case()
    compiled = compile_prefix(ast, 4, RELEASE, config)
    handles = {p.frame_handle for p in compiled.positions if p.kind is PositionKind.CLOSURE}
    context = project_context(tuple(e for e in config.approved.envelopes if e.frame_handle in handles),
        replace(config.task, causal_prefix_end=4), config.frontier, config.policy)
    hidden = mx.array(rng.normal(0,.1,(7,768)).astype(np.float32))
    identities = tuple(p.cache_identity for p in compiled.positions) + (("future",5),("future",6))
    memory = DecoderMemory(hidden, identities, compiled, "generation:fixture")
    concepts = tuple(ConceptRef(e.semantic_id, source.release_sha256, e.index,
                               ("urn:type:Entity",), "synthetic:source")
                     for e in entries if e.active and e.index<13)
    decisions = (
        DecisionSpec("control", "agent", 0, DecisionKind.CONTROL, (ControlAction.EMIT_VALUE,)),
        DecisionSpec("value", "agent", 0, DecisionKind.VALUE, concepts, ("control",)),
        DecisionSpec("end", None, 0, DecisionKind.CONTROL, (ControlAction.END_FRAME,), ("value",)),
    )
    plan = AnswerPlan(domain.modality_id, 5, decisions, domain, source, SourceSpan(0,4),
                      "generation:fixture")
    return memory, context, plan, semantics, params
