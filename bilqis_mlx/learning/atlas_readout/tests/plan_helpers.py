"""Source-typed disposable frame plans for B10.2."""
from dataclasses import replace
from bilqis_mlx.semantics.tests.test_atlas_features import _snapshot
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.atlas_projection import AbiEntry
from bilqis_mlx.semantics.frame_schema import ConceptRef, SourceSpan
from bilqis_mlx.semantics.released_frame_schemas import seal_released_frame_schemas, load_released_frame_schemas
from bilqis_mlx.learning.atlas_readout.tests.helpers import frame_release
from bilqis_mlx.learning.atlas_readout.roles import compile_frame_output


def output_domain():
    schema, _, features = frame_release()
    snapshot = _snapshot()
    prefix = tuple(AbiEntry(i, 0, i, f'urn:fixture:{i}', f'fixture.{i}',
                            'synthetic:source', False, False, 'RESERVED') for i in range(11))
    entries = prefix + snapshot.abi_entries
    snapshot = replace(snapshot, abi_entries=entries,
        semantic_lookup=tuple(sorted((e.semantic_id, e.index) for e in entries)),
        concept_lookup=(('urn:concept:A', 0),))
    schema = replace(schema, roles=tuple(replace(r, allowed_type_ids=('urn:type:Entity',))
                                        for r in schema.roles))
    manifest = seal_released_frame_schemas((schema,),
        SchemaTagMap.from_schemas(snapshot.release_sha256, (schema,)), snapshot)
    schemas = load_released_frame_schemas(manifest.canonical_bytes(),
        expected_sha256=manifest.digest, snapshot=snapshot)
    return compile_frame_output(schema, schemas, features), snapshot


def concept():
    return ConceptRef('urn:concept:A', _snapshot().release_sha256, 11,
                      ('urn:type:Entity',), 'synthetic:source')


def plan(decisions, prefix=8, maximum=64):
    from bilqis_mlx.learning.atlas_readout.plan import AnswerPlan
    domain, snapshot = output_domain()
    return AnswerPlan('answer.structured-frame/v1', prefix, tuple(decisions), domain,
                      snapshot, SourceSpan(0, min(prefix, 8)), 'generation:fixture', maximum)
