"""Immutable receipt record for B13 accepted-generation feature authority."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields

from ..records import canonical, invalid, sha

RECEIPT_SCHEMA = "bilqis.mlx.bamf-accepted-generation-feature-receipt/v1"


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
