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

from bilqis_mlx.factory.tests.skos.real_adversarial_helpers import verify_real_source_adversaries


def _compile_real_release(corpus: str, root: Path):
    prior = root / "bilqis_mlx/semantics/copular_registry_v1.json"
    boolean = root / "bilqis_mlx/semantics/legacy_abi_v1.json"
    numeric = root / "bilqis_mlx/semantics/numeric_v1.json"
    bindings = (
        FormalDomainBinding(
            "boolean", "bilqis_mlx/semantics/legacy_abi_v1.json",
            hashlib.sha256(boolean.read_bytes()).hexdigest(),
            ("legacy:cogal.operator.NOT", "legacy:cogal.operator.AND"),
            ("B.NOT", "B.AND")),
        FormalDomainBinding(
            "numeric", "bilqis_mlx/semantics/numeric_v1.json",
            hashlib.sha256(numeric.read_bytes()).hexdigest(),
            ("bilqis.numeric/v1:school.op.COUNT",
             "bilqis.numeric/v1:school.op.SUCC"),
            ("C.COUNT", "C.SUCCESSOR")),
    )
    return compile_atlas_release(
        corpus, Path(corpus) / "coverage.json", prior, bindings)


def _exercise_public_replay(test, release):
    with tempfile.TemporaryDirectory() as directory:
        artifact = persist_atlas_release(release, directory)
        snapshot = load_atlas_snapshot(artifact.path)
        pin = AtlasArtifactSelection(
            artifact.path, artifact.bundle_id, release.digest,
            release.source_bundle_id)
        pinned = load_pinned_atlas_snapshot(pin)
        public_census = public_curriculum.inventory_source_families(pin)
        public_candidate = public_curriculum.compile_semantic_curriculum(
            pin, SOURCE_FAMILY_ADAPTERS,
            LearnedFrontier(snapshot.release_sha256))
        test.assertFalse(any(
            item.family_id == "source_attested_relation"
            for item in public_candidate.source_lessons))
        identity_lesson = next(
            item for item in public_candidate.source_lessons
            if item.family_id == "positive_identity")
        test.assertTrue(public_curriculum.check_source_constructive_lesson(
            identity_lesson, identity_lesson.positive_fact[1], pin))

        class WrappedText(str):
            pass

        test.assertFalse(public_curriculum.check_source_constructive_lesson(
            identity_lesson, WrappedText(identity_lesson.positive_fact[1]),
            pin))
        test.assertEqual(
            public_census.source_authority, SOURCE_PROJECTION_ONLY)
        test.assertEqual(
            public_candidate.source_authority, SOURCE_PROJECTION_ONLY)
        test.assertIsNone(public_curriculum.assert_family_inventory_current(
            public_census, pin))
        test.assertIsNone(public_curriculum.assert_curriculum_candidate_current(
            public_candidate, pin,
            LearnedFrontier(snapshot.release_sha256)))
        public_lessons = public_curriculum.compile_source_constructive_lessons(
            pin)
        test.assertIsNone(public_curriculum.assert_source_lesson_set_current(
            public_lessons, pin))
        forged_census = replace(
            public_census,
            source_eligible_concept_ids=public_census.source_eligible_concept_ids[:8])
        with test.assertRaises(BilqisError) as census_drift:
            public_curriculum.assert_family_inventory_current(
                forged_census, pin)
        test.assertEqual(
            census_drift.exception.context["reason"],
            "BAMF_FAMILY_SOURCE_PROJECTION_DRIFT")
        with test.assertRaises(BilqisError) as candidate_drift:
            public_curriculum.assert_curriculum_candidate_current(
                replace(public_candidate, census=forged_census),
                pin, LearnedFrontier(snapshot.release_sha256))
        test.assertEqual(
            candidate_drift.exception.context["reason"],
            "BAMF_CANDIDATE_SOURCE_PROJECTION_DRIFT")
        fake_adapters = (
            SourceFamilyAdapter("invented_family", all_eligible=True),)
        with test.assertRaises(BilqisError) as adapter_drift:
            public_curriculum.compile_semantic_curriculum(
                pin, fake_adapters, LearnedFrontier(snapshot.release_sha256))
        test.assertEqual(
            adapter_drift.exception.context["reason"],
            "BAMF_FAMILY_COMPILER_INPUT_INVALID")
        with test.assertRaises(BilqisError) as lesson_drift:
            public_curriculum.assert_source_lesson_set_current(
                replace(public_lessons, lessons=public_lessons.lessons[:8]),
                pin)
        test.assertEqual(
            lesson_drift.exception.context["reason"],
            "BAMF_LESSON_SOURCE_PROJECTION_DRIFT")
        verify_real_source_adversaries(
            test, directory, artifact, pin, release, snapshot,
            public_candidate, public_lessons, public_census,
            identity_lesson, forged_census)
        return snapshot, pinned, public_census, public_candidate


def _assert_real_census_contract(
    test, release, snapshot, pinned, public_census, public_candidate,
):
    census = inventory_source_families(snapshot)
    test.assertEqual(public_census, census)
    test.assertEqual(pinned, snapshot)
    test.assertEqual(public_candidate.frozen_census_digest, census.digest)
    lexicon_root = next(
        item.concept.semantic_id for item in snapshot.concepts
        if item.concept.kind == "root")
    forged_formal = replace(
        snapshot, formal_domain_bindings=(
            replace(snapshot.formal_domain_bindings[0],
                    semantic_ids=(lexicon_root,)),
            *snapshot.formal_domain_bindings[1:]))
    with test.assertRaises(BilqisError) as caught:
        inventory_source_families(forged_formal)
    test.assertEqual(
        caught.exception.context["reason"],
        "BAMF_FAMILY_FORMAL_SOURCE_INVALID")
    test.assertEqual(census.counts.atlas_source_concepts, 9079)
    test.assertEqual(census.counts.formal_only_abi_identities, 228)
    test.assertEqual(census.counts.source_eligible_concepts, 9307)
    test.assertEqual(
        census.counts.atlas_source_concepts, release.counts.semantic_concepts)
    test.assertEqual(
        census.counts.source_eligible_concepts, release.counts.abi_entries)
    test.assertEqual(census.counts.source_held_rows, release.counts.source_held)
    test.assertEqual(
        census.counts.source_ir_only_rows, release.counts.source_ir_only)
    test.assertGreater(census.counts.source_emitted_nonconcept_rows, 0)
    test.assertIn("morphology_composition", census.pending_source_family_ids)
    test.assertIn("morphology_decomposition", census.pending_source_family_ids)
    test.assertEqual(
        len(census.source_eligible_concept_ids),
        len(set(census.source_eligible_concept_ids)))
    test.assertGreater(
        census.counts.required_family_obligations,
        census.counts.source_eligible_concepts)
    lesson_set = compile_source_constructive_lessons(snapshot, census=census)
    test.assertEqual(len(lesson_set.lessons), 9307)
    test.assertEqual(len(lesson_set.uncovered), 3044)
    test.assertEqual(lesson_set.learning_state, LEARNING_UNVERIFIED)


class SemanticFamilyRealCorpusTests(unittest.TestCase):
    def test_real_pinned_corpus_census_if_supplied(self):
        corpus = os.environ.get("BILQIS_ATLAS_REAL_CORPUS")
        if not corpus:
            self.skipTest("set BILQIS_ATLAS_REAL_CORPUS for full pinned census")
        release = _compile_real_release(
            corpus, Path(__file__).resolve().parents[4])
        state = _exercise_public_replay(self, release)
        _assert_real_census_contract(self, release, *state)
