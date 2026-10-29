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


def _snapshot(definitions=DEFINITIONS, *, release=RELEASE):
    entries = []
    concepts = []
    for index, (semantic_id, source, relation) in enumerate(definitions):
        entries.append(AbiEntry(
            index, 0, index, semantic_id, semantic_id,
            "FORMAL_DOMAIN" if source is None else "CANONICAL_SKOS",
            source is None, source is None,
            "SOURCE_ADMITTED" if source is None else "IMPLEMENTATION_UNCOVERED"))
        if source is not None:
            concept = AtlasConcept(
                semantic_id, "grammar" if semantic_id == PHASE else "synthetic",
                ("urn:type:SourceConcept",),
                (AtlasLabel("prefLabel", "source label"),), (), (),
                (relation,) if relation else (),
                (SourceRecordRef(*source),))
            concepts.append(FrozenAtlasConcept(
                concept, index, 0, index, False,
                "IMPLEMENTATION_UNCOVERED", False, "IMPLEMENTATION_UNCOVERED"))
    held = (
        CorpusCoverageRow(
            "mapping", "bilqis_semantic_bridges", "held", "urn:held",
            "SOURCE_HELD", "NOT_APPLICABLE", False,
            "MAPPING_REVIEW_PENDING", "MAPPING_REVIEW_PENDING", "source:owner"),
        CorpusCoverageRow(
            "lexicon", "lexicon_root_evidence", "support", None,
            "SOURCE_IR_ONLY", "NOT_APPLICABLE", False,
            "SUPPORT_IR_ONLY", "SUPPORT_IR_ONLY", "source:owner"),
        CorpusCoverageRow(
            "residue", "composition_components", "component", "urn:structural:row",
            "SOURCE_EMITTED_NON_CONCEPT", "NOT_APPLICABLE", False,
            "STRUCTURAL_SOURCE_ONLY", "STRUCTURAL_SOURCE_ONLY", "source:owner"),
    )
    relations = tuple(FrozenAtlasRelation(
        item.concept.semantic_id, edge.predicate, edge.target)
        for item in concepts for edge in item.concept.relations)
    bindings = (
        FormalDomainBinding(
            "boolean", "pinned:boolean", "1" * 64,
            ("urn:formal:boolean:AND",), ("B.AND",)),
        FormalDomainBinding(
            "numeric", "pinned:numeric", "2" * 64,
            ("urn:formal:numeric:ADD",), ("C.ADD",)),
    )
    return FrozenAtlasSnapshot(
        ATLAS_SNAPSHOT_SCHEMA, "c" * 64, release, SOURCE,
        "d" * 64, "e" * 64, "f" * 64, "0" * 64,
        "1" * 64, "2" * 64, "3" * 64,
        AtlasCounts(
            len(entries), len(entries), len(concepts), len(entries), 1,
            sum(entry.active for entry in entries), 2, 1, 1, len(concepts)),
        bindings, tuple(entries), tuple(sorted(
            concepts, key=lambda item: item.concept.semantic_id)),
        relations, held,
        tuple(sorted((item.semantic_id, item.index) for item in entries)),
        tuple(sorted((item.concept.semantic_id, index)
                     for index, item in enumerate(sorted(
                         concepts, key=lambda item: item.concept.semantic_id)))),
    )


class SemanticFamilyInventoryTests(unittest.TestCase):
    def test_source_checker_replays_facts_without_using_generator(self):
        definitions = tuple(
            (identifier, source, AtlasRelation(REL, "urn:lex:root")
             if identifier == "urn:morph:transform" else relation)
            for identifier, source, relation in DEFINITIONS)
        snapshot = _snapshot(definitions)
        lessons = compile_source_constructive_lessons(snapshot).lessons
        identity = next(item for item in lessons
                        if item.family_id == "positive_identity")
        relation = next(item for item in lessons
                        if item.family_id == "source_attested_relation")
        with patch(
                "bilqis_mlx.factory.skos_curriculum."
                "_compile_source_constructive_lessons_snapshot",
                side_effect=AssertionError("checker used lesson generator")):
            self.assertTrue(check_source_constructive_lesson(
                identity, identity.semantic_id, snapshot))
            self.assertTrue(check_source_constructive_lesson(
                relation, relation.positive_fact, snapshot))
            self.assertFalse(check_source_constructive_lesson(
                relation, list(relation.positive_fact), snapshot))

    def test_checker_rejects_forged_contrast_and_prerequisites(self):
        definitions = tuple(
            (identifier, source, AtlasRelation(REL, "urn:lex:root")
             if identifier == "urn:morph:transform" else relation)
            for identifier, source, relation in DEFINITIONS)
        snapshot = _snapshot(definitions)
        lessons = compile_source_constructive_lessons(snapshot).lessons
        identity = next(item for item in lessons
                        if item.semantic_id == "urn:lex:root"
                        and item.family_id == "positive_identity")
        relation = next(item for item in lessons
                        if item.semantic_id == "urn:lex:sense"
                        and item.family_id == "source_attested_relation")
        for forged in (
                replace(identity, contrast_fact=(
                    "identity", identity.contrast_fact[1], "source:invented")),
                replace(identity, variation_axes=("source-identity", "fantasy")),
                replace(relation, contrast_fact=(
                    "urn:lex:sense", REL, "urn:invented")),
                replace(relation, prerequisite_closure=()),
                replace(relation, variation_axes=("source-relation", "fantasy"))):
            with self.subTest(forged=forged):
                with self.assertRaises(BilqisError) as caught:
                    check_source_constructive_lesson(
                        forged, forged.positive_fact, snapshot)
                self.assertEqual(
                    caught.exception.context["reason"],
                    "BAMF_LESSON_SOURCE_EVIDENCE_MISMATCH")



if __name__ == "__main__":
    unittest.main()
