"""Source-bound prospective identity factors for A02 staging."""
from __future__ import annotations

from typing import Mapping

from ...runtime.model_topology_v2 import GenerationExtents, project_identity_source_factor
from ..atlas_features import (
    AtlasFeatures, ProspectiveIdentityFeatureSet,
    plan_prospective_identity_features,
)
from ..atlas_projection import FrozenAtlasSnapshot

def prepare_identity_factors(
    release: FrozenAtlasSnapshot,
    current_features: AtlasFeatures,
    semantic_ids: tuple[str, ...],
    feature_parameters: Mapping[str, object],
    *,
    extents: GenerationExtents,
) -> tuple[ProspectiveIdentityFeatureSet, tuple[tuple[str, object], ...]]:
    """Stage source-bound 768-wide factors without activating or training rows."""
    plan = plan_prospective_identity_features(
        release, current_features, semantic_ids,
        expected_feature_digest=extents.factor_map_digest)
    factors = tuple(
        (item.semantic_id, project_identity_source_factor(
            feature_parameters,
            type_rows=item.type_rows,
            type_overflow=item.type_overflow,
            graph64=item.graph64,
            extents=extents,
            predecessor_feature_digest=plan.predecessor_feature_digest))
        for item in plan.identities
    )
    return plan, factors
