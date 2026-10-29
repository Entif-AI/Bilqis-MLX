"""Reusable source-family matchers; not lesson constructors."""
from __future__ import annotations
from dataclasses import dataclass
from .common import (FAMILY_RULE_SCHEMA, _SEMANTIC_RELATIONS,
                     _SCOPE_MODALITY_TIME_CATEGORIES)

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
