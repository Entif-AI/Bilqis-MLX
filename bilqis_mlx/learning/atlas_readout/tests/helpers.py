"""Disposable source records and CPU tensors, never learner state."""
from dataclasses import replace
import hashlib
import mlx.core as mx
from lib.ithkuil.src.skos.publication import json_bytes
from bilqis_mlx.learning.frame_embeddings.banks import SemanticBankView
from bilqis_mlx.semantics.atlas_projection import AbiEntry
from bilqis_mlx.semantics.tests.test_atlas_features import _snapshot, _features
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_schema import FrameSchema, RoleSpec
from bilqis_mlx.semantics.released_frame_schemas import (
    seal_released_frame_schemas, load_released_frame_schemas,
)


def snapshot():
    entries = tuple(AbiEntry(index, index // 8192, index % 8192,
                            'urn:' + symbol, symbol, 'synthetic:source',
                            active, True, 'FIXTURE')
                    for index, symbol, active in (
                        (11, 'cogal.value.false', True),
                        (12, 'cogal.value.true', True),
                        (13, 'school.number.0', True),
                        (14, 'school.number.1', True),
                        (8193, 'bank1', True), (8194, 'inactive', False)))
    digest = hashlib.sha256(json_bytes([e.index for e in entries if e.active])).hexdigest()
    return replace(_snapshot(), abi_entries=entries, active_set_sha256=digest,
                   semantic_lookup=tuple(sorted((e.semantic_id, e.index) for e in entries)))


def banks(source):
    result = []
    for bank_index in range(2):
        weights = mx.zeros((8192, 768), dtype=mx.float32)
        active = tuple(e.row for e in source.abi_entries if e.bank == bank_index and e.active)
        for row in active:
            weights = weights.at[row, 0].add(row + bank_index)
        result.append(SemanticBankView(bank_index, weights, active,
                                      source.release_sha256, source.active_set_sha256))
    return tuple(result)


def frame_release():
    source = _snapshot()
    schema = FrameSchema('frame:fixture', 1, 'source:fixture',
                         (RoleSpec('agent', ('Entity',), 1, 1),
                          RoleSpec('theme', ('Entity',), 0, 2)),
                         'ORDERED', 'fixture')
    features = replace(_features(),
        role_map=(('UNKNOWN', 0), ('NONE', 1), ('agent', 2), ('theme', 3)),
        schema_map=(('UNKNOWN', 0), ('NONE', 1), (schema.schema_id, 2)))
    manifest = seal_released_frame_schemas((schema,),
        SchemaTagMap.from_schemas(source.release_sha256, (schema,)), source)
    released = load_released_frame_schemas(manifest.canonical_bytes(),
        expected_sha256=manifest.digest, snapshot=source)
    return schema, released, features


def role_parameters(features):
    table = mx.zeros((512, 128), dtype=mx.float32)
    for i, role in enumerate(('agent', 'theme')):
        table = table.at[dict(features.role_map)[role], i].add(1)
    return {'features.role': table,
            'readout.role_query': mx.eye(128, 768, dtype=mx.float32)}
