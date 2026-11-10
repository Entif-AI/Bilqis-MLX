"""Typed B13 feature-context records."""
from __future__ import annotations

from dataclasses import dataclass

from bilqis_mlx.semantics.atlas_features import FeatureSchema
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_projection import FrozenAtlasSnapshot

from ..records import invalid
from .receipt import AcceptedGenerationFeatureReceipt


@dataclass(frozen=True)
class AuthenticatedCandidateFeatureContext:
    """Source-replayed feature inputs for pre-acceptance evaluation only."""

    selection: AtlasArtifactSelection
    snapshot: FrozenAtlasSnapshot
    schema: FeatureSchema
    features: object

    def __post_init__(self) -> None:
        if (type(self.selection) is not AtlasArtifactSelection
                or type(self.snapshot) is not FrozenAtlasSnapshot
                or type(self.schema) is not FeatureSchema
                or self.features.semantic_release != self.selection.release_sha256
                or self.features.atlas_bundle_id != self.selection.bundle_id
                or self.features.source_bundle_id != self.selection.source_bundle_id
                or self.snapshot.release_sha256 != self.selection.release_sha256
                or self.snapshot.bundle_id != self.selection.bundle_id
                or self.snapshot.source_bundle_id != self.selection.source_bundle_id):
            invalid("BAMF_FEATURE_CONTEXT_INVALID")


@dataclass(frozen=True)
class AuthenticatedGenerationFeatureContext:
    """Source-replayed feature inputs backed by accepted-generation custody."""

    selection: AtlasArtifactSelection
    snapshot: FrozenAtlasSnapshot
    schema: FeatureSchema
    features: object
    receipt: AcceptedGenerationFeatureReceipt

    def __post_init__(self) -> None:
        AuthenticatedCandidateFeatureContext(
            self.selection, self.snapshot, self.schema, self.features)
        if (type(self.receipt) is not AcceptedGenerationFeatureReceipt
                or self.receipt.semantic_release != self.features.semantic_release
                or self.receipt.feature_sha256 != self.features.digest):
            invalid("BAMF_ACCEPTED_FEATURE_CONTEXT_INVALID")


@dataclass(frozen=True)
class AcceptedGenerationFeatureContext:
    """Typed B13 replay context for one accepted generation."""

    receipt: AcceptedGenerationFeatureReceipt
    features: object
    predecessor_features: object | None
    construction_predecessor: object | None
