"""AtlasFeatures/v2: immutable source-grounded factor and graph projection.

Compile once per admitted release. No neural tensors, source-gold, live graph
queries or optimizer writes occur in this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re

from ..errors import ErrorBus, SEMANTIC_FRAME
from rdflib.namespace import SKOS
from .atlas_projection import FrozenAtlasSnapshot
from .domains import contract_digest
from .frame_schema import ConceptRef
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.relations import SEMANTIC_PREDICATES


FEATURE_SCHEMA = "bilqis.atlas-feature-schema/v2"
# The source owner must attest each selected rule family.
FEATURE_MANIFEST_SCHEMA = "bilqis.atlas-features/v2"
FEATURE_CONCEPT_SCHEMA = "bilqis.atlas-concept-feature/v2"
FEATURE_ROW_SCHEMA = "bilqis.atlas-feature-row/v2"
FACTOR_ROWS = 512
FIRST_FACTOR_ROW = 2
FACTOR_DIM = 128
GRAPH_DIM = 64
GRAPH_HASH_START = 8
GRAPH_HASH_WIDTH = 56
GRAPH_SIGN_BYTE_INDEX = 8
EDGE_TARGET_INDEX = 2
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_BROADER = SEMANTIC_PREDICATES["subsumption"]
_NARROWER = SEMANTIC_PREDICATES["inverse_subsumption"]
_ROOT_SENSE = Identity("term", ("hasSense",)).iri
_ADMITTED_GRAPH_PREDICATES = frozenset({
    *SEMANTIC_PREDICATES.values(), str(SKOS.member), str(SKOS.memberList),
    _ROOT_SENSE,
})


def _invalid(reason: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<atlas-feature>", span_start=0, span_end=0,
    )


def _utf8(value: str) -> bytes:
    return value.encode("utf-8")


def _sorted_ids(values) -> tuple[str, ...]:
    if any(not isinstance(item, str) or not item for item in values):
        _invalid("BAMF_FEATURE_CATEGORY_INVALID")
    return tuple(sorted(set(values), key=_utf8))


def _factor_overflow(kind: str, identifier: str) -> tuple[float, ...]:
    """f128 exact SHA-256 byte expansion, never a replacement identity."""
    material = b"".join(
        hashlib.sha256(
            ("bamf.factor.v2|" + kind + "|" + identifier + "|" + str(block))
            .encode("utf-8")
        ).digest()
        for block in range(4)
    )
    return tuple((byte / 127.5 - 1.0) / math.sqrt(FACTOR_DIM)
                 for byte in material)


def _category_map(
    values: tuple[str, ...],
    prior: tuple[tuple[str, int], ...] | None,
) -> tuple[tuple[str, int], ...]:
    mapping = dict(prior or (("UNKNOWN", 0), ("NONE", 1)))
    if mapping.get("UNKNOWN") != 0 or mapping.get("NONE") != 1:
        _invalid("BAMF_FEATURE_RESERVED_CATEGORY_DRIFT")
    used = {row for row in mapping.values() if row >= FIRST_FACTOR_ROW}
    if (len(used) != sum(row >= FIRST_FACTOR_ROW for row in mapping.values())
            or any(type(row) is not int or not 0 <= row < FACTOR_ROWS
                   for row in mapping.values())):
        _invalid("BAMF_FEATURE_PRIOR_MAP_INVALID")
    next_row = max(used, default=FIRST_FACTOR_ROW - 1) + 1
    for identifier in _sorted_ids(values):
        if identifier in ("UNKNOWN", "NONE"):
            _invalid("BAMF_FEATURE_RESERVED_ID_COLLISION")
        if identifier in mapping:
            continue
        mapping[identifier] = next_row if next_row < FACTOR_ROWS else 0
        if next_row < FACTOR_ROWS:
            next_row += 1
    return tuple(sorted(mapping.items(), key=lambda item: _utf8(item[0])))


def _normalized_count(count: int) -> float:
    if type(count) is not int or count < 0:
        _invalid("BAMF_FEATURE_SOURCE_COUNT_INVALID")
    return min(math.log1p(count) / math.log(1025), 1.0)


def _source_rule_categories(
    release: FrozenAtlasSnapshot,
    source_bindings: tuple[tuple[str, str], ...],
) -> tuple[str, ...]:
    """Prove schema IDs and roles against A03's pinned released source graph."""
    if not source_bindings:
        return ()
    from ..grade_a_probe import read_sources
    from ..live_grade_c import registry_graph
    from .frame_adapters import (
        BOOLEAN_COMPOSITE_ADAPTER, BOOLEAN_CONNECTIVE_ADAPTER,
        BOOLEAN_IDENTIFICATION_ADAPTER, FINITE_NUMERIC_ADAPTER,
        MICRO_PREDICATE_ADAPTER, _schema_for_symbol,
    )
    from .frame_schema import SourceSpan

    source_root = Path(__file__).resolve().parents[2] / "vendor/legacy-v16"
    micro_graph = read_sources(source_root)[2]
    numeric_graph = registry_graph()
    graphs = {
        MICRO_PREDICATE_ADAPTER: micro_graph,
        BOOLEAN_CONNECTIVE_ADAPTER: micro_graph,
        BOOLEAN_COMPOSITE_ADAPTER: micro_graph,
        BOOLEAN_IDENTIFICATION_ADAPTER: micro_graph,
        FINITE_NUMERIC_ADAPTER: numeric_graph,
    }
    entries = {
        "frame:" + entry.semantic_id: entry
        for entry in release.abi_entries if entry.active
    }
    roles: set[str] = set()
    for schema_id, adapter_id in source_bindings:
        entry = entries.get(schema_id)
        graph = graphs.get(adapter_id)
        if (entry is None or entry.symbol is None or graph is None
                or not 0 <= entry.index < len(graph["tokens"])
                or graph["tokens"][entry.index] != entry.symbol):
            _invalid("BAMF_FEATURE_SOURCE_SCHEMA_UNVERIFIED")
        source_schema, _ = _schema_for_symbol(
            release, graph, entry.symbol, "source:" + entry.symbol,
            adapter_id=adapter_id,
            span=SourceSpan(0, 1), scope="source-rule")
        if source_schema.schema_id != schema_id:
            _invalid("BAMF_FEATURE_SOURCE_SCHEMA_UNVERIFIED")
        roles.update(role.role_id for role in source_schema.roles)
    return _sorted_ids(tuple(roles))


def _graph_vector(
    identifier: str,
    type_ids: tuple[str, ...],
    source_forms: int,
    source_senses: int,
    unresolved: bool,
    relations: tuple[tuple[str, str, str], ...],
    types_by_id: dict[str, tuple[str, ...]],
) -> tuple[float, ...]:
    incoming = [edge for edge in relations
                if edge[EDGE_TARGET_INDEX] == identifier]
    outgoing = [edge for edge in relations if edge[0] == identifier]
    values = [0.0] * GRAPH_DIM
    counts = (
        len(incoming), len(outgoing),
        sum(edge[1] == _BROADER for edge in outgoing),
        sum(edge[1] == _NARROWER for edge in outgoing),
        len(type_ids), source_forms, source_senses,
    )
    for index, count in enumerate(counts):
        values[index] = _normalized_count(count)
    values[7] = 1.0 if unresolved else 0.0
    signatures = []
    for source, predicate, target in outgoing:
        for neighbor_type in types_by_id[target] or ("UNKNOWN",):
            signatures.append("out|" + predicate + "|" + neighbor_type)
    for source, predicate, target in incoming:
        for neighbor_type in types_by_id[source] or ("UNKNOWN",):
            signatures.append("in|" + predicate + "|" + neighbor_type)
    signatures.sort(key=_utf8)
    for signature in signatures:
        digest = hashlib.sha256(
            ("bamf.graph.v2|" + signature).encode("utf-8")).digest()
        channel = GRAPH_HASH_START + (
            int.from_bytes(digest[:8], "little") % GRAPH_HASH_WIDTH)
        sign = 1.0 if digest[GRAPH_SIGN_BYTE_INDEX] & 1 == 0 else -1.0
        values[channel] += sign / len(signatures)
    return tuple(values)


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


def build_feature_manifest(
    release: FrozenAtlasSnapshot,
    feature_schema: FeatureSchema,
) -> AtlasFeatures:
    """Compile all admitted identities, preserving predecessor factor rows."""
    if (not isinstance(release, FrozenAtlasSnapshot)
            or not isinstance(feature_schema, FeatureSchema)
            or not _SHA.fullmatch(release.release_sha256)):
        _invalid("BAMF_FEATURE_RELEASE_INVALID")
    prior = feature_schema.predecessor
    if prior is not None and (
            prior.semantic_release == release.release_sha256
            or release.prior_abi_sha256 != prior.atlas_bundle_id):
        _invalid("BAMF_FEATURE_PREDECESSOR_LINEAGE_INVALID")
    if (_sorted_ids(feature_schema.role_ids)
            != _source_rule_categories(release, feature_schema.source_bindings)):
        _invalid("BAMF_FEATURE_SOURCE_ROLE_UNVERIFIED")
    active = {
        entry.semantic_id: entry for entry in release.abi_entries if entry.active
    }
    if len(active) != sum(entry.active for entry in release.abi_entries):
        _invalid("BAMF_FEATURE_DUPLICATE_ADMITTED_ID")
    source_concepts = {
        item.concept.semantic_id: item.concept for item in release.concepts
        if item.active and item.concept.semantic_id in active
    }
    types_by_id = {
        identifier: _sorted_ids(source_concepts[identifier].types)
        if identifier in source_concepts else ()
        for identifier in active
    }
    admitted_relations = tuple(sorted((
        (edge.source_semantic_id, edge.predicate, edge.target_semantic_id)
        for edge in release.relations
        if (edge.source_semantic_id in active
            and edge.target_semantic_id in active
            and edge.predicate in _ADMITTED_GRAPH_PREDICATES)
    ), key=lambda edge: tuple(_utf8(part) for part in edge)))
    source_sense_targets = {
        identifier for identifier, concept in source_concepts.items()
        if concept.kind == "sense" and any(
            ref.table == "lexicon_root_senses"
            for ref in concept.source_rows)
    }
    senses_by_root: dict[str, set[str]] = {}
    for source_id, predicate, target_id in admitted_relations:
        if (predicate in (_ROOT_SENSE, _NARROWER)
                and target_id in source_sense_targets
                and source_id in source_concepts
                and source_concepts[source_id].kind == "root"):
            senses_by_root.setdefault(source_id, set()).add(target_id)
        if (predicate == _BROADER and source_id in source_sense_targets
                and target_id in source_concepts
                and source_concepts[target_id].kind == "root"):
            senses_by_root.setdefault(target_id, set()).add(source_id)
    type_map = _category_map(
        tuple(type_id for types in types_by_id.values() for type_id in types),
        prior.type_map if prior else None)
    role_map = _category_map(
        feature_schema.role_ids, prior.role_map if prior else None)
    schema_map = _category_map(
        feature_schema.schema_ids, prior.schema_map if prior else None)
    unresolved = {
        item.semantic_id for item in release.withheld_rows
        if item.semantic_id is not None
    }
    concept_rows = []
    for identifier in _sorted_ids(tuple(active)):
        source = source_concepts.get(identifier)
        forms = len(source.realizations) if source else 0
        senses = len(senses_by_root.get(identifier, ()))
        concept_rows.append(ConceptFeature(
            identifier, active[identifier].index, types_by_id[identifier],
            _graph_vector(
                identifier, types_by_id[identifier], forms, senses,
                identifier in unresolved or source is None,
                admitted_relations, types_by_id),
            "ADMITTED_SOURCE" if source else "ADMITTED_FORMAL_ABI_UNTYPED",
        ))
    held_reasons = tuple(sorted((
        (item.semantic_id or item.key, item.reason_code)
        for item in release.withheld_rows
    ), key=lambda item: (_utf8(item[0]), _utf8(item[1]))))
    return AtlasFeatures(
        release.release_sha256, release.bundle_id, release.source_bundle_id,
        prior.digest if prior else None,
        type_map, role_map, schema_map, tuple(concept_rows),
        held_reasons,
    )
