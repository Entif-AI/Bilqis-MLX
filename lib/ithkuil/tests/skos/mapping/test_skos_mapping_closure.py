import itertools
from dataclasses import replace
import unittest

from rdflib import URIRef
from rdflib.namespace import SKOS

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.mapping import MappingClaim, project_mappings


def claim(source, predicate, target):
    states = {"exactMatch": "admitted_exact_equivalence", "closeMatch": "admitted_close_match",
              "broadMatch": "admitted_broad_match", "narrowMatch": "admitted_narrow_match",
              "relatedMatch": "admitted_related_match"}
    return MappingClaim("urn:concept:" + source, "urn:concept:" + target,
                        "urn:scheme:" + source, "urn:scheme:" + target,
                        predicate, states[predicate], "SYNTHETIC:SOURCE", "SYNTHETIC:REVIEW",
                        True, "SYNTHETIC:EXACT", "SYNTHETIC:CLOSE", "SYNTHETIC:DIRECTION")


class MappingClosureTests(unittest.TestCase):
    def test_exact_chain_clashes_with_explicit_hierarchy_or_association(self):
        for predicate in ("broadMatch", "narrowMatch", "relatedMatch"):
            rows = [claim("A", "exactMatch", "B"), claim("B", "exactMatch", "C"),
                    claim("A", predicate, "C")]
            messages = set()
            for order in itertools.permutations(rows):
                with self.assertRaises(ProfileError) as caught:
                    project_mappings(order)
                self.assertEqual(caught.exception.code, "ENTAILED_MAPPING_CONFLICT")
                self.assertIn("EXACT_MATCH_TRANSITIVE_CLASH", caught.exception.details)
                messages.add(str(caught.exception))
            self.assertEqual(len(messages), 1)

    def test_broader_transitive_path_clashes_with_related_in_either_direction(self):
        for source, target in (("A", "C"), ("C", "A")):
            with self.assertRaises(ProfileError) as caught:
                project_mappings([claim("A", "broadMatch", "B"), claim("C", "narrowMatch", "B"),
                                  claim(source, "relatedMatch", target)])
            self.assertEqual(caught.exception.code, "ENTAILED_MAPPING_CONFLICT")
            self.assertIn("HIERARCHY_RELATED_CLASH", caught.exception.details)

    def test_exact_and_explicit_close_coexist_without_collapsing_identity(self):
        graph, _ = project_mappings([claim("A", "exactMatch", "B"), claim("A", "closeMatch", "B")])
        self.assertEqual(set(graph), {
            (URIRef("urn:concept:A"), SKOS.exactMatch, URIRef("urn:concept:B")),
            (URIRef("urn:concept:B"), SKOS.exactMatch, URIRef("urn:concept:A")),
            (URIRef("urn:concept:A"), SKOS.closeMatch, URIRef("urn:concept:B")),
            (URIRef("urn:concept:B"), SKOS.closeMatch, URIRef("urn:concept:A")),
        })

    def test_close_chains_do_not_acquire_exactness_or_other_mapping_semantics(self):
        graph, _ = project_mappings([claim("A", "closeMatch", "B"), claim("B", "closeMatch", "C"),
                                    claim("A", "relatedMatch", "C")])
        self.assertEqual(len(graph), 6)
        self.assertNotIn((URIRef("urn:concept:A"), SKOS.closeMatch, URIRef("urn:concept:C")), graph)
        self.assertEqual(list(graph.triples((None, SKOS.exactMatch, None))), [])

    def test_no_cross_property_substitution_through_exact_links(self):
        # SKOS has no exactMatch/broadMatch property-chain substitution axiom.
        graph, _ = project_mappings([claim("A", "exactMatch", "B"), claim("B", "broadMatch", "C"),
                                    claim("A", "relatedMatch", "C")])
        self.assertEqual(len(graph), 6)
        self.assertNotIn((URIRef("urn:concept:A"), SKOS.broadMatch, URIRef("urn:concept:C")), graph)

    def test_valid_exact_chain_is_checked_without_materializing_inferred_assertions(self):
        graph, _ = project_mappings([claim("A", "exactMatch", "B"), claim("B", "exactMatch", "C")])
        self.assertEqual(len(graph), 4)
        self.assertNotIn((URIRef("urn:concept:A"), SKOS.exactMatch, URIRef("urn:concept:C")), graph)

    def test_multiple_invalid_reviews_report_deterministically_under_reordering(self):
        rows = [replace(claim("A", "exactMatch", "B"), review_state="unknown-z"),
                replace(claim("B", "exactMatch", "C"), review_state="unknown-a")]
        errors = set()
        for order in itertools.permutations(rows):
            with self.assertRaises(ProfileError) as caught:
                project_mappings(order)
            self.assertEqual(caught.exception.code, "UNSUPPORTED_MAPPING_REVIEW_STATE")
            self.assertEqual(caught.exception.details, ("unknown-a",))
            errors.add(str(caught.exception))
        self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
