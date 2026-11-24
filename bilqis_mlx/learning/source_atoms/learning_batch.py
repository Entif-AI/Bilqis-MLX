"""Share differentiable atom composition within one physical learning batch."""
from collections import defaultdict

import mlx.core as mx

from . import embedding


def _row_coordinates(row, config, source):
    indices = source.learning_abi_indices
    if type(indices) is not tuple or len(indices) != row.visible_end or not indices:
        embedding.invalid("BAMF_SOURCE_ATOM_INPUT_INVALID")
    return tuple((index, config.task.scope) for index in indices)


def _gather_identity_rows(banks, coordinates, bank_size):
    by_bank = defaultdict(list)
    for index, scope in coordinates:
        bank, row = divmod(index, bank_size)
        by_bank[bank].append(((index, scope), row))
    gathered = {}
    for bank, items in by_bank.items():
        indices = mx.array([row for _, row in items], dtype=mx.int32)
        values = mx.take(banks[bank].weights, indices, axis=0)
        gathered.update((key, values[ordinal])
                        for ordinal, (key, _) in enumerate(items))
    return gathered


def _compose_unique(coordinates, banks, features, snapshot, prepared):
    spec, owned = prepared.spec, prepared.owned
    feature_rows = {}
    for index, scope in coordinates:
        entry = snapshot.abi(index)
        feature_rows[index, scope] = embedding.generation_feature_row(
            snapshot, features, entry.semantic_id, index, scope,
            active_indices=prepared.active_indices)
    identities = _gather_identity_rows(banks, coordinates, spec.semantic_bank_rows)
    vectors = []
    for key in coordinates:
        value = identities[key]
        for term in embedding._released_factor_terms(owned, feature_rows[key]):
            value = value + term
        vectors.append(value + owned["features.local_slot"][0])
    combined = mx.stack(vectors)
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
