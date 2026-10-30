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

def verify_real_source_adversaries(
    test, directory, artifact, pin, release, snapshot, public_candidate,
    public_lessons, public_census, identity_lesson, forged_census,
):
    class EqAnyInventory(public_curriculum.SemanticFamilyInventory):
        def __eq__(self, other):
            return True
        def __ne__(self, other):
            return False

    class EqAnyCandidate(public_curriculum.CurriculumCandidateSet):
        def __eq__(self, other):
            return True
        def __ne__(self, other):
            return False

    class EqAnyLessonSet(public_curriculum.SourceConstructiveLessonSet):
        def __eq__(self, other):
            return True
        def __ne__(self, other):
            return False

    class EqAnyLesson(public_curriculum.SourceConstructiveLesson):
        def __eq__(self, other):
            return True
        def __ne__(self, other):
            return False

    def as_subclass(cls, source):
        return cls(**{
            field.name: getattr(source, field.name)
            for field in fields(source)})

    evil_inventory = as_subclass(EqAnyInventory, forged_census)
    evil_candidate = as_subclass(EqAnyCandidate, public_candidate)
    evil_lessons = as_subclass(EqAnyLessonSet, public_lessons)
    nested_evil = replace(public_candidate, census=evil_inventory)
    for action in (
            lambda: public_curriculum.assert_family_inventory_current(
                evil_inventory, pin),
            lambda: public_curriculum.assert_curriculum_candidate_current(
                evil_candidate, pin,
                LearnedFrontier(snapshot.release_sha256)),
            lambda: public_curriculum.assert_curriculum_candidate_current(
                nested_evil, pin,
                LearnedFrontier(snapshot.release_sha256)),
            lambda: public_curriculum.assert_source_lesson_set_current(
                evil_lessons, pin)):
        with test.subTest(equality_override=action):
            with test.assertRaises(BilqisError):
                action()
    fake_lesson_fields = {
        field.name: getattr(identity_lesson, field.name)
        for field in fields(identity_lesson)}
    fake_lesson_fields.update({
        "semantic_id": "urn:invented:NOT-SOURCE",
        "positive_fact": (
            "identity", "urn:invented:NOT-SOURCE", "source:fake")})
    evil_lesson = EqAnyLesson(**fake_lesson_fields)
    with test.assertRaises(BilqisError) as evil_checker:
        public_curriculum.check_source_constructive_lesson(
            evil_lesson, "urn:invented:NOT-SOURCE", pin)
    test.assertEqual(
        evil_checker.exception.context["reason"],
        "BAMF_LESSON_CHECKER_INPUT_INVALID")
    for replacement in (
            ("legacy:cogal.operator.OR",),
            ("legacy:cogal.operator.OR", "legacy:cogal.operator.XOR")):
        with test.subTest(repacked_formal=replacement):
            trial_root = Path(directory) / (
                "repacked-" + str(len(replacement)))
            trial_root.mkdir()
            copy = trial_root / artifact.bundle_id
            shutil.copytree(artifact.path, copy)
            atlas_record = json.loads((copy / "atlas.json").read_bytes())
            atlas_record["formal_domain_bindings"][0]["semantic_ids"] = (
                list(replacement))
            atlas_bytes = json_bytes(atlas_record)
            (copy / "atlas.json").write_bytes(atlas_bytes)
            manifest = json.loads((copy / "manifest.json").read_bytes())
            manifest["files"]["atlas.json"] = {
                "sha256": hashlib.sha256(atlas_bytes).hexdigest(),
                "bytes": len(atlas_bytes)}
            manifest_bytes = json_bytes(manifest)
            (copy / "manifest.json").write_bytes(manifest_bytes)
            repacked = trial_root / hashlib.sha256(
                manifest_bytes).hexdigest()
            copy.rename(repacked)
            with test.assertRaises(BilqisError) as self_attested:
                public_curriculum.inventory_source_families(
                    AtlasArtifactSelection(
                        str(repacked), repacked.name, release.digest,
                        release.source_bundle_id))
            test.assertEqual(
                self_attested.exception.context["reason"],
                "ATLAS_SOURCE_PIN_NOT_REGISTERED")
            with test.assertRaises(BilqisError) as replaced_pin:
                public_curriculum.inventory_source_families(
                    replace(pin, path=str(repacked),
                            bundle_id=repacked.name))
            test.assertEqual(
                replaced_pin.exception.context["reason"],
                "ATLAS_SOURCE_PIN_NOT_REGISTERED")
    other_boolean = tuple(
        entry.semantic_id for entry in snapshot.abi_entries
        if entry.semantic_id.startswith("legacy:cogal.operator.")
        and entry.semantic_id not in
        snapshot.formal_domain_bindings[0].semantic_ids)
    for replacement in (
            other_boolean[:1],
            other_boolean[:len(snapshot.formal_domain_bindings[0].semantic_ids)]):
        if not replacement:
            continue
        with test.subTest(formal_binding_substitution=replacement):
            forged = replace(
                snapshot, formal_domain_bindings=(
                    replace(snapshot.formal_domain_bindings[0],
                            semantic_ids=replacement),
                    *snapshot.formal_domain_bindings[1:]))
            # An internal pure projection can represent this forged
            # snapshot, but the public consumer must replay pinned A01.
            forged_inventory = inventory_source_families(forged)
            test.assertNotEqual(
                forged_inventory.digest, public_census.digest)
            with test.assertRaises(BilqisError) as rejected:
                public_curriculum.assert_family_inventory_current(
                    forged_inventory, pin)
            test.assertEqual(
                rejected.exception.context["reason"],
                "BAMF_FAMILY_SOURCE_PROJECTION_DRIFT")
