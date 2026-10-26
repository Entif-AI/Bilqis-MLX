from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from rdflib import Graph

import lib.ithkuil.src.skos as _skos
BASE_SKOS = Path(next(iter(_skos.__path__))).resolve()
STAGED = Path(__file__).resolve().parents[1] / "src" / "skos"
VERIFY = Path(__file__).resolve().parents[3] / "_verify" / "lib" / "ithkuil" / "src" / "skos"
CORRECTED = Path(__file__).resolve().parents[3] / "upstream-correction" / "lib" / "ithkuil" / "src" / "skos"
_skos.__path__.insert(0, str(STAGED))
if CORRECTED.exists():
    _skos.__path__.insert(1, str(CORRECTED))
if VERIFY.exists():
    _skos.__path__.insert(2, str(VERIFY))

from lib.ithkuil.src.skos.affix_degree import project_affix_degrees
from lib.ithkuil.src.skos.allomorph_rule import project_allomorph_rules
from lib.ithkuil.src.skos.composition import load_composition_profile, project_compositions
from lib.ithkuil.src.skos.composition_components import project_composition_components
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.extension_vocabulary import load_extension_vocabulary, validate_graph_vocabulary
from lib.ithkuil.src.skos.lexicon_dimensions import project_lexicon_dimensions
from lib.ithkuil.src.skos.lexicon_links import load_root_sense_term, project_root_sense_links
from lib.ithkuil.src.skos.preflight import preflight


LIB = BASE_SKOS.parents[1]
DATA = LIB / "_data" / "csv"
VOCAB = STAGED / "extension_vocabulary.json"
VERIFY_ITHKUIL = VERIFY.parents[1] if VERIFY.exists() else LIB
COMPOSITION_PROFILE = (VERIFY if VERIFY.exists() else BASE_SKOS) / "composition_profile.json"
COMPOSITION_NEGATIVE = VERIFY_ITHKUIL / "tests" / "fixtures" / "skos_composition_negative.ttl"
ROOT_SENSE_PROFILE = (VERIFY if VERIFY.exists() else BASE_SKOS) / "root_sense_extension.json"
ROOT_SENSE_NEGATIVE = VERIFY_ITHKUIL / "tests" / "fixtures" / "skos_root_sense_negative.ttl"


def csv_rows(name: str):
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class ExtensionVocabularyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure = preflight(DATA).require_valid()
        cls.vocabulary = load_extension_vocabulary(VOCAB, DATA)

    def test_exact_normative_term_set_and_rejections(self):
        self.assertEqual(self.vocabulary.admitted_keys, frozenset({
            "lexiconStem", "lexiconSpecification", "hasSense", "degreeOf",
            "surfacePattern", "condition", "componentCount", "componentRole", "slotLabel",
            "inputPattern", "intermediatePattern", "outputPattern", "allomorphDomain",
        }))
        rejected = {item.key for item in self.vocabulary.reviewed_not_admitted}
        self.assertEqual(rejected, {"sourceLocusKind", "componentPosition", "degreeNumber", "surfaceReplacement"})

    def test_every_admitted_term_is_bound_to_one_real_source_fixture(self):
        self.assertEqual(len(self.vocabulary.terms), 13)
        for term in self.vocabulary.terms:
            self.assertTrue(term.source_fixture)
            self.assertTrue(term.source_fields)
            self.assertTrue(term.rejected_alternatives)
            self.assertIsNone(term.subproperty_of)

    def test_actual_residue_graphs_use_only_admitted_terms(self):
        composition_profile = load_composition_profile(
            COMPOSITION_PROFILE, self.closure, COMPOSITION_NEGATIVE
        )
        compositions = project_compositions(self.closure, composition_profile)
        degrees = project_affix_degrees(self.closure, csv_rows("affix_degrees.csv"))
        components = project_composition_components(
            self.closure, csv_rows("composition_components.csv"), compositions
        )
        rules = project_allomorph_rules(self.closure, csv_rows("allomorph_rules.csv"))
        graph = Graph()
        for source in (degrees.graph, compositions.graph, components.graph, rules.graph):
            for triple in source:
                graph.add(triple)
        used = validate_graph_vocabulary(graph, self.vocabulary)
        self.assertEqual({iri.rsplit("/", 1)[-1] for iri in used}, {
            "degreeOf", "surfacePattern", "condition", "componentCount",
            "componentRole", "slotLabel", "inputPattern", "intermediatePattern",
            "outputPattern", "allomorphDomain",
        })

    def test_lexicon_semantic_terms_are_admitted_and_source_mode_stays_record_only(self):
        dimensions = project_lexicon_dimensions(self.closure)
        self.assertEqual(
            {iri.rsplit("/", 1)[-1] for iri in validate_graph_vocabulary(dimensions.graph, self.vocabulary)},
            {"lexiconStem", "lexiconSpecification"},
        )
        self.assertEqual(
            {mode for record in dimensions.records for mode in record.source_locus_kinds},
            {"table", "prose", "compact_numbered_stem"},
        )
        self.assertFalse(any(str(predicate).endswith("/sourceLocusKind")
                             for _, predicate, _ in dimensions.graph))

        term = load_root_sense_term(
            ROOT_SENSE_PROFILE, source_csv_root=DATA, negative_fixture_path=ROOT_SENSE_NEGATIVE
        )
        links = project_root_sense_links(self.closure, term)
        self.assertEqual(
            {iri.rsplit("/", 1)[-1] for iri in validate_graph_vocabulary(links.graph, self.vocabulary)},
            {"hasSense"},
        )

    def test_unregistered_vocab_predicate_fails_closed(self):
        graph = Graph()
        from rdflib import URIRef, Literal
        graph.add((URIRef("urn:s"), URIRef("https://github.com/Entif-AI/Bilqis-MLX/vocab/notAdmitted"), Literal("x")))
        with self.assertRaises(ProfileError) as caught:
            validate_graph_vocabulary(graph, self.vocabulary)
        self.assertEqual(caught.exception.code, "UNADMITTED_EXTENSION_TERM")

    def test_source_fixture_lookup_cannot_escape_the_declared_public_csv_root(self):
        for table in ("../outside.csv", "/tmp/outside.csv"):
            value = json.loads(VOCAB.read_text())
            value["admitted_terms"][0]["source_table"] = table
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "vocabulary.json"
                path.write_text(json.dumps(value))
                with self.assertRaises(ProfileError) as caught:
                    load_extension_vocabulary(path, DATA)
                self.assertEqual(caught.exception.code, "EXTENSION_VOCAB_SOURCE_PATH_INVALID")

    def test_duplicate_rejection_and_boolean_issue_owner_do_not_pass_registry_validation(self):
        for change, code in (
            ("duplicate-rejection", "EXTENSION_VOCAB_REJECTION_INVALID"),
            ("boolean-owner", "EXTENSION_VOCAB_TERM_INVALID"),
        ):
            value = json.loads(VOCAB.read_text())
            if change == "duplicate-rejection":
                value["reviewed_not_admitted"].append(dict(value["reviewed_not_admitted"][0]))
            else:
                value["admitted_terms"][0]["owner_issues"] = [True]
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "vocabulary.json"
                path.write_text(json.dumps(value))
                with self.assertRaises(ProfileError) as caught:
                    load_extension_vocabulary(path, DATA)
                self.assertEqual(caught.exception.code, code)


if __name__ == "__main__":
    unittest.main()
