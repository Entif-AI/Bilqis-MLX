"""Differentiable raw-atom vectors from the actual released B01 parameters."""
import mlx.core as mx

from ...semantics.atlas_features import build_feature_manifest
from ...semantics.atlas_snapshot import load_pinned_atlas_snapshot
from ...semantics.source_atom_binding.common import invalid
from ...source_adapters.atom_binding import (
    build_source_atom_handoff, require_pinned_embedding_ready,
)
from ..frame_embeddings import (
    SemanticBankView, _released_factor_terms, _validate_banks,
    embedding_parameter_view,
)
from ...runtime.model_topology_v2 import ModelTopologySpecV2
from .inputs import SourceAtomRow


def source_atom_vectors(parameters, compiled, config, source, features, feature_schema, extents):
    """Recheck source/rights before gathering any identity tensor.

    Native formal signatures remain source metadata. A06 alone owns categorical
    feature types. Unframed atoms use its existing NONE role/schema and local
    slot zero, without casting the atom to a caller-created ConceptRef.
    """
    if type(source) is not SourceAtomRow:
        invalid("BAMF_SOURCE_ATOM_INPUT_INVALID")
    snapshot = load_pinned_atlas_snapshot(source.selection)
    expected_features = build_feature_manifest(snapshot, feature_schema)
    minimum_bank_count = 1 + max(
        (entry.bank for entry in snapshot.abi_entries if entry.active), default=-1)
    if (features != expected_features or extents.factor_map_digest != features.digest
            or extents.active_semantic_digest != snapshot.active_set_sha256
            or extents.semantic_bank_count < minimum_bank_count):
        invalid("BAMF_SOURCE_ATOM_GENERATION_DRIFT")
    handoff = build_source_atom_handoff(
        compiled, config, source.selection, source.source_row, source.graph,
        **source.replay_arguments())
    require_pinned_embedding_ready(
        handoff, compiled, config, source.selection, source.source_row,
        source.graph, **source.replay_arguments())
    spec = ModelTopologySpecV2()
    owned = embedding_parameter_view(parameters, spec=spec, extents=extents)
    banks = tuple(SemanticBankView(
        index, owned[f"identity.bank.{index}"],
        tuple(entry.row for entry in snapshot.abi_entries if entry.bank == index and entry.active),
        snapshot.release_sha256, snapshot.active_set_sha256)
        for index in range(extents.semantic_bank_count))
    _validate_banks(banks)
    vectors = []
    for binding in handoff.bindings:
        row = features.features_for(
            binding.candidate_semantic_id, "NONE", "NONE", config.task.scope)
        if row.abi_index != binding.candidate_abi_index:
            invalid("BAMF_SOURCE_ATOM_FEATURE_ABI_DRIFT")
        bank_index, bank_row = divmod(row.abi_index, spec.semantic_bank_rows)
        if bank_row not in banks[bank_index].active_rows:
            invalid("BAMF_SOURCE_ATOM_INACTIVE_IDENTITY")
        factors = _released_factor_terms(owned, row)
        value = banks[bank_index].weights[bank_row]
        for term in factors:
            value = value + term
        value = value + owned["features.local_slot"][0]
        vectors.append(value)
    combined = mx.stack(vectors)
    vectors = combined * mx.rsqrt(
        mx.mean(combined * combined, axis=-1, keepdims=True) + spec.rms_norm_epsilon
    ) * owned["features.norm"]
    return vectors, banks, handoff
