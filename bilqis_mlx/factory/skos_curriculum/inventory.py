"""A01-pinned source-family census independent of constructors."""
from __future__ import annotations
from urllib.parse import urlsplit
from lib.ithkuil.src.skos.identity import Identity
from bilqis_mlx.semantics.atlas_projection import (ATLAS_SNAPSHOT_SCHEMA,
    FrozenAtlasConcept, FrozenAtlasRelation, FrozenAtlasSnapshot)
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from .adapters import SOURCE_FAMILY_ADAPTERS
from .common import (_fail, _digest, _load_pinned, _SEMANTIC_RELATIONS,
    _SOURCE_TABLES, _FORMAL_FAMILIES, _FORMAL_ID_PREFIXES)
from .serialization import _strict_source_bytes
from .types import (ConceptFamilyCoverage, FamilyObligation,
    FamilyInventoryCounts, SemanticFamilyInventory)

def _grammar_category(semantic_id: str) -> str | None:
    """Only the source-owned grammar IRI category, never English gloss text."""
    path = urlsplit(semantic_id).path
    marker = "/id/grammar/"
    if marker not in path:
        return None
    try:
        category, value = path.split(marker, 1)[1].split("/")
    except ValueError:
        return None
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
    concept_ids = {item.concept.semantic_id for item in concepts}
    seen_formal = set()
    for binding in atlas.formal_domain_bindings:
        for semantic_id in binding.semantic_ids:
            entry = by_id.get(semantic_id)
            if (entry is None or entry.source not in {
                    "FORMAL_DOMAIN", "PRIOR_ACCEPTED_NATIVE_REGISTRY"}
                    or semantic_id in concept_ids
                    or semantic_id in seen_formal
                    or (binding.family in _FORMAL_ID_PREFIXES
                        and not semantic_id.startswith(
                            _FORMAL_ID_PREFIXES[binding.family]))):
                _fail("BAMF_FAMILY_FORMAL_SOURCE_INVALID")
            seen_formal.add(semantic_id)
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


def _inventory_source_families(atlas: FrozenAtlasSnapshot) -> SemanticFamilyInventory:
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
    source_order = lambda row: (
        row.domain, row.table, row.key, row.semantic_id or "", row.reason_code)
    held = tuple(sorted(
        (row for row in atlas.withheld_rows
         if row.source_disposition == "SOURCE_HELD"), key=source_order))
    ir_only = tuple(sorted(
        (row for row in atlas.withheld_rows
         if row.source_disposition == "SOURCE_IR_ONLY"), key=source_order))
    nonconcept = tuple(sorted((
        (row, tuple(sorted(
            rule.family_id for rule in SOURCE_FAMILY_ADAPTERS
            if f"{row.domain}/{row.table}" in rule.source_tables))
         if f"{row.domain}/{row.table}" in _SOURCE_TABLES else (
             f"source:{row.domain}/{row.table}",))
        for row in atlas.withheld_rows
        if row.source_disposition == "SOURCE_EMITTED_NON_CONCEPT"
    ), key=lambda item: source_order(item[0])))
    pending = tuple(sorted({
        family for _, families in nonconcept
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


def inventory_source_families(atlas: AtlasArtifactSelection) -> SemanticFamilyInventory:
    """Inventory only an A01 artifact selected by the source-pin registry."""
    return _inventory_source_families(_load_pinned(atlas))


def assert_family_inventory_current(
    inventory: SemanticFamilyInventory, atlas: AtlasArtifactSelection,
) -> None:
    """A consumer must rederive source truth; the inventory is not a grant."""
    if (type(inventory) is not SemanticFamilyInventory
            or _strict_source_bytes(inventory)
            != _strict_source_bytes(inventory_source_families(atlas))):
        _fail("BAMF_FAMILY_SOURCE_PROJECTION_DRIFT")
