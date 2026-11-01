"""Versioned Atlas feature and prospective identity records."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import json

from ..frame_schema import ConceptRef


from .common import FEATURE_SCHEMA, FEATURE_MANIFEST_SCHEMA, FEATURE_CONCEPT_SCHEMA, FEATURE_ROW_SCHEMA, PROSPECTIVE_IDENTITY_SCHEMA, PROSPECTIVE_FEATURE_SET_SCHEMA, _invalid, _sorted_ids, _factor_overflow

@dataclass(frozen=True)
class FeatureSchema:
    role_ids: tuple[str, ...]
    schema_ids: tuple[str, ...]
    predecessor: "AtlasFeatures | None" = None
    source_bindings: tuple[tuple[str, str], ...] = ()
    schema_version: str = FEATURE_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.role_ids, tuple)
                or not isinstance(self.schema_ids, tuple)
                or not isinstance(self.source_bindings, tuple)
                or any(not isinstance(item, tuple) or len(item) != 2
                       or not all(isinstance(value, str) and value
                                  for value in item)
                       for item in self.source_bindings)
                or tuple(item[0] for item in self.source_bindings)
                != _sorted_ids(self.schema_ids)
                or self.schema_version != FEATURE_SCHEMA
                or (self.predecessor is not None
                    and not isinstance(self.predecessor, AtlasFeatures))):
            _invalid("BAMF_FEATURE_SCHEMA_INVALID")
        _sorted_ids(self.role_ids)
        _sorted_ids(self.schema_ids)


@dataclass(frozen=True)
class ConceptFeature:
    semantic_id: str
    abi_index: int
    type_ids: tuple[str, ...]
    graph64: tuple[float, ...]
    source_status: str
    schema_version: str = FEATURE_CONCEPT_SCHEMA


@dataclass(frozen=True)
class ProspectiveIdentityFeature:
    """Source-qualified features for one inactive ABI identity."""

    semantic_id: str
    abi_index: int
    type_ids: tuple[str, ...]
    type_rows: tuple[int, ...]
    type_overflow: tuple[tuple[float, ...] | None, ...]
    graph64: tuple[float, ...]
    source_status: str
    schema_version: str = PROSPECTIVE_IDENTITY_SCHEMA


@dataclass(frozen=True)
class ProspectiveIdentityFeatureSet:
    """A pure source-side staging plan; it grants no admission or neural write."""

    semantic_release: str
    atlas_bundle_id: str
    source_bundle_id: str
    predecessor_feature_digest: str
    type_map: tuple[tuple[str, int], ...]
    identities: tuple[ProspectiveIdentityFeature, ...]
    schema_version: str = PROSPECTIVE_FEATURE_SET_SCHEMA

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(
            asdict(self), sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FeatureRow:
    semantic_id: str
    abi_index: int
    scope: str
    type_ids: tuple[str, ...]
    type_rows: tuple[int, ...]
    type_overflow: tuple[tuple[str, tuple[float, ...]], ...]
    role_id: str
    role_row: int
    role_overflow: tuple[float, ...] | None
    schema_id: str
    schema_row: int
    schema_overflow: tuple[float, ...] | None
    graph64: tuple[float, ...]
    source_status: str
    schema_version: str = FEATURE_ROW_SCHEMA


@dataclass(frozen=True)
class AtlasFeatures:
    semantic_release: str
    atlas_bundle_id: str
    source_bundle_id: str
    predecessor_digest: str | None
    type_map: tuple[tuple[str, int], ...]
    role_map: tuple[tuple[str, int], ...]
    schema_map: tuple[tuple[str, int], ...]
    concepts: tuple[ConceptFeature, ...]
    held_reasons: tuple[tuple[str, str], ...]
    schema_version: str = FEATURE_MANIFEST_SCHEMA

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(
            asdict(self), sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()

    def features_for(
        self, concept: str | ConceptRef, role: str, schema: str, scope: str,
    ) -> FeatureRow:
        if isinstance(concept, ConceptRef):
            if concept.semantic_release != self.semantic_release:
                _invalid("BAMF_FEATURE_FOREIGN_RELEASE")
            semantic_id = concept.semantic_id
        elif isinstance(concept, str):
            semantic_id = concept
        else:
            _invalid("BAMF_FEATURE_CONCEPT_INVALID")
        item = next(
            (entry for entry in self.concepts if entry.semantic_id == semantic_id),
            None)
        if item is None:
            _invalid("BAMF_FEATURE_CONCEPT_NOT_ADMITTED")
        if isinstance(concept, ConceptRef) and (
                concept.abi_index != item.abi_index
                or _sorted_ids(concept.type_ids) != item.type_ids):
            _invalid("BAMF_FEATURE_CONCEPT_SOURCE_MISMATCH")
        if not isinstance(scope, str) or not scope:
            _invalid("BAMF_FEATURE_SCOPE_INVALID")
        roles, schemas, types = (
            dict(self.role_map), dict(self.schema_map), dict(self.type_map))
        if role not in roles or schema not in schemas:
            _invalid("BAMF_FEATURE_ROLE_SCHEMA_NOT_ADMITTED")
        return FeatureRow(
            semantic_id=item.semantic_id, abi_index=item.abi_index,
            scope=scope, type_ids=item.type_ids,
            type_rows=tuple(types[identifier] for identifier in item.type_ids),
            type_overflow=tuple(
                (identifier, _factor_overflow("type", identifier))
                for identifier in item.type_ids if types[identifier] == 0),
            role_id=role, role_row=roles[role],
            role_overflow=_factor_overflow("role", role)
            if roles[role] == 0 and role != "UNKNOWN" else None,
            schema_id=schema, schema_row=schemas[schema],
            schema_overflow=_factor_overflow("schema", schema)
            if schemas[schema] == 0 and schema != "UNKNOWN" else None,
            graph64=item.graph64, source_status=item.source_status,
        )
