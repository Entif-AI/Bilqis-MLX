import csv
import unittest

from rdflib import URIRef
from rdflib.namespace import SKOS

from lib.ithkuil.src.skos.mapping import MappingClaim, decide_mapping, project_mappings

from lib.ithkuil.tests.skos.mapping.test_skos_mapping import (
    CORPUS_ROOT,
    FIXTURE,
    MappingContractSupport,
)


class MappingConflictContractTests(MappingContractSupport, unittest.TestCase):
    def test_broad_and_reversed_narrow_are_same_admitted_relation(self):
            row = next(row for row in FIXTURE["positive_claims"] if row["id"] == "broad")
            broad = self.claim(row)
            inverse = MappingClaim(
                source_iri=broad.target_iri,
                target_iri=broad.source_iri,
                source_scheme_iri=broad.target_scheme_iri,
                target_scheme_iri=broad.source_scheme_iri,
                predicate="narrowMatch",
                review_state="admitted_narrow_match",
                source_ref="SYNTHETIC:INVERSE",
                evidence_ref="SYNTHETIC:EVIDENCE:INVERSE",
                independent_schemes=True,
                direction_ref="SYNTHETIC:DIRECTION:INVERSE",
            )
            graph, decisions = project_mappings([broad, inverse])
            self.assertEqual(len(decisions), 2)
            self.assertEqual(
                set(graph),
                {
                    (URIRef(broad.source_iri), SKOS.broadMatch, URIRef(broad.target_iri)),
                    (URIRef(broad.target_iri), SKOS.narrowMatch, URIRef(broad.source_iri)),
                },
            )
    def test_conflicting_admitted_predicates_fail_even_when_pair_is_reversed(self):
            exact_row = next(row for row in FIXTURE["positive_claims"] if row["id"] == "exact")
            exact = self.claim(exact_row)
            related_reversed = MappingClaim(
                source_iri=exact.target_iri,
                target_iri=exact.source_iri,
                source_scheme_iri=exact.target_scheme_iri,
                target_scheme_iri=exact.source_scheme_iri,
                predicate="relatedMatch",
                review_state="admitted_related_match",
                source_ref="SYNTHETIC:CONFLICT",
                evidence_ref="SYNTHETIC:EVIDENCE:CONFLICT",
                independent_schemes=True,
            )
            error = self.assert_code(
                "CONFLICTING_MAPPING_PREDICATES",
                project_mappings,
                [exact, related_reversed],
            )
            self.assertIn(exact.source_iri, error.details)
            self.assertIn(exact.target_iri, error.details)

            broad_row = next(row for row in FIXTURE["positive_claims"] if row["id"] == "broad")
            broad = self.claim(broad_row)
            reciprocal = MappingClaim(
                source_iri=broad.target_iri,
                target_iri=broad.source_iri,
                source_scheme_iri=broad.target_scheme_iri,
                target_scheme_iri=broad.source_scheme_iri,
                predicate="broadMatch",
                review_state="admitted_broad_match",
                source_ref="SYNTHETIC:RECIPROCAL",
                evidence_ref="SYNTHETIC:EVIDENCE:RECIPROCAL",
                independent_schemes=True,
                direction_ref="SYNTHETIC:DIRECTION:RECIPROCAL",
            )
            graph, decisions = project_mappings([broad, reciprocal])
            self.assertEqual(len(decisions), 2)
            self.assertEqual(set(graph), {
                (URIRef(broad.source_iri), SKOS.broadMatch, URIRef(broad.target_iri)),
                (URIRef(broad.target_iri), SKOS.narrowMatch, URIRef(broad.source_iri)),
                (URIRef(broad.target_iri), SKOS.broadMatch, URIRef(broad.source_iri)),
                (URIRef(broad.source_iri), SKOS.narrowMatch, URIRef(broad.target_iri)),
            })
    def test_source_evidence_and_independent_scheme_disposition_are_required(self):
            row = next(row for row in FIXTURE["positive_claims"] if row["id"] == "related")
            for field, code in (
                ("source_ref", "MAPPING_SOURCE_REF_REQUIRED"),
                ("evidence_ref", "MAPPING_EVIDENCE_REF_REQUIRED"),
            ):
                with self.subTest(field=field):
                    self.assert_code(code, self.claim, row, **{field: ""})

            self.assert_code(
                "MAPPING_SCHEME_DISPOSITION_REQUIRED",
                self.claim,
                row,
                independent_schemes=None,
            )

            not_independent = decide_mapping(
                self.claim(row, independent_schemes=False)
            )
            self.assertEqual(
                not_independent.reason_code,
                "MAPPING_NOT_INDEPENDENT_SCHEMES",
            )

            same_scheme = decide_mapping(
                self.claim(
                    row,
                    target_scheme_iri=FIXTURE["schemes"]["a"],
                    source_ref="SOURCE-DOC-A",
                    evidence_ref="SOURCE-DOC-B",
                )
            )
            self.assertEqual(same_scheme.reason_code, "MAPPING_SAME_SCHEME_HELD")
    def test_mapping_never_collapses_independently_governed_identity(self):
            row = next(row for row in FIXTURE["positive_claims"] if row["id"] == "related")
            self.assert_code(
                "MAPPING_SELF_RELATION_FORBIDDEN",
                decide_mapping,
                self.claim(row, target_iri=row["source_iri"]),
            )
    def test_unknown_predicate_fails_closed(self):
            row = next(row for row in FIXTURE["positive_claims"] if row["id"] == "related")
            self.assert_code(
                "UNKNOWN_MAPPING_PREDICATE",
                decide_mapping,
                self.claim(row, predicate="sameAs"),
            )
    def test_current_raw_crosswalk_has_no_concept_target_equivalences(self):
            data = CORPUS_ROOT / "_data/csv"
            with (data / "bilqis_ithkuil_crosswalk.csv").open(
                newline="", encoding="utf-8"
            ) as handle:
                crosswalk = list(csv.DictReader(handle))
            with (data / "bilqis_semantic_bridges.csv").open(
                newline="", encoding="utf-8"
            ) as handle:
                bridges = list(csv.DictReader(handle))

            self.assertEqual(
                {row["target_kind"] for row in crosswalk},
                {"source_document", "source_section"},
            )
            self.assertEqual(
                {row["target_kind"] for row in bridges},
                {"source_document", "source_section", "historical_source"},
            )
            self.assertNotIn(
                "admitted_exact_equivalence",
                {row["equivalence_state"] for row in crosswalk},
            )
            self.assertTrue(FIXTURE["synthetic"])

if __name__ == "__main__":
    unittest.main()
