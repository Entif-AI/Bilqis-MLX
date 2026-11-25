"""Share differentiable atom composition within one physical learning batch."""
from collections import defaultdict

import mlx.core as mx

from bilqis_mlx.learning.frame_embeddings.common import FactorGate
from bilqis_mlx.runtime.model_topology_v2 import FEATURE_NONE_ROW

from . import embedding


def _row_coordinates(row, config, source):
    indices = source.learning_abi_indices
    if type(indices) is not tuple or len(indices) != row.visible_end or not indices:
        embedding.invalid("BAMF_SOURCE_ATOM_INPUT_INVALID")
    return tuple((index, config.task.scope) for index in indices)


def _restore_order(groups, ordinals):
    if len(groups) == 1:
        return groups[0]
    order = sorted(range(len(ordinals)), key=ordinals.__getitem__)
    return mx.take(mx.concatenate(groups, axis=0), mx.array(order, dtype=mx.int32), axis=0)


def _gather_identity_rows(banks, coordinates, bank_size):
    by_bank = defaultdict(list)
    for ordinal, (index, _scope) in enumerate(coordinates):
        bank, row = divmod(index, bank_size)
        by_bank[bank].append((ordinal, row))
    groups, ordinals = [], []
    for bank, items in by_bank.items():
        indices = mx.array([row for _, row in items], dtype=mx.int32)
        groups.append(mx.take(banks[bank].weights, indices, axis=0))
        ordinals.extend(ordinal for ordinal, _ in items)
    return _restore_order(groups, ordinals)


def _categorical_batch(table, rows, overflows):
    values = mx.take(table, mx.array(rows, dtype=mx.int32), axis=0)
    if any(item is not None for item in overflows):
        zero = (0.0,) * table.shape[-1]
        values = values + mx.array(tuple(zero if item is None else item for item in overflows),
                                   dtype=mx.float32)
    return values


def _type_batch(table, features):
    by_count = defaultdict(list)
    for ordinal, feature in enumerate(features):
        rows = feature.type_rows or (FEATURE_NONE_ROW,)
        overflow = dict(feature.type_overflow)
        extras = tuple(overflow.get(item) for item in feature.type_ids) or (None,)
        by_count[len(rows)].append((ordinal, rows, extras))
    groups, ordinals = [], []
    for count, items in by_count.items():
        gathered = _categorical_batch(
            table, tuple(row for _, rows, _ in items for row in rows),
            tuple(extra for _, _, extras in items for extra in extras))
        groups.append(mx.mean(gathered.reshape(len(items), count, table.shape[-1]), axis=1))
        ordinals.extend(ordinal for ordinal, _, _ in items)
    return _restore_order(groups, ordinals)


def _batch_factor_terms(owned, features):
    """Compute each released feature projection as one differentiable matrix product."""
    types = _type_batch(owned["features.type"], features)
    role = _categorical_batch(owned["features.role"],
                              tuple(row.role_row for row in features),
                              tuple(row.role_overflow for row in features))
    schema = _categorical_batch(owned["features.schema"],
                                tuple(row.schema_row for row in features),
                                tuple(row.schema_overflow for row in features))
    graph = mx.array(tuple(row.graph64 for row in features), dtype=mx.float32)
    gates = mx.sigmoid(owned["features.gates"])
    return (gates[FactorGate.TYPE] * (types @ owned["features.project_type"].T),
            gates[FactorGate.ROLE] * (role @ owned["features.project_role"].T),
            gates[FactorGate.SCHEMA] * (schema @ owned["features.project_schema"].T),
            gates[FactorGate.GRAPH] * (graph @ owned["features.project_graph"].T))


def _compose_unique(coordinates, banks, features, snapshot, prepared):
    spec, owned = prepared.spec, prepared.owned
    feature_rows = []
    for index, scope in coordinates:
        entry = snapshot.abi(index)
        feature_rows.append(embedding.generation_feature_row(
            snapshot, features, entry.semantic_id, index, scope,
            active_indices=prepared.active_indices))
    combined = _gather_identity_rows(banks, coordinates, spec.semantic_bank_rows)
    for term in _batch_factor_terms(owned, tuple(feature_rows)):
        combined = combined + term
    combined = combined + owned["features.local_slot"][0]
    return combined * mx.rsqrt(
        mx.mean(combined * combined, axis=-1, keepdims=True)
        + spec.rms_norm_epsilon) * owned["features.norm"]


def learning_first_source_batch_vectors(
        rows, configs, sources, features, banks, snapshot, prepared):
    """Gather each bank once; restore every original atom occurrence and row."""
    if snapshot is None:
        embedding.invalid("BAMF_SOURCE_ATOM_INPUT_INVALID")
    row_keys = tuple(_row_coordinates(row, config, source)
                     for row, config, source in zip(rows, configs, sources, strict=True))
    unique = tuple(dict.fromkeys(key for keys in row_keys for key in keys))
    vectors = _compose_unique(unique, banks, features, snapshot, prepared)
    positions = {key: index for index, key in enumerate(unique)}
    occurrences = mx.take(vectors, mx.array([
        positions[key] for keys in row_keys for key in keys], dtype=mx.int32), axis=0)
    result = []
    offset = 0
    for row, source, keys in zip(rows, sources, row_keys, strict=True):
        end = offset + len(keys)
        handoff = embedding._LearningSourceHandoff.from_row(
            row.source_instance_id, source.learning_abi_indices)
        result.append((occurrences[offset:end], handoff))
        offset = end
    return tuple(result)
