"""Owner-derived zero-ID C07 v2 resource facts from accepted B13 custody."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.runtime.atlas_admission_policy_v2 import AtlasDerivedAdmissionFactsV2
from bilqis_mlx.runtime.atlas_lease_contracts import _invalid


def read_capability_only_admission_facts_v2(
        run_dir: Path, handoff) -> AtlasDerivedAdmissionFactsV2:
    """Derive zero-ID resource facts from accepted B13/source authority only."""
    from bilqis_mlx.runtime.bamf_bundle import (
        load_bamf_generation_authority,
        read_accepted_generation_feature_context,
    )
    from bilqis_mlx.runtime.bamf_bundle.feature.replay_support import (
        artifact_identity,
        feature_source,
    )
    from bilqis_mlx.runtime.bamf_bundle.vocabulary.admission_facts import (
        accepted_active_semantic_ids,
    )
    from bilqis_mlx.runtime.model_topology_v2 import bamf_parameter_census
    from bilqis_mlx.semantics.atlas.snapshot import (
        load_pinned_atlas_snapshot,
        resolve_atlas_artifact_selection,
    )
    from bilqis_mlx.semantics.atlas.vocabulary_resources import (
        FP32_WEIGHT_AND_ADAMW_BYTES,
    )

    pointer = Path(run_dir) / "bamf-state.json"
    parent, parent_manifest = load_bamf_generation_authority(pointer)
    feature_context = read_accepted_generation_feature_context(pointer)
    source = feature_source(parent.compiler_features)
    selection = resolve_atlas_artifact_selection(artifact_identity(source))
    snapshot = load_pinned_atlas_snapshot(selection)
    active_ids = accepted_active_semantic_ids(parent, snapshot)
    predecessor = handoff.receipt.predecessor_release
    successor = handoff.receipt.staged_successor
    if (feature_context.receipt.generation_manifest_sha256 != parent_manifest
            or feature_context.receipt.active_set_sha256
               != parent.extents.active_semantic_digest
            or feature_context.features.semantic_release != selection.release_sha256
            or feature_context.features.semantic_release
               != handoff.receipt.selection_snapshot.semantic_release
            or tuple(predecessor.semantic_catalog) != tuple(successor.semantic_catalog)
            or parent.extents.active_semantic_digest != snapshot.active_set_sha256):
        _invalid("BAMF_ATLAS_V2_CAPABILITY_ONLY_FACTS_DRIFT")
    checkpoint_bytes = (
        bamf_parameter_census(parent.topology, parent.extents).total
        * FP32_WEIGHT_AND_ADAMW_BYTES)
    return AtlasDerivedAdmissionFactsV2(
        semantic_banks=parent.extents.semantic_bank_count,
        motif_pages=parent.extents.motif_page_count,
        total_atlas_semantic_identities=len(active_ids),
        checkpoint_bytes_lower_bound=checkpoint_bytes,
        required_available_bytes_lower_bound=checkpoint_bytes,
        new_semantic_identities=0,
    )
