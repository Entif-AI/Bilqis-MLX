"""Append-only projection selection receipts."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json

from bilqis_mlx.runtime.akasha_domains import AkashaDomain
from .common import _canonical, _digest, _invalid, _sha


SELECTION_RECEIPT_SCHEMA = "bilqis.akasha.projection-selection/v1"


class ProjectionSelectionKind(str, Enum):
    INITIAL = "INITIAL"
    MIGRATION = "MIGRATION"
    REBUILD = "REBUILD"
    ROLLBACK = "ROLLBACK"


@dataclass(frozen=True)
class ProjectionSelectionReceipt:
    kind: ProjectionSelectionKind
    domain: AkashaDomain
    previous_version_sha256: str | None
    selected_version_sha256: str
    evidence_sha256: str
    selection_sha256: str
    schema_version: str = field(default=SELECTION_RECEIPT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if (not isinstance(self.kind, ProjectionSelectionKind)
                or not isinstance(self.domain, AkashaDomain)
                or (self.previous_version_sha256 is not None
                    and not _sha(self.previous_version_sha256))
                or not _sha(self.selected_version_sha256)
                or not _sha(self.evidence_sha256)
                or self.schema_version != SELECTION_RECEIPT_SCHEMA
                or self.selection_sha256 != _digest(self._identity_payload())):
            _invalid("AKASHA_PROJECTION_SELECTION_RECEIPT_INVALID")

    def _identity_payload(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind.value,
            "domain": self.domain.value,
            "previous_version_sha256": self.previous_version_sha256,
            "selected_version_sha256": self.selected_version_sha256,
            "evidence_sha256": self.evidence_sha256,
        }

    @property
    def canonical_json(self) -> str:
        return _canonical({
            **self._identity_payload(), "selection_sha256": self.selection_sha256})

    @classmethod
    def create(cls, kind: ProjectionSelectionKind, domain: AkashaDomain,
               previous_version_sha256: str | None, selected_version_sha256: str,
               evidence_sha256: str) -> "ProjectionSelectionReceipt":
        identity = {
            "schema_version": SELECTION_RECEIPT_SCHEMA,
            "kind": kind.value,
            "domain": domain.value,
            "previous_version_sha256": previous_version_sha256,
            "selected_version_sha256": selected_version_sha256,
            "evidence_sha256": evidence_sha256,
        }
        return cls(
            kind, domain, previous_version_sha256, selected_version_sha256,
            evidence_sha256, _digest(identity))

    @classmethod
    def from_canonical_json(cls, value: str) -> "ProjectionSelectionReceipt":
        try:
            raw = json.loads(value)
            schema_version = raw.pop("schema_version")
            item = cls(**{
                **raw,
                "kind": ProjectionSelectionKind(raw["kind"]),
                "domain": AkashaDomain(raw["domain"]),
            })
            if schema_version != item.schema_version:
                _invalid("AKASHA_PROJECTION_SELECTION_STORED_INVALID")
            return item
        except (TypeError, ValueError, KeyError):
            _invalid("AKASHA_PROJECTION_SELECTION_STORED_INVALID")
