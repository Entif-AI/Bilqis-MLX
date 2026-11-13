"""Native answer labels reuse the Factory registry and B02 tied active rows."""
import hashlib
import mlx.core as mx
from lib.ithkuil.src.skos.publication import json_bytes
from bilqis_mlx.factory.answers import AnswerModalityRegistry, RegisteredAnswerModality
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.learning.frame_embeddings.banks import semantic_logits
from bilqis_mlx.semantics.atlas_projection import FrozenAtlasSnapshot
from .records import (
    VALUE_BINDING_SCHEMA, ValueHeadBinding, TypedHeadLogits,
    invalid, validate_hidden,
)


def _active_symbols(snapshot):
    if type(snapshot) is not FrozenAtlasSnapshot:
        invalid()
    entries = snapshot.abi_entries
    if (not entries or len({e.symbol for e in entries}) != len(entries)
            or len({e.index for e in entries}) != len(entries)
            or any(type(e.index) is not int or e.index < 0
                   or (e.bank, e.row) != divmod(e.index, ModelTopologySpecV2.semantic_bank_rows) for e in entries)):
        invalid()
    active = sorted(e.index for e in entries if e.active)
    if hashlib.sha256(json_bytes(active)).hexdigest() != snapshot.active_set_sha256:
        invalid()
    return {e.symbol: e.index for e in entries if e.active}


def bind_value_head(kind, values, snapshot, registry):
    """Resolve task labels through existing native mappings and the A01 snapshot."""
    symbols = _active_symbols(snapshot)
    if (type(values) is not tuple or not values
            or any(type(v) is not str or not v for v in values)
            or len(set(values)) != len(values)
            or type(kind) is not str
            or not isinstance(registry, AnswerModalityRegistry)):
        invalid()
    if kind == 'semantic_token':
        identities, modality, registered = values, 'semantic_token', None
    else:
        registered = registry.require(kind)
        if registered.canonicalize(values) != values:
            invalid()
        identities = tuple(registered.resolve_identity(v) for v in values)
        modality = registered.descriptor.adapter_id
    if (len(set(identities)) != len(identities)
            or any(v not in symbols for v in identities)):
        invalid()
    return ValueHeadBinding(kind, modality, values, identities,
                            tuple(symbols[v] for v in identities), snapshot, registered)


def value_logits(hidden, binding, banks):
    """Score only source-bound legal labels, in the task's original label order."""
    validate_hidden(hidden)
    if (type(binding) is not ValueHeadBinding
            or binding.schema_version != VALUE_BINDING_SCHEMA):
        invalid()
    symbols = _active_symbols(binding.snapshot)
    if binding.kind == 'semantic_token':
        expected_identities, modality = binding.values, 'semantic_token'
        if binding.adapter is not None:
            invalid()
    else:
        adapter = binding.adapter
        if (type(adapter) is not RegisteredAnswerModality
                or adapter.descriptor.kind != binding.kind
                or adapter.canonicalize(binding.values) != binding.values):
            invalid()
        expected_identities = tuple(adapter.resolve_identity(v) for v in binding.values)
        modality = adapter.descriptor.adapter_id
    if binding.identities != expected_identities or binding.modality_id != modality:
        invalid()
    if (not binding.values or len(set(binding.values)) != len(binding.values)
            or len(binding.identities) != len(binding.values)
            or any(v not in symbols for v in binding.identities)
            or binding.abi_indices != tuple(symbols[v] for v in binding.identities)):
        invalid()
    indexed = semantic_logits(hidden, banks)
    if (banks[0].semantic_release != binding.semantic_release
            or banks[0].active_semantic_digest != binding.active_semantic_digest):
        invalid()
    offsets = {index: offset for offset, index in enumerate(indexed.indices)}
    if any(index not in offsets for index in binding.abi_indices):
        invalid()
    logits = indexed.logits[..., mx.array([offsets[i] for i in binding.abi_indices])]
    return TypedHeadLogits(logits, binding.values, binding.modality_id,
                           binding.semantic_release)
