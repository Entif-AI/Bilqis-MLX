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

class SemanticFamilyCheckerTests(unittest.TestCase):
    def test_second_true_relation_from_same_source_is_not_negative(self):
        snapshot = _snapshot()
        concepts = tuple(
            replace(item, concept=replace(
                item.concept, relations=(
                    *item.concept.relations,
                    AtlasRelation(REL, "urn:morph:composition"))))
            if item.concept.semantic_id == "urn:lex:sense" else item
            for item in snapshot.concepts)
        relations = tuple(
            FrozenAtlasRelation(item.concept.semantic_id, edge.predicate, edge.target)
            for item in concepts for edge in item.concept.relations)
        snapshot = replace(snapshot, concepts=concepts, relations=relations)
        compiled = compile_source_constructive_lessons(snapshot)
        self.assertFalse(any(
            item.semantic_id == "urn:lex:sense"
            and item.family_id == "source_attested_relation"
            for item in compiled.lessons))
        self.assertTrue(any(
            item.semantic_id == "urn:lex:sense"
            and item.family_id == "source_attested_relation"
            for item in compiled.uncovered))

    def test_checker_rejects_same_source_contrast_even_with_recomputed_digest(self):
        definitions = tuple(
            (identifier, source, AtlasRelation(REL, "urn:lex:root")
             if identifier == "urn:morph:transform" else relation)
            for identifier, source, relation in DEFINITIONS)
        snapshot = _snapshot(definitions)
        concepts = tuple(
            replace(item, concept=replace(
                item.concept, relations=(
                    *item.concept.relations,
                    AtlasRelation(REL, "urn:morph:composition"))))
            if item.concept.semantic_id == "urn:lex:sense" else item
            for item in snapshot.concepts)
        relations = tuple(
            FrozenAtlasRelation(item.concept.semantic_id, edge.predicate, edge.target)
            for item in concepts for edge in item.concept.relations)
        snapshot = replace(snapshot, concepts=concepts, relations=relations)
        lesson = next(
            item for item in compile_source_constructive_lessons(snapshot).lessons
            if item.semantic_id == "urn:lex:sense"
            and item.family_id == "source_attested_relation")
        same_source = ("urn:lex:sense", REL, "urn:morph:composition")
        obligation = next(
            item for item in inventory_source_families(snapshot).obligations
            if (item.semantic_id, item.family_id)
            == (lesson.semantic_id, lesson.family_id))
        constituents = tuple(dict.fromkeys((
            lesson.positive_fact[0], lesson.positive_fact[2],
            same_source[0], same_source[2])))
        forged = replace(
            lesson, contrast_fact=same_source, constituents=constituents,
            prerequisite_closure=constituents,
            source_evidence_sha256=public_curriculum._source_lesson_evidence(
                obligation, lesson.positive_fact, same_source))
        with self.assertRaises(BilqisError) as caught:
            check_source_constructive_lesson(
                forged, forged.positive_fact, snapshot)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_LESSON_SOURCE_EVIDENCE_MISMATCH")

    def test_wrapped_source_strings_do_not_pass_lesson_type_boundary(self):
        class WrappedText(str):
            pass

        snapshot = _snapshot()
        lesson = compile_source_constructive_lessons(snapshot).lessons[0]
        with self.assertRaises(BilqisError) as nested:
            replace(lesson, positive_fact=(
                "identity", WrappedText("urn:unverified"), "source:unverified"))
        self.assertEqual(
            nested.exception.context["reason"],
            "BAMF_LESSON_RECORD_INVALID")
        definitions = tuple(
            (identifier, source, AtlasRelation(REL, "urn:lex:root")
             if identifier == "urn:morph:transform" else relation)
            for identifier, source, relation in DEFINITIONS)
        related = _snapshot(definitions)
        relation = next(
            item for item in compile_source_constructive_lessons(related).lessons
            if item.family_id == "source_attested_relation")
        self.assertFalse(check_source_constructive_lesson(
            relation,
            tuple(WrappedText(part) for part in relation.positive_fact),
            related))

    def test_source_proposals_cannot_be_relabelled_as_attestation(self):
        snapshot = _snapshot()
        registry = json.loads((
            Path(__file__).resolve().parents[4]
            / "bilqis_mlx/semantics/atlas_source_pins_v1.json").read_text())
        pin = registry["entries"][0]
        forged = replace(
            snapshot, bundle_id=pin["bundle_id"],
            release_sha256=pin["release_sha256"],
            source_bundle_id=pin["source_bundle_id"])
        census = inventory_source_families(forged)
        candidate = compile_semantic_curriculum(
            forged, SOURCE_FAMILY_ADAPTERS,
            LearnedFrontier(forged.release_sha256))
        lessons = compile_source_constructive_lessons(forged)
        self.assertTrue(all(
            item.source_authority == SOURCE_PROJECTION_ONLY
            and "proposal" in item.schema
            for item in (census, candidate, lessons, lessons.lessons[0])))
        for item, claimed_schema in (
                (census, "bilqis.semantic-family-inventory/v1"),
                (candidate, "bilqis.semantic-curriculum-candidates/v1"),
                (lessons, "bilqis.source-constructive-lesson-set/v1"),
                (lessons.lessons[0], "bilqis.source-constructive-lesson/v1")):
            with self.subTest(item=item):
                with self.assertRaises(BilqisError):
                    replace(
                        item, source_authority="A01_PINNED_SOURCE_ATTESTED",
                        schema=claimed_schema)

    def test_public_census_and_lesson_apis_reject_unpinned_snapshots(self):
        raw = _snapshot()
        lesson = compile_source_constructive_lessons(raw).lessons[0]
        actions = (
            lambda: public_curriculum.inventory_source_families(raw),
            lambda: public_curriculum.compile_semantic_curriculum(
                raw, SOURCE_FAMILY_ADAPTERS, LearnedFrontier(raw.release_sha256)),
            lambda: public_curriculum.compile_source_constructive_lessons(raw),
            lambda: public_curriculum.check_source_constructive_lesson(
                lesson, lesson.positive_fact[1], raw),
        )
        for action in actions:
            with self.subTest(action=action):
                with self.assertRaises(BilqisError) as caught:
                    action()
                self.assertEqual(
                    caught.exception.context["reason"], "ATLAS_SOURCE_SELECTION_INVALID")
