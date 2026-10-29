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
            Path(__file__).resolve().parents[3]
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

    def test_real_pinned_corpus_census_if_supplied(self):
        corpus = os.environ.get("BILQIS_ATLAS_REAL_CORPUS")
        if not corpus:
            self.skipTest("set BILQIS_ATLAS_REAL_CORPUS for full pinned census")
        root = Path(__file__).resolve().parents[3]
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
        release = compile_atlas_release(
            corpus, Path(corpus) / "coverage.json", prior, bindings)
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
            # This A01 source contains no admitted SKOS relation triples.
            # Synthetic fixtures test relations; the real corpus cannot
            # manufacture them to inflate the source lesson denominator.
            self.assertFalse(any(
                item.family_id == "source_attested_relation"
                for item in public_candidate.source_lessons))
            identity_lesson = next(
                item for item in public_candidate.source_lessons
                if item.family_id == "positive_identity")
            self.assertTrue(public_curriculum.check_source_constructive_lesson(
                identity_lesson, identity_lesson.positive_fact[1], pin))
            class WrappedText(str):
                pass
            self.assertFalse(public_curriculum.check_source_constructive_lesson(
                identity_lesson, WrappedText(identity_lesson.positive_fact[1]),
                pin))
            self.assertEqual(
                public_census.source_authority, SOURCE_PROJECTION_ONLY)
            self.assertEqual(
                public_candidate.source_authority, SOURCE_PROJECTION_ONLY)
            self.assertIsNone(public_curriculum.assert_family_inventory_current(
                public_census, pin))
            self.assertIsNone(public_curriculum.assert_curriculum_candidate_current(
                public_candidate, pin,
                LearnedFrontier(snapshot.release_sha256)))
            public_lessons = public_curriculum.compile_source_constructive_lessons(
                pin)
            self.assertIsNone(public_curriculum.assert_source_lesson_set_current(
                public_lessons, pin))
            forged_census = replace(
                public_census,
                source_eligible_concept_ids=public_census.source_eligible_concept_ids[:8])
            with self.assertRaises(BilqisError) as census_drift:
                public_curriculum.assert_family_inventory_current(
                    forged_census, pin)
            self.assertEqual(
                census_drift.exception.context["reason"],
                "BAMF_FAMILY_SOURCE_PROJECTION_DRIFT")
            with self.assertRaises(BilqisError) as candidate_drift:
                public_curriculum.assert_curriculum_candidate_current(
                    replace(public_candidate, census=forged_census),
                    pin,
                    LearnedFrontier(snapshot.release_sha256))
            self.assertEqual(
                candidate_drift.exception.context["reason"],
                "BAMF_CANDIDATE_SOURCE_PROJECTION_DRIFT")
            fake_adapters = (
                SourceFamilyAdapter("invented_family", all_eligible=True),)
            with self.assertRaises(BilqisError) as adapter_drift:
                public_curriculum.compile_semantic_curriculum(
                    pin, fake_adapters,
                    LearnedFrontier(snapshot.release_sha256))
            self.assertEqual(
                adapter_drift.exception.context["reason"],
                "BAMF_FAMILY_COMPILER_INPUT_INVALID")
            with self.assertRaises(BilqisError) as lesson_drift:
                public_curriculum.assert_source_lesson_set_current(
                    replace(public_lessons, lessons=public_lessons.lessons[:8]),
                    pin)
            self.assertEqual(
                lesson_drift.exception.context["reason"],
                "BAMF_LESSON_SOURCE_PROJECTION_DRIFT")

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
                with self.subTest(equality_override=action):
                    with self.assertRaises(BilqisError):
                        action()
            fake_lesson_fields = {
                field.name: getattr(identity_lesson, field.name)
                for field in fields(identity_lesson)}
            fake_lesson_fields.update({
                "semantic_id": "urn:invented:NOT-SOURCE",
                "positive_fact": (
                    "identity", "urn:invented:NOT-SOURCE", "source:fake")})
            evil_lesson = EqAnyLesson(**fake_lesson_fields)
            with self.assertRaises(BilqisError) as evil_checker:
                public_curriculum.check_source_constructive_lesson(
                    evil_lesson, "urn:invented:NOT-SOURCE", pin)
            self.assertEqual(
                evil_checker.exception.context["reason"],
                "BAMF_LESSON_CHECKER_INPUT_INVALID")
            for replacement in (
                    ("legacy:cogal.operator.OR",),
                    ("legacy:cogal.operator.OR", "legacy:cogal.operator.XOR")):
                with self.subTest(repacked_formal=replacement):
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
                    with self.assertRaises(BilqisError) as self_attested:
                        public_curriculum.inventory_source_families(
                            AtlasArtifactSelection(
                                str(repacked), repacked.name, release.digest,
                                release.source_bundle_id))
                    self.assertEqual(
                        self_attested.exception.context["reason"],
                        "ATLAS_SOURCE_PIN_NOT_REGISTERED")
                    with self.assertRaises(BilqisError) as replaced_pin:
                        public_curriculum.inventory_source_families(
                            replace(pin, path=str(repacked),
                                    bundle_id=repacked.name))
                    self.assertEqual(
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
                with self.subTest(formal_binding_substitution=replacement):
                    forged = replace(
                        snapshot, formal_domain_bindings=(
                            replace(snapshot.formal_domain_bindings[0],
                                    semantic_ids=replacement),
                            *snapshot.formal_domain_bindings[1:]))
                    # An internal pure projection can represent this forged
                    # snapshot, but the public consumer must replay pinned A01.
                    forged_inventory = inventory_source_families(forged)
                    self.assertNotEqual(
                        forged_inventory.digest, public_census.digest)
                    with self.assertRaises(BilqisError) as rejected:
                        public_curriculum.assert_family_inventory_current(
                            forged_inventory, pin)
                    self.assertEqual(
                        rejected.exception.context["reason"],
                        "BAMF_FAMILY_SOURCE_PROJECTION_DRIFT")
        census = inventory_source_families(snapshot)
        self.assertEqual(public_census, census)
        self.assertEqual(pinned, snapshot)
        self.assertEqual(public_candidate.frozen_census_digest, census.digest)
        lexicon_root = next(
            item.concept.semantic_id for item in snapshot.concepts
            if item.concept.kind == "root")
        forged_formal = replace(
            snapshot, formal_domain_bindings=(
                replace(snapshot.formal_domain_bindings[0],
                        semantic_ids=(lexicon_root,)),
                *snapshot.formal_domain_bindings[1:]))
        with self.assertRaises(BilqisError) as caught:
            inventory_source_families(forged_formal)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_FAMILY_FORMAL_SOURCE_INVALID")
        # Frozen A01.2/A01.3 source census: formal ABI cannot disappear
        # merely because no AtlasConcept record backs its identity.
        self.assertEqual(census.counts.atlas_source_concepts, 9079)
        self.assertEqual(census.counts.formal_only_abi_identities, 228)
        self.assertEqual(census.counts.source_eligible_concepts, 9307)
        self.assertEqual(census.counts.atlas_source_concepts,
                         release.counts.semantic_concepts)
        self.assertEqual(census.counts.source_eligible_concepts,
                         release.counts.abi_entries)
        self.assertEqual(census.counts.source_held_rows,
                         release.counts.source_held)
        self.assertEqual(census.counts.source_ir_only_rows,
                         release.counts.source_ir_only)
        self.assertGreater(census.counts.source_emitted_nonconcept_rows, 0)
        self.assertIn("morphology_composition",
                      census.pending_source_family_ids)
        self.assertIn("morphology_decomposition",
                      census.pending_source_family_ids)
        self.assertEqual(len(census.source_eligible_concept_ids),
                         len(set(census.source_eligible_concept_ids)))
        self.assertGreater(census.counts.required_family_obligations,
                           census.counts.source_eligible_concepts)
        lesson_set = compile_source_constructive_lessons(snapshot, census=census)
        self.assertEqual(len(lesson_set.lessons), 9307)
        self.assertEqual(len(lesson_set.uncovered), 3044)
        self.assertEqual(lesson_set.learning_state, LEARNING_UNVERIFIED)


if __name__ == "__main__":
    unittest.main()
