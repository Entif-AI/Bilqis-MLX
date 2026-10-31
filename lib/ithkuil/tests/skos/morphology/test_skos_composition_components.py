from __future__ import annotations
from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT

import csv
from pathlib import Path
import unittest

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF

import lib.ithkuil.src.skos as _skos
BASE_SKOS = Path(next(iter(_skos.__path__))).resolve()
STAGED = ITHKUIL_ROOT / "src" / "skos"
VERIFY = REPO_ROOT / "_verify" / "lib" / "ithkuil" / "src" / "skos"
_skos.__path__.insert(0, str(STAGED))
if VERIFY.exists():
    _skos.__path__.append(str(VERIFY))

from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.composition import load_composition_profile, project_compositions
from lib.ithkuil.src.skos.composition_components import (
    COMPONENT_ROLE, SLOT_LABEL, component_iri, ordered_components, project_composition_components,
)
from lib.ithkuil.src.skos.preflight import preflight


LIB = BASE_SKOS.parents[1]
DATA = LIB / "_data" / "csv"
FIXTURES = FIXTURES
PROFILE = (VERIFY if VERIFY.exists() else BASE_SKOS) / "composition_profile.json"
NEGATIVE = (
    (VERIFY.parents[1] / "tests" / "fixtures")
    if VERIFY.exists()
    else (BASE_SKOS.parents[1] / "tests" / "fixtures")
) / "skos_composition_negative.ttl"


def rows():
    with (DATA / "composition_components.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class CompositionComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure = preflight(DATA).require_valid()
        cls.profile = load_composition_profile(PROFILE, cls.closure, NEGATIVE)
        cls.parents = project_compositions(cls.closure, cls.profile)
        cls.rows = rows()
        cls.result = project_composition_components(cls.closure, cls.rows, cls.parents)

    def test_current_component_corpus_is_fully_accounted(self):
        self.assertEqual(len(self.rows), 3855)
        self.assertEqual(len(self.result.records), 3855)
        self.assertEqual(len(self.result.emitted_ids), 3855)
        self.assertEqual(self.result.held_ids, ())
        self.assertEqual(self.result.issues, ())

    def test_standard_formative_reconstructs_literal_nine_component_sequence(self):
        selected = ordered_components(self.result.records, "COMP-db595ab9beac42")
        self.assertEqual([record.position for record in selected], list(range(1, 10)))
        self.assertEqual([record.literal for record in selected], [
            "C_C V_V", "C_R", "V_R", "C_S V_X ...", "C_A", "V_X C_S ...",
            "V_N C_N", "V_C / V_K", "stress",
        ])
        self.assertTrue(all(not record.atomic_id for record in selected))

    def test_atomic_components_preserve_source_id_and_resolved_semantic_reference(self):
        selected = ordered_components(self.result.records, "COMP-0060583f4d9807")
        self.assertEqual([record.position for record in selected], [1, 2])
        self.assertEqual([record.atomic_id for record in selected],
                         ["ATOM-109428d5140ef9", "ATOM-7c73d550bffdc5"])
        for record in selected:
            subject = URIRef(record.iri)
            self.assertIn((subject, RDF.value, Literal(record.atomic_id)), self.result.graph)
            self.assertIn((subject, DCTERMS.references, URIRef(record.atomic_identity.iri)), self.result.graph)

    def test_rdf_container_membership_roundtrips_exact_source_position(self):
        parent = URIRef("https://github.com/Entif-AI/Bilqis-MLX/id/composition/COMP-044604fe8e62d7")
        selected = ordered_components(self.result.records, "COMP-044604fe8e62d7")
        for record in selected:
            predicate = URIRef(str(RDF) + "_" + str(record.position))
            self.assertIn((parent, predicate, URIRef(record.iri)), self.result.graph)
        self.assertFalse(any("curriculum" in str(predicate).lower() for _, predicate, _ in self.result.graph))

    def test_group_validation_holds_all_components_on_count_position_or_value_failure(self):
        base = [dict(row) for row in self.rows]
        cases = []
        missing = [row for row in base if row["component_id"] != "CC-88d06c223b2f4a"]
        cases.append((missing, "COMPONENT_COUNT_MISMATCH", "COMP-044604fe8e62d7"))
        duplicate = [dict(row) for row in base]
        next(row for row in duplicate if row["component_id"] == "CC-8a2f8234fc13dc")["position_in_form"] = "1"
        cases.append((duplicate, "DUPLICATE_COMPONENT_POSITION", "COMP-044604fe8e62d7"))
        invalid = [dict(row) for row in base]
        target = next(row for row in invalid if row["component_id"] == "CC-39a9d514203027")
        target["literal_form_or_symbol"] = "also-set"
        cases.append((invalid, "INVALID_COMPONENT_VALUE_KIND", "COMP-0060583f4d9807"))
        for changed, code, parent_id in cases:
            with self.subTest(code=code):
                result = project_composition_components(self.closure, changed, self.parents)
                expected = {row["component_id"] for row in changed if row["composition_id"] == parent_id}
                self.assertTrue(expected <= set(result.held_ids))
                self.assertTrue(any(issue.code == code for issue in result.issues))

    def test_unknown_atomic_id_holds_parent_group(self):
        changed = [dict(row) for row in self.rows]
        target = next(row for row in changed if row["component_id"] == "CC-39a9d514203027")
        target["atomic_id"] = "ATOM-not-real"
        result = project_composition_components(self.closure, changed, self.parents)
        self.assertTrue(any(issue.code == "COMPONENT_ATOMIC_ID_NOT_RESOLVED" for issue in result.issues))
        self.assertEqual(len([value for value in result.held_ids if value in {
            "CC-39a9d514203027", "CC-f3698d202266a8"
        }]), 2)

    def test_missing_entire_component_group_fails_with_its_parent_identity(self):
        parent_id = "COMP-0060583f4d9807"
        without_group = [row for row in self.rows if row["composition_id"] != parent_id]
        for changed in (without_group, []):
            with self.subTest(remaining_rows=len(changed)):
                with self.assertRaises(ProfileError) as caught:
                    project_composition_components(self.closure, changed, self.parents)
                self.assertEqual(caught.exception.code, "COMPONENT_GROUP_MISSING")
                self.assertIn(parent_id, caught.exception.details)

    def test_row_reorder_is_canonically_invariant(self):
        other = project_composition_components(self.closure, reversed(self.rows), self.parents)
        self.assertEqual(canonicalize(other.graph), canonicalize(self.result.graph))
        self.assertEqual(other.records, self.result.records)

    def test_component_identity_cannot_repeat_across_different_parents(self):
        changed = [dict(row) for row in self.rows]
        first = changed[0]
        other = next(row for row in changed if row["composition_id"] != first["composition_id"])
        other["component_id"] = first["component_id"]
        with self.assertRaises(ProfileError) as caught:
            project_composition_components(self.closure, changed, self.parents)
        self.assertEqual(caught.exception.code, "DUPLICATE_COMPOSITION_COMPONENT_SOURCE_ID")
        self.assertEqual(caught.exception.details, (first["component_id"],))
        first["component_id"] = ""
        with self.assertRaises(ProfileError) as caught:
            project_composition_components(self.closure, changed, self.parents)
        self.assertEqual(caught.exception.code, "COMPOSITION_COMPONENT_SOURCE_ID_REQUIRED")

    def test_literal_mixed_component_fixture_is_exact(self):
        expected = Graph().parse(FIXTURES / "skos_composition_components_expected.nt", format="nt")
        actual = Graph()
        for parent_id in ("COMP-0060583f4d9807", "COMP-044604fe8e62d7"):
            for record in ordered_components(self.result.records, parent_id):
                subject = URIRef(record.iri)
                for triple in self.result.graph.triples((subject, None, None)):
                    actual.add(triple)
            parent = URIRef("https://github.com/Entif-AI/Bilqis-MLX/id/composition/" + parent_id)
            for triple in self.result.graph.triples((parent, None, None)):
                actual.add(triple)
        self.assertEqual(canonicalize(actual), canonicalize(expected))


if __name__ == "__main__":
    unittest.main()
