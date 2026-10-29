"""Source-qualified A08 family inventory, before lesson/checker construction.

This module is deliberately neural-inert. The frozen A01 Atlas determines the
source census; installed constructors cannot alter its eligible denominator.
A08.1b owns binding constructive lessons and independent checkers to these rows.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from urllib.parse import urlsplit

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.atlas_projection import (
    ATLAS_SNAPSHOT_SCHEMA, FrozenAtlasConcept, FrozenAtlasRelation,
    FrozenAtlasSnapshot,
)
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.relations import SEMANTIC_PREDICATES


FAMILY_INVENTORY_SCHEMA = "bilqis.semantic-family-inventory/v1"
FAMILY_OBLIGATION_SCHEMA = "bilqis.semantic-family-obligation/v1"
FAMILY_CONCEPT_SCHEMA = "bilqis.semantic-family-concept/v1"
FAMILY_RULE_SCHEMA = "bilqis.semantic-family-source-rule/v1"
_SEMANTIC_RELATIONS = tuple(sorted(set(SEMANTIC_PREDICATES.values())))
_SOURCE_TABLES = frozenset({
    "atomic/morphemes_atomic",
    "lexicon/lexicon_roots",
    "lexicon/lexicon_root_senses",
    "residue/morpheme_compositions",
    "residue/composition_components",
    "residue/affix_degrees",
    "residue/allomorph_rules",
})
_FORMAL_FAMILIES = frozenset({"boolean", "numeric"})
_SCOPE_MODALITY_TIME_CATEGORIES = (
    "ASPECT", "CASE_SCOPE", "FUNCTION_SPECIFICATION_CONTEXT",
    "ILLOCUTION", "MOOD", "PHASE", "PERSPECTIVE_ESSENCE",
)


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SourceFamilyAdapter:
    """A reusable *source matcher*, not a lesson or assessment checker."""

    family_id: str
    source_tables: tuple[str, ...] = ()
    formal_families: tuple[str, ...] = ()
    relation_predicates: tuple[str, ...] = ()
    grammar_categories: tuple[str, ...] = ()
    all_eligible: bool = False
    schema: str = FAMILY_RULE_SCHEMA

    def matches(
        self, *, tables: frozenset[str], formal: frozenset[str],
        relations: frozenset[str], grammar_category: str | None,
    ) -> bool:
        return (
            self.all_eligible
            or bool(tables.intersection(self.source_tables))
            or bool(formal.intersection(self.formal_families))
            or bool(relations.intersection(self.relation_predicates))
            or (grammar_category in self.grammar_categories
                and "atomic/morphemes_atomic" in tables)
        )


SOURCE_FAMILY_ADAPTERS = (
    SourceFamilyAdapter("positive_identity", all_eligible=True),
    SourceFamilyAdapter(
        "typed_role_binding",
        source_tables=("lexicon/lexicon_root_senses",),
        formal_families=("boolean", "numeric"),
        grammar_categories=("CASE", "CASE_SCOPE", "REFERENTIAL"),
    ),
    SourceFamilyAdapter(
        "source_attested_relation", relation_predicates=_SEMANTIC_RELATIONS),
    SourceFamilyAdapter(
        "morphology_composition",
        source_tables=("residue/composition_components",
                       "residue/morpheme_compositions")),
    SourceFamilyAdapter(
        "morphology_decomposition",
        source_tables=("residue/composition_components",
                       "residue/morpheme_compositions")),
    SourceFamilyAdapter(
        "boolean_composition", formal_families=("boolean",)),
    SourceFamilyAdapter(
        "numeric_composition", formal_families=("numeric",)),
    SourceFamilyAdapter(
        "scope_modality_time",
        grammar_categories=_SCOPE_MODALITY_TIME_CATEGORIES),
    SourceFamilyAdapter(
        "released_transformations",
        source_tables=("residue/allomorph_rules",)),
)


@dataclass(frozen=True)
class ConceptFamilyCoverage:
    semantic_id: str
    abi_index: int
    abi_active: bool
    source_disposition: str
    implementation_status: str
    required_family_ids: tuple[str, ...]
    source_refs: tuple[str, ...]
    schema: str = FAMILY_CONCEPT_SCHEMA


@dataclass(frozen=True)
class FamilyObligation:
    semantic_id: str
    family_id: str
    source_evidence_sha256: str
    implementation_status: str
    reason: str
    schema: str = FAMILY_OBLIGATION_SCHEMA


@dataclass(frozen=True)
class FamilyInventoryCounts:
    atlas_source_concepts: int
    formal_only_abi_identities: int
    source_eligible_concepts: int
    source_held_rows: int
    source_ir_only_rows: int
    source_emitted_nonconcept_rows: int
    required_families: int
    pending_source_families: int
    required_family_obligations: int
    implementation_uncovered_obligations: int


@dataclass(frozen=True)
class SemanticFamilyInventory:
    semantic_release: str
    atlas_bundle_id: str
    source_bundle_id: str
    source_coverage_sha256: str
    source_eligible_concept_ids: tuple[str, ...]
    required_source_family_ids: tuple[str, ...]
    pending_source_family_ids: tuple[str, ...]
    concepts: tuple[ConceptFamilyCoverage, ...]
    obligations: tuple[FamilyObligation, ...]
    source_held: tuple[tuple[str, str, str, str], ...]
    source_ir_only: tuple[tuple[str, str, str, str], ...]
    source_nonconcept: tuple[
        tuple[str, str, str, str | None, str, tuple[str, ...]], ...
    ]
    counts: FamilyInventoryCounts
    schema: str = FAMILY_INVENTORY_SCHEMA

    @property
    def digest(self) -> str:
        return _digest(asdict(self))


def _grammar_category(semantic_id: str) -> str | None:
    """Only the source-owned grammar IRI category, never English gloss text."""
    parts = urlsplit(semantic_id).path.split("/")
    for index, part in enumerate(parts):
        if part == "id" and parts[index + 1:index + 2] == ["grammar"]:
            if len(parts) == index + 4:
                category, value = parts[index + 2:index + 4]
                if Identity("grammar", (category, value)).iri == semantic_id:
                    return category
    return None


def _validate_snapshot(atlas: FrozenAtlasSnapshot) -> None:
    if not isinstance(atlas, FrozenAtlasSnapshot) or atlas.schema != ATLAS_SNAPSHOT_SCHEMA:
        _fail("BAMF_FAMILY_ATLAS_SNAPSHOT_REQUIRED")
    abi = atlas.abi_entries
    if (tuple(entry.index for entry in abi) != tuple(range(len(abi)))
            or len({entry.semantic_id for entry in abi}) != len(abi)
            or any(not entry.source for entry in abi)
            or len(abi) != atlas.counts.abi_entries
            or len(atlas.concepts) != atlas.counts.semantic_concepts
            or sum(entry.active for entry in abi) != atlas.counts.active_abi_indices):
        _fail("BAMF_FAMILY_ABI_CENSUS_INVALID")
    by_id = {entry.semantic_id: entry for entry in abi}
    concepts = atlas.concepts
    if (tuple(item.concept.semantic_id for item in concepts)
            != tuple(sorted(item.concept.semantic_id for item in concepts))
            or any(not item.concept.source_rows
                   or item.concept.semantic_id not in by_id
                   or item.abi_index != by_id[item.concept.semantic_id].index
                   for item in concepts)):
        _fail("BAMF_FAMILY_SOURCE_CONCEPT_INVALID")
    if atlas.relations != tuple(
            FrozenAtlasRelation(item.concept.semantic_id, edge.predicate, edge.target)
            for item in concepts for edge in item.concept.relations):
        _fail("BAMF_FAMILY_RELATION_SOURCE_INVALID")
    if any(semantic_id not in by_id
           for binding in atlas.formal_domain_bindings
           for semantic_id in binding.semantic_ids):
        _fail("BAMF_FAMILY_FORMAL_SOURCE_INVALID")
    held = tuple(row for row in atlas.withheld_rows
                 if row.source_disposition == "SOURCE_HELD")
    ir_only = tuple(row for row in atlas.withheld_rows
                    if row.source_disposition == "SOURCE_IR_ONLY")
    if any(row.source_disposition not in {
            "SOURCE_HELD", "SOURCE_IR_ONLY", "SOURCE_ELIGIBLE",
            "SOURCE_EMITTED_NON_CONCEPT"} for row in atlas.withheld_rows):
        _fail("BAMF_FAMILY_SOURCE_DISPOSITION_INVALID")
    if any(row.semantic_id not in by_id for row in atlas.withheld_rows
           if row.source_disposition == "SOURCE_ELIGIBLE"):
        _fail("BAMF_FAMILY_SOURCE_ELIGIBLE_ROW_INVALID")
    if (len(held) != atlas.counts.source_held
            or len(ir_only) != atlas.counts.source_ir_only
            or any(row.semantic_id in by_id for row in held)):
        _fail("BAMF_FAMILY_SOURCE_HOLD_CENSUS_INVALID")


def inventory_source_families(atlas: FrozenAtlasSnapshot) -> SemanticFamilyInventory:
    """Freeze every source-qualified concept/family before inspecting implementations.

    An unavailable constructor/checker is implementation debt, never a reason
    to drop a source-eligible concept or shrink the required family denominator.
    """
    _validate_snapshot(atlas)
    by_concept: dict[str, FrozenAtlasConcept] = {
        item.concept.semantic_id: item for item in atlas.concepts
    }
    formal_by_id: dict[str, set[str]] = {}
    for binding in atlas.formal_domain_bindings:
        for semantic_id in binding.semantic_ids:
            formal_by_id.setdefault(semantic_id, set()).add(binding.family)
    eligible = frozenset(entry.semantic_id for entry in atlas.abi_entries)
    relations_by_id: dict[str, set[str]] = {}
    for edge in atlas.relations:
        if (edge.source_semantic_id in eligible
                and edge.target_semantic_id in eligible
                and edge.predicate in _SEMANTIC_RELATIONS):
            relations_by_id.setdefault(edge.source_semantic_id, set()).add(
                edge.predicate)
    concepts = []
    obligations = []
    for entry in sorted(atlas.abi_entries, key=lambda item: item.semantic_id):
        source_concept = by_concept.get(entry.semantic_id)
        refs = (source_concept.concept.source_rows
                if source_concept is not None else ())
        tables = frozenset(f"{ref.domain}/{ref.table}" for ref in refs)
        formal = frozenset(formal_by_id.get(entry.semantic_id, ()))
        relations = frozenset(relations_by_id.get(entry.semantic_id, ()))
        category = _grammar_category(entry.semantic_id)
        families = {
            rule.family_id for rule in SOURCE_FAMILY_ADAPTERS
            if rule.matches(
                tables=tables, formal=formal, relations=relations,
                grammar_category=category)
        }
        families.update(
            f"source:{table}" for table in tables if table not in _SOURCE_TABLES)
        families.update(
            f"formal:{family}" for family in formal
            if family not in _FORMAL_FAMILIES)
        source_refs = tuple(sorted(
            f"{ref.domain}/{ref.table}/{ref.key}" for ref in refs))
        if not source_refs:
            source_refs = (f"abi:{entry.source}:{entry.index}",)
        family_ids = tuple(sorted(families))
        concepts.append(ConceptFamilyCoverage(
            entry.semantic_id, entry.index, entry.active,
            "SOURCE_ELIGIBLE", "IMPLEMENTATION_UNCOVERED",
            family_ids, source_refs))
        for family in family_ids:
            evidence = {
                "release": atlas.release_sha256,
                "source_bundle": atlas.source_bundle_id,
                "semantic_id": entry.semantic_id,
                "abi_index": entry.index,
                "source_refs": source_refs,
                "formal_families": tuple(sorted(formal)),
                "relations": tuple(sorted(relations)),
                "family": family,
            }
            obligations.append(FamilyObligation(
                entry.semantic_id, family, _digest(evidence),
                "IMPLEMENTATION_UNCOVERED",
                "SOURCE_FAMILY_RULE_UNCLASSIFIED"
                if family.startswith(("source:", "formal:"))
                else "FAMILY_CONSTRUCTOR_CHECKER_NOT_BOUND"))
    family_ids = tuple(sorted({item.family_id for item in obligations}))
    held = tuple(sorted(
        (row.domain, row.table, row.key, row.reason_code)
        for row in atlas.withheld_rows
        if row.source_disposition == "SOURCE_HELD"))
    ir_only = tuple(sorted(
        (row.domain, row.table, row.key, row.reason_code)
        for row in atlas.withheld_rows
        if row.source_disposition == "SOURCE_IR_ONLY"))
    nonconcept = tuple(sorted(
        (
            row.domain, row.table, row.key, row.semantic_id,
            row.reason_code,
            tuple(sorted(
                (
                    rule.family_id for rule in SOURCE_FAMILY_ADAPTERS
                    if f"{row.domain}/{row.table}" in rule.source_tables
                )
            )) if f"{row.domain}/{row.table}" in _SOURCE_TABLES else (
                f"source:{row.domain}/{row.table}",),
        )
        for row in atlas.withheld_rows
        if row.source_disposition == "SOURCE_EMITTED_NON_CONCEPT"
    ))
    pending = tuple(sorted({
        family for _, _, _, _, _, families in nonconcept
        for family in families
    }))
    return SemanticFamilyInventory(
        semantic_release=atlas.release_sha256,
        atlas_bundle_id=atlas.bundle_id,
        source_bundle_id=atlas.source_bundle_id,
        source_coverage_sha256=atlas.coverage_sha256,
        source_eligible_concept_ids=tuple(item.semantic_id for item in concepts),
        required_source_family_ids=family_ids,
        pending_source_family_ids=pending,
        concepts=tuple(concepts),
        obligations=tuple(obligations),
        source_held=held,
        source_ir_only=ir_only,
        source_nonconcept=nonconcept,
        counts=FamilyInventoryCounts(
            atlas_source_concepts=len(atlas.concepts),
            formal_only_abi_identities=len(atlas.abi_entries) - len(atlas.concepts),
            source_eligible_concepts=len(concepts),
            source_held_rows=len(held),
            source_ir_only_rows=len(ir_only),
            source_emitted_nonconcept_rows=len(nonconcept),
            required_families=len(family_ids),
            pending_source_families=len(pending),
            required_family_obligations=len(obligations),
            implementation_uncovered_obligations=len(obligations),
        ),
    )
