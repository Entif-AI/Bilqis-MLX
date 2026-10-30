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


from bilqis_mlx.factory.tests.sources.test_skos_curriculum import _snapshot

class SemanticFamilyConstructiveTests(unittest.TestCase):
    def test_source_identity_and_attested_relation_constructive_checkers(self):
        definitions = tuple(
            (identifier, source, AtlasRelation(REL, "urn:lex:root")
             if identifier == "urn:morph:transform" else relation)
            for identifier, source, relation in DEFINITIONS)
        snapshot = _snapshot(definitions)
        compiled = compile_source_constructive_lessons(snapshot)
        identity = next(
            item for item in compiled.lessons
            if item.family_id == "positive_identity"
            and item.semantic_id == "urn:lex:root")
        self.assertEqual(identity.answer_modality, "SEMANTIC_ID")
        self.assertEqual(identity.constituents, ("urn:lex:root",))
        self.assertEqual(identity.prerequisite_closure, ())
        self.assertNotEqual(identity.positive_fact, identity.contrast_fact)
        self.assertTrue(check_source_constructive_lesson(
            identity, "urn:lex:root", snapshot))
        self.assertFalse(check_source_constructive_lesson(
            identity, identity.contrast_fact[1], snapshot))
        relation = next(
            item for item in compiled.lessons
            if item.family_id == "source_attested_relation"
            and item.semantic_id == "urn:lex:sense")
        attested = {
            (edge.source_semantic_id, edge.predicate, edge.target_semantic_id)
            for edge in snapshot.relations}
        self.assertIn(relation.positive_fact, attested)
        self.assertIn(relation.contrast_fact, attested)
        self.assertNotEqual(relation.positive_fact, relation.contrast_fact)
        self.assertEqual(relation.answer_modality, "RELATION_TRIPLE")
        self.assertIn(
            relation.semantic_id, relation.prerequisite_closure)
        self.assertEqual(
            relation.prerequisite_closure, relation.constituents)
        self.assertNotEqual(
            relation.contrast_fact[0], relation.semantic_id)
        self.assertTrue(check_source_constructive_lesson(
            relation, relation.positive_fact, snapshot))
        self.assertFalse(check_source_constructive_lesson(
            relation, relation.contrast_fact, snapshot))
        self.assertTrue(any(
            row.family_id == "numeric_composition"
            for row in compiled.uncovered))
        self.assertEqual(compiled.learning_state, LEARNING_UNVERIFIED)

    def test_source_lesson_checker_rejects_forged_gold_and_foreign_release(self):
        snapshot = _snapshot()
        lesson = next(
            item for item in compile_source_constructive_lessons(snapshot).lessons
            if item.semantic_id == "urn:lex:root"
            and item.family_id == "positive_identity")
        with self.assertRaises(BilqisError) as caught:
            check_source_constructive_lesson(
                replace(lesson, positive_fact=(
                    "identity", "urn:invented", "source:fake")),
                "urn:invented", snapshot)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_LESSON_SOURCE_EVIDENCE_MISMATCH")
        with self.assertRaises(BilqisError):
            check_source_constructive_lesson(
                lesson, lesson.semantic_id,
                replace(snapshot, release_sha256="f" * 64))

    def test_owner_api_preserves_denominator_and_unverified_learning_claims(self):
        snapshot = _snapshot()
        self.assertTrue(any(not item.active for item in snapshot.concepts))
        concept_ids = {
            item.concept.semantic_id for item in snapshot.concepts}
        formal_ids = {
            identifier for binding in snapshot.formal_domain_bindings
            for identifier in binding.semantic_ids}
        self.assertTrue(any(
            entry.semantic_id in formal_ids
            and entry.semantic_id not in concept_ids
            for entry in snapshot.abi_entries))
        frontier = LearnedFrontier(
            snapshot.release_sha256,
            claimed_exposed=("urn:formal:boolean:AND",),
            claimed_qualified=("urn:formal:numeric:ADD",))
        with_adapters = compile_semantic_curriculum(
            snapshot, SOURCE_FAMILY_ADAPTERS, frontier)
        without_adapters = compile_semantic_curriculum(
            snapshot, (), frontier)
        self.assertEqual(
            with_adapters.frozen_census_digest,
            without_adapters.frozen_census_digest)
        self.assertEqual(
            with_adapters.source_eligible_concept_ids,
            without_adapters.source_eligible_concept_ids)
        self.assertEqual(len(with_adapters.source_eligible_concept_ids), 8)
        self.assertEqual(with_adapters.adapter_ready_count, 0)
        self.assertEqual(with_adapters.exposed_count, 0)
        self.assertEqual(with_adapters.qualified_count, 0)
        self.assertEqual(with_adapters.learning_state, LEARNING_UNVERIFIED)
        self.assertEqual(
            with_adapters.unverified_exposure_claims,
            ("urn:formal:boolean:AND",))
        self.assertEqual(
            with_adapters.unverified_qualification_claims,
            ("urn:formal:numeric:ADD",))
        self.assertTrue(all(
            row.learning_state == LEARNING_UNVERIFIED
            and row.source_disposition == "SOURCE_ELIGIBLE"
            and row.implementation_status == "IMPLEMENTATION_UNCOVERED"
            for row in with_adapters.coverage_rows))

    def test_owner_api_rejects_forged_family_and_foreign_learning_release(self):
        snapshot = _snapshot()
        frontier = LearnedFrontier(snapshot.release_sha256)
        forged = SourceFamilyAdapter(
            "numeric_composition",
            source_tables=("lexicon/lexicon_root_senses",))
        with self.assertRaises(BilqisError) as caught:
            compile_semantic_curriculum(snapshot, (forged,), frontier)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_FAMILY_COMPILER_INPUT_INVALID")
        with self.assertRaises(BilqisError) as caught:
            compile_semantic_curriculum(
                snapshot, (), LearnedFrontier("f" * 64))
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_FAMILY_COMPILER_INPUT_INVALID")
