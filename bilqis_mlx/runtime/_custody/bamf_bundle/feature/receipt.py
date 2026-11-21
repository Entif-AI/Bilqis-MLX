"""Immutable receipt record for B13 accepted-generation feature authority."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields

from ..records import canonical, invalid, sha

RECEIPT_SCHEMA = "bilqis.mlx.bamf-accepted-generation-feature-receipt/v1"
ARTIFACT_COMMITMENT_SCHEMA = (
    "bilqis.mlx.bamf-accepted-feature-artifact-commitment/v1")


def is_digest(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


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
                or any(not is_digest(value) for value in digests)
                or (self.parent_generation_manifest_sha256 is not None
                    and not is_digest(self.parent_generation_manifest_sha256))
                or (self.predecessor_feature_sha256 is not None
                    and not is_digest(self.predecessor_feature_sha256))):
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
class AcceptedFeatureArtifactCommitment:
    """Feature slice of an owner-authenticated accepted-authority checkpoint.

    The record is data, not checkpoint authority by itself. The checkpoint owner
    authenticates this commitment before B13 consumes it to verify current feature
    bytes without replaying feature ancestry.
    """

    receipt: AcceptedGenerationFeatureReceipt
    artifact_bundle_id: str
    artifact_predecessor_digest: str | None
    schema_version: str = ARTIFACT_COMMITMENT_SCHEMA

    def __post_init__(self) -> None:
        if (self.schema_version != ARTIFACT_COMMITMENT_SCHEMA
                or type(self.receipt) is not AcceptedGenerationFeatureReceipt
                or not is_digest(self.artifact_bundle_id)
                or (self.artifact_predecessor_digest is not None
                    and not is_digest(self.artifact_predecessor_digest))):
            invalid("BAMF_FEATURE_CHECKPOINT_COMMITMENT_INVALID")

    def to_record(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "receipt": self.receipt.to_record(),
            "artifact_bundle_id": self.artifact_bundle_id,
            "artifact_predecessor_digest": self.artifact_predecessor_digest,
        }

    @classmethod
    def from_record(cls, record) -> "AcceptedFeatureArtifactCommitment":
        names = {
            "schema_version", "receipt", "artifact_bundle_id",
            "artifact_predecessor_digest",
        }
        if not isinstance(record, dict) or set(record) != names:
            invalid("BAMF_FEATURE_CHECKPOINT_COMMITMENT_INVALID")
        return cls(
            AcceptedGenerationFeatureReceipt.from_record(record["receipt"]),
            record["artifact_bundle_id"],
            record["artifact_predecessor_digest"],
            record["schema_version"],
        )
