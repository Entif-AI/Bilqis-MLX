import unittest

from lib.ithkuil.src.skos.mapping import (
    HELD_REASON_BY_STATE,
    decide_mapping,
    project_mappings,
)

from lib.ithkuil.tests.skos.mapping.test_skos_mapping import (
    FIXTURE,
    MappingContractSupport,
)


class MappingAdmissionContractTests(MappingContractSupport, unittest.TestCase):
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

if __name__ == "__main__":
    unittest.main()
