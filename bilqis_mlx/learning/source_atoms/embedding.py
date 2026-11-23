"""Differentiable raw-atom vectors from the actual released B01 parameters."""
from dataclasses import dataclass

import mlx.core as mx

from ...runtime.atlas_artifact_owner import AtlasFeatureArtifactOwner
from ...semantics.atlas_features import build_feature_manifest, generation_feature_row
from ...semantics.atlas.snapshot import load_pinned_atlas_snapshot
from ...semantics.source_atom_binding.common import invalid
from ...source_adapters.atom_binding import (
    _build_source_atom_handoff_from_snapshot, _require_embedding_ready_from_snapshot,
)
from ..frame_embeddings import (
    SemanticBankView, _released_factor_terms, _validate_banks,
    embedding_parameter_view,
)
from ...runtime.model_topology_v2 import ModelTopologySpecV2
from .inputs import SourceAtomRow
from ...semantics.domains import contract_digest


@dataclass(frozen=True)
class _LearningSourceHandoff:
    """Numerical source coordinates for verification-free ordinary training."""

    source_instance_id: str
    abi_indices: tuple[int, ...]
    digest: str

    @classmethod
    def from_row(cls, source_instance_id, abi_indices):
        digest = contract_digest((
            "bilqis.mlx.learning-source-handoff/v1",
            source_instance_id,
            abi_indices,
        ))
        return cls(source_instance_id, abi_indices, digest)

    def __post_init__(self):
        if (not isinstance(self.source_instance_id, str) or not self.source_instance_id
                or type(self.abi_indices) is not tuple or not self.abi_indices
                or any(type(index) is not int or index < 0 for index in self.abi_indices)
                or self.digest != contract_digest((
                    "bilqis.mlx.learning-source-handoff/v1",
                    self.source_instance_id,
                    self.abi_indices,
                ))):
            invalid("BAMF_SOURCE_ATOM_INPUT_INVALID")


def _resolve_source_embedding_authority(
    compiled, config, source, features, feature_schema, artifact_owner,
    snapshot, source_execution_authority,
):
    if (type(source) is not SourceAtomRow
            or type(artifact_owner) is not AtlasFeatureArtifactOwner):
        invalid("BAMF_SOURCE_ATOM_INPUT_INVALID")
    handoff = None
    if source_execution_authority is not None:
        from bilqis_mlx.runtime.b11_source_execution_authority import (
            b11_source_authority_launch_trusted,
            require_b11_source_execution_authority,
        )
        authority = source_execution_authority
        if not b11_source_authority_launch_trusted(
                authority, compiled, config, source):
            authority = require_b11_source_execution_authority(
                authority, compiled, config, source)
        if snapshot is not None and snapshot is not authority.snapshot:
            invalid("BAMF_SOURCE_ATOM_GENERATION_DRIFT")
        snapshot, handoff = authority.snapshot, authority.source_handoff
    elif snapshot is None:
        snapshot = load_pinned_atlas_snapshot(source.selection)
        expected_features = build_feature_manifest(snapshot, feature_schema)
        if features != expected_features:
            invalid("BAMF_SOURCE_ATOM_GENERATION_DRIFT")
    return snapshot, handoff


def _validate_source_embedding_generation(
    source, features, extents, banks, snapshot,
):
    selection = source.selection
    if (snapshot.release_sha256 != selection.release_sha256
            or snapshot.bundle_id != selection.bundle_id
            or snapshot.source_bundle_id != selection.source_bundle_id
            or features.semantic_release != selection.release_sha256
            or features.atlas_bundle_id != selection.bundle_id
            or features.source_bundle_id != selection.source_bundle_id
            or extents.factor_map_digest != features.digest
            or type(banks) is not tuple or not banks
            or any(type(bank) is not SemanticBankView for bank in banks)):
        invalid("BAMF_SOURCE_ATOM_GENERATION_DRIFT")


def _bind_source_embedding_handoff(
    compiled, config, source, features, artifact_owner, snapshot, handoff,
):
    artifact_owner.require(features)
    if handoff is None:
        handoff = _build_source_atom_handoff_from_snapshot(
            compiled, config, source.selection, snapshot, source.source_row,
            source.graph, **source.replay_arguments())
        _require_embedding_ready_from_snapshot(
            handoff, compiled, config, source.selection, snapshot,
            source.source_row, source.graph, **source.replay_arguments())
    else:
        handoff.__post_init__()
        if not handoff.embedding_ready:
            invalid("BAMF_SOURCE_ATOM_BINDING_HELD")
    return snapshot, handoff


def _source_embedding_parameters(
    parameters, source, features, extents, banks, snapshot,
):
    spec = ModelTopologySpecV2()
    owned = embedding_parameter_view(parameters, spec=spec, extents=extents)
    _validate_banks(banks)
    active_indices = tuple(
        bank.bank_index * spec.semantic_bank_rows + row
        for bank in banks for row in bank.active_rows)
    if (len(banks) != extents.semantic_bank_count
            or banks[0].semantic_release != snapshot.release_sha256
            or banks[0].active_semantic_digest != extents.active_semantic_digest
            or any(bank.weights is not owned.get(f"identity.bank.{bank.bank_index}")
                   for bank in banks)
            or any(index >= len(snapshot.abi_entries)
                   or snapshot.abi_entries[index].index != index
                   for index in active_indices)):
        invalid("BAMF_SOURCE_ATOM_GENERATION_DRIFT")
    return spec, owned


def _source_binding_feature_row(
    binding, config, features, snapshot, banks, spec,
):
    """Bind source factors only after the accepted generation activates the ABI row.

    A02/C07 may activate an append-only identity while B13 deliberately keeps the
    predecessor feature-factor manifest immutable.  In that case the immutable
    Atlas source still owns the prospective type/graph factors, while the
    generation-active bank owns admission.
    """
    abi_index = binding.candidate_abi_index
    bank_index, bank_row = divmod(abi_index, spec.semantic_bank_rows)
    if bank_index >= len(banks) or bank_row not in banks[bank_index].active_rows:
        invalid("BAMF_SOURCE_ATOM_INACTIVE_IDENTITY")

    active_indices = tuple(
        bank.bank_index * spec.semantic_bank_rows + row
        for bank in banks
        for row in bank.active_rows
    )
    row = generation_feature_row(
        snapshot,
        features,
        binding.candidate_semantic_id,
        abi_index,
        config.task.scope,
        active_indices=active_indices,
    )
    if row.abi_index != abi_index:
        invalid("BAMF_SOURCE_ATOM_FEATURE_ABI_DRIFT")
    return row, bank_index, bank_row


def _source_binding_vectors(
    handoff, config, features, banks, spec, owned, snapshot,
):
    vectors = []
    for binding in handoff.bindings:
        row, bank_index, bank_row = _source_binding_feature_row(
            binding, config, features, snapshot, banks, spec)
        factors = _released_factor_terms(owned, row)
        value = banks[bank_index].weights[bank_row]
        for term in factors:
            value = value + term
        value = value + owned["features.local_slot"][0]
        vectors.append(value)
    combined = mx.stack(vectors)
    return combined * mx.rsqrt(
        mx.mean(combined * combined, axis=-1, keepdims=True)
        + spec.rms_norm_epsilon
    ) * owned["features.norm"]


def _learning_first_source_vectors(
        parameters, compiled, config, source, features, extents, banks, snapshot):
    indices = source.learning_abi_indices
    if (type(indices) is not tuple or len(indices) != compiled.visible_end
            or snapshot is None):
        invalid("BAMF_SOURCE_ATOM_INPUT_INVALID")
    spec, owned = _source_embedding_parameters(
        parameters, source, features, extents, banks, snapshot)
    active_indices = tuple(
        bank.bank_index * spec.semantic_bank_rows + row
        for bank in banks for row in bank.active_rows)
    vectors = []
    for abi_index in indices:
        entry = snapshot.abi(abi_index)
        feature = generation_feature_row(
            snapshot, features, entry.semantic_id, abi_index, config.task.scope,
            active_indices=active_indices)
        bank_index, bank_row = divmod(abi_index, spec.semantic_bank_rows)
        value = banks[bank_index].weights[bank_row]
        for term in _released_factor_terms(owned, feature):
            value = value + term
        value = value + owned["features.local_slot"][0]
        vectors.append(value)
    combined = mx.stack(tuple(vectors))
    vectors = combined * mx.rsqrt(
        mx.mean(combined * combined, axis=-1, keepdims=True)
        + spec.rms_norm_epsilon
    ) * owned["features.norm"]
    return vectors, _LearningSourceHandoff.from_row(
        compiled.source_instance_id, indices)


def source_atom_vectors(
    parameters, compiled, config, source, features, feature_schema, extents,
    banks, artifact_owner, *, snapshot=None, source_execution_authority=None,
):
    """Recheck source/rights before gathering any identity tensor.

    Native formal signatures remain source metadata. A06 alone owns categorical
    feature types. Unframed atoms use its existing NONE role/schema and local
    slot zero, without casting the atom to a caller-created ConceptRef.
    """
    if source.learning_abi_indices is not None:
        vectors, handoff = _learning_first_source_vectors(
            parameters, compiled, config, source, features, extents, banks, snapshot)
        return vectors, banks, handoff
    snapshot, handoff = _resolve_source_embedding_authority(
        compiled, config, source, features, feature_schema, artifact_owner,
        snapshot, source_execution_authority)
    _validate_source_embedding_generation(
        source, features, extents, banks, snapshot)
    snapshot, handoff = _bind_source_embedding_handoff(
        compiled, config, source, features, artifact_owner, snapshot, handoff)
    spec, owned = _source_embedding_parameters(
        parameters, source, features, extents, banks, snapshot)
    vectors = _source_binding_vectors(
        handoff, config, features, banks, spec, owned, snapshot)
    return vectors, banks, handoff

