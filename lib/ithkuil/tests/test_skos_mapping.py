import csv
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import unittest

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, SKOS

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.mapping import (
    ADMITTED_STATE_BY_PREDICATE,
    HELD_REASON_BY_STATE,
    MappingClaim,
    decide_mapping,
    project_mappings,
)


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
CORPUS_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads(
    (FIXTURE_ROOT / "skos_mapping_admission.json").read_text(encoding="utf-8")
)


class MappingContractTests(unittest.TestCase):
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

    def test_every_negative_review_state_is_held_without_rdf(self):
        template = FIXTURE["positive_claims"][-1]
        for state, reason in FIXTURE["held_states"].items():
            with self.subTest(state=state):
                claim = self.claim(template, review_state=state)
                decision = decide_mapping(claim)
                self.assertFalse(decision.emitted)
                self.assertEqual(decision.reason_code, reason)
                graph, decisions = project_mappings([claim])
                self.assertEqual(len(graph), 0)
                self.assertEqual(decisions, (decision,))
                self.assertEqual(reason, HELD_REASON_BY_STATE[state])

    def test_unknown_and_raw_adapter_states_fail_closed(self):
        template = FIXTURE["positive_claims"][-1]
        for state in (
            "future_mapping_state",
            "formal_adapter",
            "APPROVED_TYPED_FORMAL_ADAPTER",
            "qualified_relation",
        ):
            with self.subTest(state=state):
                self.assert_code(
                    "UNSUPPORTED_MAPPING_REVIEW_STATE",
                    decide_mapping,
                    self.claim(template, review_state=state),
                )

    def test_exact_match_requires_explicit_equivalence_proof(self):
        row = next(row for row in FIXTURE["positive_claims"] if row["id"] == "exact")
        self.assert_code(
            "EXACT_MATCH_PROOF_REQUIRED",
            decide_mapping,
            self.claim(row, exactness_proof_ref=None),
        )
        self.assert_code(
            "EXACT_MATCH_PROOF_REQUIRED",
            decide_mapping,
            self.claim(row, exactness_proof_ref=""),
        )
        self.assert_code(
            "MAPPING_STATE_PREDICATE_MISMATCH",
            decide_mapping,
            self.claim(
                row,
                predicate="closeMatch",
                qualification_ref="SYNTHETIC:QUALIFICATION",
            ),
        )

    def test_close_match_is_separately_qualified_not_exactness_uncertainty(self):
        row = next(row for row in FIXTURE["positive_claims"] if row["id"] == "close")
        self.assert_code(
            "CLOSE_MATCH_QUALIFICATION_REQUIRED",
            decide_mapping,
            self.claim(row, qualification_ref=None),
        )
        self.assert_code(
            "MAPPING_STATE_PREDICATE_MISMATCH",
            decide_mapping,
            self.claim(
                row,
                review_state="admitted_exact_equivalence",
                exactness_proof_ref="SYNTHETIC:EXACT-PROOF",
            ),
        )
        ambiguous = decide_mapping(self.claim(row, review_state="ambiguous"))
        self.assertFalse(ambiguous.emitted)
        self.assertEqual(ambiguous.reason_code, "MAPPING_AMBIGUOUS_HELD")

    def test_broad_and_narrow_require_direction_evidence(self):
        for row in (
            row
            for row in FIXTURE["positive_claims"]
            if row["id"] in {"broad", "narrow"}
        ):
            with self.subTest(predicate=row["predicate"]):
                self.assert_code(
                    "DIRECTIONAL_MAPPING_EVIDENCE_REQUIRED",
                    decide_mapping,
                    self.claim(row, direction_ref=None),
                )

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
