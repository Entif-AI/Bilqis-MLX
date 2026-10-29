"""Source-qualified A08 family inventory, before lesson/checker construction.

This module is deliberately neural-inert. The frozen A01 Atlas determines the
source census; installed constructors cannot alter its eligible denominator.
A08.1b owns binding constructive lessons and independent checkers to these rows.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from urllib.parse import urlsplit

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.atlas_projection import (
    ATLAS_SNAPSHOT_SCHEMA, CorpusCoverageRow, FrozenAtlasConcept,
    FrozenAtlasRelation, FrozenAtlasSnapshot,
)
from bilqis_mlx.semantics.atlas_snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
)
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.relations import SEMANTIC_PREDICATES


FAMILY_INVENTORY_SCHEMA = "bilqis.semantic-family-inventory-proposal/v1"
FAMILY_OBLIGATION_SCHEMA = "bilqis.semantic-family-obligation/v1"
FAMILY_CONCEPT_SCHEMA = "bilqis.semantic-family-concept/v1"
FAMILY_RULE_SCHEMA = "bilqis.semantic-family-source-rule/v1"
CURRICULUM_CANDIDATE_SCHEMA = "bilqis.semantic-curriculum-proposal/v1"
LEARNED_FRONTIER_SCHEMA = "bilqis.semantic-learned-frontier/v1"
SOURCE_LESSON_SCHEMA = "bilqis.source-constructive-lesson-proposal/v1"
SOURCE_LESSON_SET_SCHEMA = "bilqis.source-constructive-lesson-proposal-set/v1"
LEARNING_UNVERIFIED = "LEARNING_UNVERIFIED"
SOURCE_PROJECTION_ONLY = "SOURCE_PROJECTION_NOT_AUTHORITY"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
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
_FORMAL_ID_PREFIXES = {
    "boolean": ("legacy:cogal.operator.", "urn:formal:boolean:"),
    "numeric": ("bilqis.numeric/v1:school.op.", "urn:formal:numeric:"),
}
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
    learning_state: str = LEARNING_UNVERIFIED
    schema: str = FAMILY_CONCEPT_SCHEMA


@dataclass(frozen=True)
class FamilyObligation:
    semantic_id: str
    family_id: str
    source_evidence_sha256: str
    implementation_status: str
    reason: str
    learning_state: str = LEARNING_UNVERIFIED
    source_disposition: str = "SOURCE_ELIGIBLE"
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
    source_held: tuple[CorpusCoverageRow, ...]
    source_ir_only: tuple[CorpusCoverageRow, ...]
    source_nonconcept: tuple[
        tuple[CorpusCoverageRow, tuple[str, ...]], ...]
    counts: FamilyInventoryCounts
    source_authority: str = SOURCE_PROJECTION_ONLY
    schema: str = FAMILY_INVENTORY_SCHEMA

    def __post_init__(self) -> None:
        if (self.source_authority != SOURCE_PROJECTION_ONLY
                or self.schema != FAMILY_INVENTORY_SCHEMA):
            _fail("BAMF_FAMILY_PROPOSAL_AUTHORITY_INVALID")

    @property
    def digest(self) -> str:
        return _digest(asdict(self))


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
    return _inventory_source_families(load_pinned_atlas_snapshot(atlas))


def assert_family_inventory_current(
    inventory: SemanticFamilyInventory, atlas: AtlasArtifactSelection,
) -> None:
    """A consumer must rederive source truth; the inventory is not a grant."""
    if (not isinstance(inventory, SemanticFamilyInventory)
            or inventory != inventory_source_families(atlas)):
        _fail("BAMF_FAMILY_SOURCE_PROJECTION_DRIFT")


@dataclass(frozen=True)
class LearnedFrontier:
    """Unverified learner claims; source eligibility never depends on them."""

    semantic_release: str
    claimed_exposed: tuple[str, ...] = ()
    claimed_qualified: tuple[str, ...] = ()
    schema: str = LEARNED_FRONTIER_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.semantic_release, str)
                or not _SHA.fullmatch(self.semantic_release)
                or any(not isinstance(group, tuple)
                       or group != tuple(sorted(set(group)))
                       or any(not isinstance(item, str) or not item
                              for item in group)
                       for group in (
                           self.claimed_exposed, self.claimed_qualified))
                or self.schema != LEARNED_FRONTIER_SCHEMA):
            _fail("BAMF_FAMILY_LEARNED_FRONTIER_INVALID")


@dataclass(frozen=True)
class CurriculumCandidateSet:
    """A08.1a census-only bridge; A08.1b owns constructive readiness."""

    census: SemanticFamilyInventory
    source_adapter_ids: tuple[str, ...]
    unverified_exposure_claims: tuple[str, ...]
    unverified_qualification_claims: tuple[str, ...]
    source_lessons: tuple["SourceConstructiveLesson", ...] = ()
    learning_state: str = LEARNING_UNVERIFIED
    adapter_ready_count: int = 0
    exposed_count: int = 0
    qualified_count: int = 0
    status: str = "IMPLEMENTATION_DEBT"
    source_authority: str = SOURCE_PROJECTION_ONLY
    schema: str = CURRICULUM_CANDIDATE_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.census, SemanticFamilyInventory)
                or self.source_adapter_ids
                != tuple(sorted(set(self.source_adapter_ids)))
                or not isinstance(self.source_lessons, tuple)
                or any(not isinstance(item, SourceConstructiveLesson)
                       or item.semantic_release != self.census.semantic_release
                       for item in self.source_lessons)
                or self.learning_state != LEARNING_UNVERIFIED
                or any(value != 0 for value in (
                    self.adapter_ready_count, self.exposed_count,
                    self.qualified_count))
                or self.status != "IMPLEMENTATION_DEBT"
                or self.source_authority != SOURCE_PROJECTION_ONLY
                or self.schema != CURRICULUM_CANDIDATE_SCHEMA):
            _fail("BAMF_FAMILY_CANDIDATE_SET_INVALID")

    @property
    def semantic_release(self) -> str:
        return self.census.semantic_release

    @property
    def atlas_bundle_id(self) -> str:
        return self.census.atlas_bundle_id

    @property
    def source_eligible_concept_ids(self) -> tuple[str, ...]:
        return self.census.source_eligible_concept_ids

    @property
    def required_source_family_ids(self) -> tuple[str, ...]:
        return self.census.required_source_family_ids

    @property
    def coverage_rows(self) -> tuple[FamilyObligation, ...]:
        return self.census.obligations

    @property
    def source_hold_rows(self) -> tuple[CorpusCoverageRow, ...]:
        return self.census.source_held

    @property
    def source_held_count(self) -> int:
        return self.census.counts.source_held_rows

    @property
    def implementation_uncovered_count(self) -> int:
        return self.census.counts.implementation_uncovered_obligations

    @property
    def frozen_census_digest(self) -> str:
        return self.census.digest

    @property
    def source_lesson_count(self) -> int:
        return len(self.source_lessons)


def _compile_semantic_curriculum_snapshot(
    atlas: FrozenAtlasSnapshot,
    source_adapters: tuple[SourceFamilyAdapter, ...],
    learned_frontier: LearnedFrontier,
) -> CurriculumCandidateSet:
    """Original A08 owner API, staged without constructor/learning promotion."""
    census = _inventory_source_families(atlas)
    if (not isinstance(source_adapters, tuple)
            or any(not isinstance(item, SourceFamilyAdapter)
                   or item not in SOURCE_FAMILY_ADAPTERS
                   for item in source_adapters)
            or len(set(item.family_id for item in source_adapters))
            != len(source_adapters)
            or not isinstance(learned_frontier, LearnedFrontier)
            or learned_frontier.semantic_release != census.semantic_release):
        _fail("BAMF_FAMILY_COMPILER_INPUT_INVALID")
    return CurriculumCandidateSet(
        census=census,
        source_adapter_ids=tuple(sorted(
            item.family_id for item in source_adapters)),
        unverified_exposure_claims=learned_frontier.claimed_exposed,
        unverified_qualification_claims=learned_frontier.claimed_qualified,
        source_lessons=_compile_source_constructive_lessons_snapshot(
            atlas, census=census).lessons)


def compile_semantic_curriculum(
    atlas: AtlasArtifactSelection,
    source_adapters: tuple[SourceFamilyAdapter, ...],
    learned_frontier: LearnedFrontier,
) -> CurriculumCandidateSet:
    """Original three-argument API with an A01-pinned source authority."""
    return _compile_semantic_curriculum_snapshot(
        load_pinned_atlas_snapshot(atlas), source_adapters, learned_frontier)


def assert_curriculum_candidate_current(
    candidate: CurriculumCandidateSet,
    atlas: AtlasArtifactSelection,
    source_adapters: tuple[SourceFamilyAdapter, ...],
    learned_frontier: LearnedFrontier,
) -> None:
    """No transferable attestation: replay exact A01 and learner claims."""
    if (not isinstance(candidate, CurriculumCandidateSet)
            or candidate != compile_semantic_curriculum(
                atlas, source_adapters, learned_frontier)):
        _fail("BAMF_CANDIDATE_SOURCE_PROJECTION_DRIFT")


@dataclass(frozen=True)
class SourceConstructiveLesson:
    """An exact source-fact teaching contrast, not a learner credit receipt."""

    semantic_release: str
    semantic_id: str
    family_id: str
    source_evidence_sha256: str
    positive_fact: tuple[str, ...]
    contrast_fact: tuple[str, ...]
    answer_modality: str
    checker_reference: str
    constituents: tuple[str, ...]
    prerequisite_closure: tuple[str, ...]
    variation_axes: tuple[str, ...]
    learning_state: str = LEARNING_UNVERIFIED
    source_authority: str = SOURCE_PROJECTION_ONLY
    schema: str = SOURCE_LESSON_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.semantic_release, str)
                or not _SHA.fullmatch(self.semantic_release)
                or not isinstance(self.source_evidence_sha256, str)
                or not _SHA.fullmatch(self.source_evidence_sha256)
                or not self.semantic_id or not self.family_id
                or not isinstance(self.positive_fact, tuple)
                or not isinstance(self.contrast_fact, tuple)
                or not self.positive_fact or not self.contrast_fact
                or self.positive_fact == self.contrast_fact
                or self.answer_modality not in {
                    "SEMANTIC_ID", "RELATION_TRIPLE"}
                or not self.checker_reference
                or not isinstance(self.constituents, tuple)
                or not isinstance(self.prerequisite_closure, tuple)
                or not isinstance(self.variation_axes, tuple)
                or not self.variation_axes
                or self.learning_state != LEARNING_UNVERIFIED
                or self.source_authority != SOURCE_PROJECTION_ONLY
                or self.schema != SOURCE_LESSON_SCHEMA):
            _fail("BAMF_LESSON_RECORD_INVALID")


@dataclass(frozen=True)
class SourceConstructiveLessonSet:
    semantic_release: str
    census_digest: str
    lessons: tuple[SourceConstructiveLesson, ...]
    uncovered: tuple[FamilyObligation, ...]
    learning_state: str = LEARNING_UNVERIFIED
    source_authority: str = SOURCE_PROJECTION_ONLY
    schema: str = SOURCE_LESSON_SET_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.lessons, tuple)
                or any(not isinstance(item, SourceConstructiveLesson)
                       for item in self.lessons)):
            _fail("BAMF_LESSON_SET_INVALID")
        keys = tuple(
            (item.semantic_id, item.family_id) for item in self.lessons)
        if (not isinstance(self.semantic_release, str)
                or not _SHA.fullmatch(self.semantic_release)
                or not isinstance(self.census_digest, str)
                or not _SHA.fullmatch(self.census_digest)
                or not isinstance(self.uncovered, tuple)
                or any(item.semantic_release != self.semantic_release
                       for item in self.lessons)
                or any(not isinstance(item, FamilyObligation)
                       for item in self.uncovered)
                or len(set(keys)) != len(keys)
                or self.learning_state != LEARNING_UNVERIFIED
                or self.source_authority != SOURCE_PROJECTION_ONLY
                or self.schema != SOURCE_LESSON_SET_SCHEMA):
            _fail("BAMF_LESSON_SET_INVALID")


def _compile_source_constructive_lessons_snapshot(
    atlas: FrozenAtlasSnapshot,
    *, census: SemanticFamilyInventory | None = None,
) -> SourceConstructiveLessonSet:
    """Compile only facts provable from A01; other families remain debt."""
    authoritative = _inventory_source_families(atlas)
    if census is not None and census != authoritative:
        _fail("BAMF_LESSON_CENSUS_DRIFT")
    census = authoritative
    by_id = {item.semantic_id: item for item in census.concepts}
    eligible = census.source_eligible_concept_ids
    position = {identifier: index for index, identifier in enumerate(eligible)}
    relations = tuple(sorted(
        (edge.source_semantic_id, edge.predicate, edge.target_semantic_id)
        for edge in atlas.relations
        if edge.source_semantic_id in by_id
        and edge.target_semantic_id in by_id
        and edge.predicate in _SEMANTIC_RELATIONS))
    relations_by_source: dict[str, tuple[str, str, str]] = {}
    for triple in relations:
        relations_by_source.setdefault(triple[0], triple)
    lessons = []
    uncovered = []
    for obligation in census.obligations:
        semantic_id = obligation.semantic_id
        family = obligation.family_id
        if family == "positive_identity" and len(eligible) > 1:
            contrast_id = eligible[(position[semantic_id] + 1) % len(eligible)]
            positive = ("identity", semantic_id, by_id[semantic_id].source_refs[0])
            contrast = ("identity", contrast_id, by_id[contrast_id].source_refs[0])
            modality = "SEMANTIC_ID"
            checker = "bilqis.source-checker.identity/v1"
            constituents = (semantic_id,)
            prerequisites = ()
            axes = ("source-identity", "source-contrast")
        elif family == "source_attested_relation" and len(relations) > 1:
            positive = relations_by_source.get(semantic_id)
            if positive is None:
                uncovered.append(obligation)
                continue
            contrast = next((item for item in relations if item != positive), None)
            if contrast is None:
                uncovered.append(obligation)
                continue
            modality = "RELATION_TRIPLE"
            checker = "bilqis.source-checker.attested-relation/v1"
            constituents = tuple(dict.fromkeys((positive[0], positive[2])))
            prerequisites = tuple(
                item for item in constituents if item != semantic_id)
            axes = ("source-relation", "source-contrast")
        else:
            uncovered.append(obligation)
            continue
        lessons.append(SourceConstructiveLesson(
            atlas.release_sha256, semantic_id, family,
            obligation.source_evidence_sha256,
            tuple(positive), tuple(contrast), modality, checker,
            constituents, prerequisites, axes))
    return SourceConstructiveLessonSet(
        atlas.release_sha256, census.digest, tuple(lessons),
        tuple(uncovered))


def compile_source_constructive_lessons(
    atlas: AtlasArtifactSelection,
    *, census: SemanticFamilyInventory | None = None,
) -> SourceConstructiveLessonSet:
    return _compile_source_constructive_lessons_snapshot(
        load_pinned_atlas_snapshot(atlas), census=census)


def assert_source_lesson_set_current(
    lessons: SourceConstructiveLessonSet,
    atlas: AtlasArtifactSelection,
) -> None:
    """Reconstruct source lessons at the consuming boundary, never trust a tag."""
    if (not isinstance(lessons, SourceConstructiveLessonSet)
            or lessons != compile_source_constructive_lessons(atlas)):
        _fail("BAMF_LESSON_SOURCE_PROJECTION_DRIFT")


def _check_source_constructive_lesson_snapshot(
    lesson: SourceConstructiveLesson, answer: object,
    atlas: FrozenAtlasSnapshot,
) -> bool:
    """Independent source replay; never trust a generator's claimed gold."""
    if not isinstance(lesson, SourceConstructiveLesson):
        _fail("BAMF_LESSON_CHECKER_INPUT_INVALID")
    verified = _compile_source_constructive_lessons_snapshot(atlas)
    if lesson not in verified.lessons:
        _fail("BAMF_LESSON_SOURCE_EVIDENCE_MISMATCH")
    if lesson.answer_modality == "SEMANTIC_ID":
        return type(answer) is str and answer == lesson.positive_fact[1]
    if lesson.answer_modality == "RELATION_TRIPLE":
        return type(answer) is tuple and answer == lesson.positive_fact
    _fail("BAMF_LESSON_CHECKER_UNSUPPORTED")


def check_source_constructive_lesson(
    lesson: SourceConstructiveLesson, answer: object,
    atlas: AtlasArtifactSelection,
) -> bool:
    return _check_source_constructive_lesson_snapshot(
        lesson, answer, load_pinned_atlas_snapshot(atlas))
