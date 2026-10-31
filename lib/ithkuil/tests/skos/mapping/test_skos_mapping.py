from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
from dataclasses import FrozenInstanceError
import json
import unittest

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, SKOS

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.mapping import (
    ADMITTED_STATE_BY_PREDICATE,
    MappingClaim,
    project_mappings,
)


FIXTURE_ROOT = FIXTURES
CORPUS_ROOT = ITHKUIL_ROOT
FIXTURE = json.loads(
    (FIXTURE_ROOT / "skos_mapping_admission.json").read_text(encoding="utf-8")
)

class MappingContractSupport:
    def assert_code(self, code, callable_, *args, **kwargs):
            with self.assertRaises(ProfileError) as caught:
                callable_(*args, **kwargs)
            self.assertEqual(caught.exception.code, code)
            return caught.exception
    def claim(self, row, **changes):
            data = {
                "source_iri": row["source_iri"],
                "target_iri": row["target_iri"],
                "source_scheme_iri": FIXTURE["schemes"]["a"],
                "target_scheme_iri": FIXTURE["schemes"]["b"],
                "predicate": row["predicate"],
                "review_state": row["review_state"],
                "source_ref": row["source_ref"],
                "evidence_ref": row["evidence_ref"],
                "independent_schemes": row["independent_schemes"],
                "exactness_proof_ref": row.get("exactness_proof_ref"),
                "qualification_ref": row.get("qualification_ref"),
                "direction_ref": row.get("direction_ref"),
            }
            data.update(changes)
            return MappingClaim(**data)
    def positives(self):
            return [self.claim(row) for row in FIXTURE["positive_claims"]]


class MappingContractTests(MappingContractSupport, unittest.TestCase):
    def test_machine_readable_matrix_covers_all_five_predicates(self):
            matrix = FIXTURE["matrix"]
            self.assertEqual(set(matrix), set(ADMITTED_STATE_BY_PREDICATE))
            for predicate, state in ADMITTED_STATE_BY_PREDICATE.items():
                self.assertEqual(matrix[predicate]["review_state"], state)
                self.assertFalse(matrix[predicate]["historical_emission"])
                self.assertTrue(matrix[predicate]["insufficient"])
            self.assertTrue(matrix["exactMatch"]["symmetry"])
            self.assertTrue(matrix["closeMatch"]["symmetry"])
            self.assertTrue(matrix["relatedMatch"]["symmetry"])
            self.assertEqual(matrix["broadMatch"]["inverse"], "narrowMatch")
            self.assertEqual(matrix["narrowMatch"]["inverse"], "broadMatch")
            self.assertEqual({name: row["transitive"] for name, row in matrix.items()}, {
                "exactMatch": True, "closeMatch": False, "broadMatch": False,
                "narrowMatch": False, "relatedMatch": False,
            })
            self.assertEqual(matrix["exactMatch"]["subproperty_of"], "closeMatch")
    def test_records_are_frozen_and_projection_is_input_order_invariant(self):
            claims = self.positives()
            first = claims[0]
            with self.assertRaises(FrozenInstanceError):
                first.predicate = "relatedMatch"

            forward_graph, forward_decisions = project_mappings(claims)
            reverse_graph, reverse_decisions = project_mappings(reversed(claims))
            self.assertEqual(set(forward_graph), set(reverse_graph))
            self.assertEqual(forward_decisions, reverse_decisions)
    def test_synthetic_positive_fixture_matches_literal_expected_rdf(self):
            graph, decisions = project_mappings(self.positives())
            self.assertTrue(all(decision.emitted for decision in decisions))

            expected = {
                (URIRef(source), URIRef(predicate), URIRef(target))
                for source, predicate, target in FIXTURE["expected_triples"]
            }
            self.assertEqual(set(graph), expected)

            fixture_graph = Graph().parse(
                FIXTURE_ROOT / "skos_mapping_positive.ttl",
                format="turtle",
            )
            self.assertEqual(set(graph), set(fixture_graph))

            reparsed = Graph().parse(data=graph.serialize(format="nt"), format="nt")
            self.assertEqual(set(reparsed), expected)
            self.assertFalse(any(predicate == OWL.sameAs for _, predicate, _ in graph))
    def test_symmetric_and_directional_inverse_semantics_are_explicit(self):
            by_id = {row["id"]: row for row in FIXTURE["positive_claims"]}
            exact = self.claim(by_id["exact"])
            close = self.claim(by_id["close"])
            related = self.claim(by_id["related"])
            broad = self.claim(by_id["broad"])
            narrow = self.claim(by_id["narrow"])
            graph, _ = project_mappings([exact, close, related, broad, narrow])

            for claim, predicate in (
                (exact, SKOS.exactMatch),
                (close, SKOS.closeMatch),
                (related, SKOS.relatedMatch),
            ):
                self.assertIn((URIRef(claim.source_iri), predicate, URIRef(claim.target_iri)), graph)
                self.assertIn((URIRef(claim.target_iri), predicate, URIRef(claim.source_iri)), graph)

            self.assertIn(
                (URIRef(broad.source_iri), SKOS.broadMatch, URIRef(broad.target_iri)),
                graph,
            )
            self.assertIn(
                (URIRef(broad.target_iri), SKOS.narrowMatch, URIRef(broad.source_iri)),
                graph,
            )
            self.assertIn(
                (URIRef(narrow.source_iri), SKOS.narrowMatch, URIRef(narrow.target_iri)),
                graph,
            )
            self.assertIn(
                (URIRef(narrow.target_iri), SKOS.broadMatch, URIRef(narrow.source_iri)),
                graph,
            )


if __name__ == "__main__":
    unittest.main()
