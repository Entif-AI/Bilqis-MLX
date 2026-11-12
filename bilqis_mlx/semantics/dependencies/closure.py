"""Canonical, closed executed-artifact evidence."""
from __future__ import annotations

import hashlib
import json

from . import ArtifactKind, ArtifactNode, DependencyIndex, DependencyKind, DependencyRef

SCHEMA = 'bilqis.c06.executed-artifact-closure/v1'
_NODES_REQUIRED = 'BAMF_SALIENCE_CLOSURE_NODES_REQUIRED'
_NODE_INVALID = 'CLOSURE_NODE_INVALID'
_DEPENDENCIES_INVALID = 'CLOSURE_DEPENDENCIES_INVALID'
_DEPENDENCY_RECORD_WIDTH = 2
_FIELDS = frozenset(('artifact_id', 'kind', 'content_digest', 'eligible',
                     'immediate_dependencies', 'impact', 'exigency', 'schema_version'))


def _invalid(reason):
    raise ValueError(reason)


def encode_closure_nodes(nodes):
    if type(nodes) is not tuple or not nodes:
        _invalid(_NODES_REQUIRED)
    index = DependencyIndex(nodes)
    return tuple({
        'artifact_id': node.artifact_id, 'kind': node.kind.value,
        'content_digest': node.content_digest, 'eligible': node.eligible,
        'immediate_dependencies': tuple((ref.kind.value, ref.key) for ref in node.immediate_dependencies),
        'impact': node.impact, 'exigency': node.exigency, 'schema_version': node.schema_version,
    } for node in index.nodes)


def decode_closure_nodes(records):
    if not isinstance(records, (list, tuple)) or not records:
        _invalid(_NODES_REQUIRED)
    nodes = []
    for item in records:
        if not isinstance(item, dict) or set(item) != _FIELDS:
            _invalid(_NODE_INVALID)
        deps = item['immediate_dependencies']
        if (not isinstance(deps, (list, tuple))
                or any(not isinstance(d, (list, tuple))
                       or len(d) != _DEPENDENCY_RECORD_WIDTH for d in deps)):
            _invalid(_DEPENDENCIES_INVALID)
        nodes.append(ArtifactNode(item['artifact_id'], ArtifactKind(item['kind']), item['content_digest'],
            item['eligible'], tuple(DependencyRef(DependencyKind(d[0]), d[1]) for d in deps),
            item['impact'], item['exigency'], item['schema_version']))
    result = tuple(nodes)
    DependencyIndex(result)
    return result


def canonical_closure_bytes(nodes):
    return json.dumps({'schema': SCHEMA, 'nodes': encode_closure_nodes(nodes)},
                      sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def closure_digest(nodes):
    return hashlib.sha256(canonical_closure_bytes(nodes)).hexdigest()
