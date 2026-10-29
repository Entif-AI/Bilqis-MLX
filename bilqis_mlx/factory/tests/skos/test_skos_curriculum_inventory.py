"""A08.1a source-family census: literal obligations, holds and no silent debt loss."""
from __future__ import annotations

from dataclasses import fields, replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory import skos_curriculum as public_curriculum
from bilqis_mlx.factory.skos_curriculum import (
    LEARNING_UNVERIFIED, SOURCE_FAMILY_ADAPTERS, SOURCE_PROJECTION_ONLY,
    LearnedFrontier,
    SourceFamilyAdapter,
    _check_source_constructive_lesson_snapshot as check_source_constructive_lesson,
    _compile_semantic_curriculum_snapshot as compile_semantic_curriculum,
    _compile_source_constructive_lessons_snapshot as compile_source_constructive_lessons,
    _inventory_source_families as inventory_source_families,
)
from bilqis_mlx.semantics.atlas_projection import (
    ATLAS_SNAPSHOT_SCHEMA, AbiEntry, AtlasConcept, AtlasCounts,
    AtlasLabel, AtlasRelation, CorpusCoverageRow, FormalDomainBinding,
    FrozenAtlasConcept, FrozenAtlasRelation, FrozenAtlasSnapshot,
    SourceRecordRef, compile_atlas_release, load_atlas_snapshot,
    persist_atlas_release,
)
from bilqis_mlx.semantics.atlas_snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
)
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.publication import json_bytes
from lib.ithkuil.src.skos.relations import SEMANTIC_PREDICATES


PHASE = Identity("grammar", ("PHASE", "FLC")).iri
REL = SEMANTIC_PREDICATES["subsumption"]
SOURCE = "b" * 64
RELEASE = "a" * 64
DEFINITIONS = (
    ("urn:formal:boolean:AND", None, None),
    ("urn:formal:numeric:ADD", None, None),
    (PHASE, ("atomic", "morphemes_atomic", "phase"), None),
    ("urn:lex:root", ("lexicon", "lexicon_roots", "root"), None),
    ("urn:lex:sense", ("lexicon", "lexicon_root_senses", "sense"),
     AtlasRelation(REL, "urn:lex:root")),
    ("urn:morph:composition", ("residue", "morpheme_compositions", "comp"), None),
    ("urn:morph:transform", ("residue", "allomorph_rules", "rule"), None),
    ("urn:unknown:source", ("other", "new_source_table", "future"), None),
)


from bilqis_mlx.factory.tests.test_skos_curriculum import _snapshot

class SemanticFamilyCensusTests(unittest.TestCase):
    def test_literal_source_qualified_families_and_full_denominator(self):
        census = inventory_source_families(_snapshot())
        by_id = {row.semantic_id: row for row in census.concepts}
        self.assertEqual(census.counts.source_eligible_concepts, 8)
        self.assertEqual(census.counts.atlas_source_concepts, 6)
        self.assertEqual(census.counts.formal_only_abi_identities, 2)
        self.assertEqual(census.counts.source_held_rows, 1)
        self.assertEqual(census.counts.source_ir_only_rows, 1)
        self.assertEqual(census.counts.source_emitted_nonconcept_rows, 1)
        self.assertEqual(census.pending_source_family_ids,
                         ("morphology_composition", "morphology_decomposition"))
        self.assertEqual(census.counts.required_family_obligations,
                         len(census.obligations))
        self.assertEqual(census.counts.implementation_uncovered_obligations,
                         len(census.obligations))
        self.assertEqual(set(by_id["urn:formal:boolean:AND"].required_family_ids),
                         {"positive_identity", "typed_role_binding",
                          "boolean_composition"})
        self.assertEqual(set(by_id["urn:formal:numeric:ADD"].required_family_ids),
                         {"positive_identity", "typed_role_binding",
                          "numeric_composition"})
        self.assertEqual(set(by_id[PHASE].required_family_ids),
                         {"positive_identity", "scope_modality_time"})
        self.assertEqual(set(by_id["urn:lex:sense"].required_family_ids),
                         {"positive_identity", "typed_role_binding",
                          "source_attested_relation"})
        self.assertEqual(set(by_id["urn:morph:composition"].required_family_ids),
                         {"positive_identity", "morphology_composition",
                          "morphology_decomposition"})
        self.assertEqual(set(by_id["urn:morph:transform"].required_family_ids),
                         {"positive_identity", "released_transformations"})
        self.assertEqual(set(by_id["urn:unknown:source"].required_family_ids),
                         {"positive_identity", "source:other/new_source_table"})
        self.assertNotIn("urn:held", census.source_eligible_concept_ids)
        self.assertIn(CorpusCoverageRow(
            "mapping", "bilqis_semantic_bridges", "held", "urn:held",
            "SOURCE_HELD", "NOT_APPLICABLE", False,
            "MAPPING_REVIEW_PENDING", "MAPPING_REVIEW_PENDING",
            "source:owner"), census.source_held)
        self.assertEqual(
            census.source_nonconcept[0][0].owner, "source:owner")

    def test_source_eligibility_does_not_depend_on_available_constructors(self):
        snapshot = _snapshot()
        first = inventory_source_families(snapshot)
        second = inventory_source_families(snapshot)
        self.assertEqual(first, second)
        self.assertEqual(first.digest, second.digest)
        self.assertTrue(all(
            row.implementation_status == "IMPLEMENTATION_UNCOVERED"
            for row in first.obligations))
        self.assertEqual(
            tuple(sorted({row.family_id for row in first.obligations})),
            first.required_source_family_ids)
        self.assertEqual(len(SOURCE_FAMILY_ADAPTERS), 9)

    def test_source_gloss_changes_do_not_invent_semantic_family(self):
        original = _snapshot()
        first = original.concepts[0]
        altered = replace(
            first, concept=replace(first.concept, labels=(
                AtlasLabel("prefLabel", "This English gloss says time and modality"),)))
        changed = replace(original, concepts=(altered, *original.concepts[1:]))
        before = inventory_source_families(original)
        after = inventory_source_families(changed)
        self.assertEqual(before.required_source_family_ids,
                         after.required_source_family_ids)
        self.assertEqual(tuple(row.required_family_ids for row in before.concepts),
                         tuple(row.required_family_ids for row in after.concepts))

    def test_release_changes_bind_family_evidence_without_reassigning_ids(self):
        first = inventory_source_families(_snapshot())
        second = inventory_source_families(_snapshot(release="9" * 64))
        self.assertEqual(first.source_eligible_concept_ids,
                         second.source_eligible_concept_ids)
        self.assertEqual(first.required_source_family_ids,
                         second.required_source_family_ids)
        self.assertNotEqual(first.digest, second.digest)
        self.assertNotEqual(first.obligations[0].source_evidence_sha256,
                            second.obligations[0].source_evidence_sha256)

    def test_held_identity_cannot_be_admitted_into_census(self):
        snapshot = _snapshot()
        changed = replace(snapshot, withheld_rows=(
            replace(snapshot.withheld_rows[0],
                    semantic_id="urn:formal:boolean:AND"),
            *snapshot.withheld_rows[1:]))
        with self.assertRaises(BilqisError) as caught:
            inventory_source_families(changed)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_FAMILY_SOURCE_HOLD_CENSUS_INVALID")

    def test_unknown_source_family_is_visible_debt_not_a_hold(self):
        census = inventory_source_families(_snapshot())
        item = next(row for row in census.obligations
                    if row.family_id == "source:other/new_source_table")
        self.assertEqual(item.reason, "SOURCE_FAMILY_RULE_UNCLASSIFIED")
        self.assertEqual(item.implementation_status, "IMPLEMENTATION_UNCOVERED")
        self.assertEqual(next(row for row in census.concepts
                              if row.semantic_id == item.semantic_id
                              ).source_disposition, "SOURCE_ELIGIBLE")

    def test_foreign_formal_binding_cannot_create_family_obligation(self):
        snapshot = _snapshot()
        forged = replace(
            snapshot, formal_domain_bindings=(
                replace(snapshot.formal_domain_bindings[0],
                        semantic_ids=("urn:foreign:invented",)),
                snapshot.formal_domain_bindings[1]))
        with self.assertRaises(BilqisError) as caught:
            inventory_source_families(forged)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_FAMILY_FORMAL_SOURCE_INVALID")

    def test_same_abi_formal_family_substitution_fails_closed(self):
        snapshot = _snapshot()
        for replacement_id in (
                "urn:lex:root", "urn:formal:numeric:ADD"):
            with self.subTest(replacement_id=replacement_id):
                forged = replace(
                    snapshot, formal_domain_bindings=(
                        replace(snapshot.formal_domain_bindings[0],
                                semantic_ids=(replacement_id,)),
                        snapshot.formal_domain_bindings[1]))
                with self.assertRaises(BilqisError) as caught:
                    inventory_source_families(forged)
                self.assertEqual(
                    caught.exception.context["reason"],
                    "BAMF_FAMILY_FORMAL_SOURCE_INVALID")

    def test_forged_relation_without_source_concept_is_not_admitted(self):
        snapshot = _snapshot()
        forged = replace(snapshot, relations=(
            FrozenAtlasRelation("urn:formal:boolean:AND", REL,
                                "urn:formal:numeric:ADD"),
            *snapshot.relations))
        with self.assertRaises(BilqisError) as caught:
            inventory_source_families(forged)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_FAMILY_RELATION_SOURCE_INVALID")

    def test_forged_grammar_host_does_not_mint_scope_family(self):
        forged_id = "https://example.invalid/id/grammar/PHASE/FLC"
        definitions = tuple(
            (forged_id if semantic_id == PHASE else semantic_id, source, relation)
            for semantic_id, source, relation in DEFINITIONS)
        census = inventory_source_families(_snapshot(definitions))
        item = next(row for row in census.concepts if row.semantic_id == forged_id)
        self.assertEqual(item.required_family_ids, ("positive_identity",))
