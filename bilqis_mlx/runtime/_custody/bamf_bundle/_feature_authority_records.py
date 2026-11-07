"""Typed records and sidecar decoders for B13 feature authority."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas_features import FeatureSchema
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_projection import FrozenAtlasSnapshot

from .records import canonical, invalid, sha

RECEIPT_SCHEMA = "bilqis.mlx.bamf-accepted-generation-feature-receipt/v1"
FEATURE_SOURCE_KEYS = frozenset({
    "atlas_bundle_id", "release_sha256", "source_bundle_id"})
FEATURE_SCHEMA_KEYS = frozenset({"role_ids", "schema_ids", "source_bindings"})
SOURCE_BINDING_WIDTH = 2


@dataclass(frozen=True)
class AcceptedGenerationFeatureReceipt:
    """One immutable binding between an accepted generation and its feature map."""

    run_id: str
    generation: int
    generation_manifest_sha256: str
    parent_generation_manifest_sha256: str | None
    semantic_release: str
    active_set_sha256: str
    feature_sha256: str
    predecessor_feature_sha256: str | None
    compiler_sha256: str
    implementation_sha256: str
    acceptance_sha256: str
    source_atlas_bundle_id: str
    source_release_sha256: str
    source_source_bundle_id: str
    schema_version: str = RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        digests = (
            self.generation_manifest_sha256, self.semantic_release,
            self.active_set_sha256, self.feature_sha256, self.compiler_sha256,
            self.implementation_sha256, self.acceptance_sha256,
            self.source_atlas_bundle_id, self.source_release_sha256,
            self.source_source_bundle_id,
        )
        if (self.schema_version != RECEIPT_SCHEMA
                or not isinstance(self.run_id, str) or not self.run_id
                or type(self.generation) is not int or self.generation < 0
                or any(not _hex(value) for value in digests)
                or (self.parent_generation_manifest_sha256 is not None
                    and not _hex(self.parent_generation_manifest_sha256))
                or (self.predecessor_feature_sha256 is not None
                    and not _hex(self.predecessor_feature_sha256))):
            invalid("BAMF_FEATURE_RECEIPT_INVALID")

    @property
    def digest(self) -> str:
        return sha(canonical(asdict(self)))

    def to_record(self) -> dict:
        return {**asdict(self), "receipt_sha256": self.digest}

    @classmethod
    def from_record(cls, record) -> "AcceptedGenerationFeatureReceipt":
        names = {field.name for field in fields(cls)}
        if (not isinstance(record, dict)
                or set(record) != names | {"receipt_sha256"}):
            invalid("BAMF_FEATURE_RECEIPT_INVALID")
        receipt = cls(**{name: record[name] for name in names})
        if record["receipt_sha256"] != receipt.digest:
            invalid("BAMF_FEATURE_RECEIPT_INVALID")
        return receipt


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


def _hex(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _feature_source(compiler_features: dict) -> dict:
    source = compiler_features.get("feature_source")
    if (not isinstance(source, dict) or set(source) != set(FEATURE_SOURCE_KEYS)
            or any(not _hex(source[name]) for name in FEATURE_SOURCE_KEYS)):
        invalid("BAMF_FEATURE_SOURCE_BINDING_MISSING")
    return dict(source)


def _feature_schema(compiler_features: dict) -> FeatureSchema:
    recorded = compiler_features.get("feature_schema")
    if (not isinstance(recorded, dict)
            or set(recorded) != set(FEATURE_SCHEMA_KEYS)):
        invalid("BAMF_FEATURE_SCHEMA_BINDING_MISSING")
    bindings = recorded["source_bindings"]
    if (not isinstance(recorded["role_ids"], list)
            or not isinstance(recorded["schema_ids"], list)
            or not isinstance(bindings, list)
            or any(not isinstance(row, list) or len(row) != SOURCE_BINDING_WIDTH
                   or not all(isinstance(value, str) and value for value in row)
                   for row in bindings)):
        invalid("BAMF_FEATURE_SCHEMA_BINDING_INVALID")
    try:
        return FeatureSchema(
            role_ids=tuple(recorded["role_ids"]),
            schema_ids=tuple(recorded["schema_ids"]),
            source_bindings=tuple((row[0], row[1]) for row in bindings))
    except BilqisError:
        invalid("BAMF_FEATURE_SCHEMA_BINDING_INVALID")
