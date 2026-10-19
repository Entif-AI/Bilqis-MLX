"""Consumer witnesses enforce every finite AST path without granting admission."""
from dataclasses import replace
import unittest

from bilqis_mlx.curriculum_contracts import (ConstructionFamily, FamilyDisposition,
    FamilyObligation, LeafDomainBinding)
from bilqis_mlx.semantics.catalog import Catalog, SemanticCatalog, SemanticToken
from bilqis_mlx.semantics.core import Operation, Signature, TypedError, literal
from bilqis_mlx.semantics.domains import AnswerContract, AnswerMode, contract_digest
from bilqis_mlx.semantics.functions import curry
from bilqis_mlx.semantics.laws import LawCandidate
from bilqis_mlx.verification.construction_contracts import verify_domain_witness, verify_transformation_family
from bilqis_mlx.verification.outcomes import LawCheckStatus
from tests.support.contract_fixtures import BooleanBackend, SOURCE, construction, domain


class ConstructionWitnessTests(unittest.TestCase):
    def setUp(self):
        _, self.template, self.contract = construction()
        self.operation = self.template.operation
        self.catalog = Catalog((self.operation,))
        self.source, self.independent = BooleanBackend("source-fixture"), BooleanBackend("separate-fixture")
        self.expression = curry(self.operation)(literal(False, "Boolean"))

    def witness(self, expression=None, contract=None, **kwargs):
        contract = contract or self.contract
        return verify_domain_witness(expression or self.expression, contract=contract,
            expected_contract_sha256=contract_digest(contract), catalog=self.catalog,
            source=self.source, independent=self.independent, **kwargs)

    def test_valid_proof_retains_all_paths_and_does_not_certify_source_approval(self):
        witness = self.witness()
        self.assertEqual(witness.value, literal(True, "Boolean"))
        self.assertFalse(witness.source_qualified)
        self.assertEqual(witness.construction_contract_sha256, contract_digest(self.contract))

    def test_inputs_and_intermediate_results_are_checked_even_when_final_gold_is_valid(self):
        narrow = replace(domain(), values=(literal(True, "Boolean"),), closed=False)
        with self.assertRaisesRegex(TypedError, "INPUT_DOMAIN"):
            self.witness(contract=replace(self.contract, inputs=(LeafDomainBinding((0,), narrow),)))
        composed = curry(self.operation)(self.expression)
        contract = replace(self.contract, inputs=(LeafDomainBinding((0, 0), domain()),))
        with self.assertRaisesRegex(TypedError, "INTERMEDIATE_DOMAIN"):
            self.witness(composed, contract)
        contract = replace(contract, intermediates=(LeafDomainBinding((0,), domain()),))
        self.assertEqual(self.witness(composed, contract).value, literal(False, "Boolean"))
        with self.assertRaisesRegex(TypedError, "INTERMEDIATE_DOMAIN"):
            self.witness(composed, replace(contract, intermediates=(LeafDomainBinding((0,), narrow),)))

    def test_pin_oracle_wire_type_and_catalog_drift_fail_at_boundary(self):
        with self.assertRaisesRegex(TypedError, "PIN_MISMATCH"):
            verify_domain_witness(self.expression, contract=self.contract, expected_contract_sha256="9" * 64,
                catalog=self.catalog, source=self.source, independent=self.independent)
        wrong = curry(replace(self.operation, contract_sha256="f" * 64))(literal(False, "Boolean"))
        with self.assertRaisesRegex(TypedError, "CATALOG_DRIFT"):
            self.witness(wrong)
        class Wrong(BooleanBackend):
            def invoke(self, operation, values, world_contract):
                return False
        with self.assertRaisesRegex(TypedError, "ORACLE_DISAGREEMENT"):
            verify_domain_witness(self.expression, contract=self.contract,
                expected_contract_sha256=contract_digest(self.contract), catalog=self.catalog,
                source=self.source, independent=Wrong("wrong"))

    def test_native_tokens_require_actual_catalog_identity_and_fingerprint(self):
        tokens = tuple(SemanticToken(i, f"fixture.answer.{value}", f"answer.{value}",
            "Boolean", 0, "answer", "literal", "synthetic fixture", str(i + 1) * 64)
            for i, value in enumerate((False, True)))
        semantic = SemanticCatalog("fixture/v1", "c" * 64, 2, tokens, ())
        boolean = domain()
        answer = AnswerContract(AnswerMode.NATIVE_TOKEN, boolean,
            tuple(zip(boolean.values, (0, 1))), semantic.digest,
            tuple((value, f"fixture.answer.{value.value}") for value in boolean.values))
        contract = replace(self.contract, answer=answer)
        with self.assertRaisesRegex(TypedError, "NATIVE_CATALOG_REQUIRED"):
            self.witness(contract=contract)
        self.assertEqual(self.witness(contract=contract, semantic_catalog=semantic).native_token_index, 1)
        swapped = replace(answer, native_tokens=tuple(zip(boolean.values, (1, 0))))
        with self.assertRaisesRegex(TypedError, "NATIVE_IDENTITY_DRIFT"):
            self.witness(contract=replace(contract, answer=swapped), semantic_catalog=semantic)
        with self.assertRaisesRegex(TypedError, "NATIVE_CATALOG_DRIFT"):
            self.witness(contract=contract, semantic_catalog=replace(semantic, release="fixture/v2"))

    def test_transformation_receipts_retain_counterexamples_unknown_and_full_cohort(self):
        obligation = FamilyObligation(ConstructionFamily.RECONSTRUCTION, FamilyDisposition.REQUIRED,
                                       "synthetic equivalence", SOURCE)
        examples = tuple(curry(self.operation)(literal(value, "Boolean")) for value in (False, True))
        def checked(transform, precondition=lambda _: True):
            law = LawCandidate(self.operation, SOURCE.locator, "Boolean", None, precondition, transform)
            return verify_transformation_family(obligation, law, examples,
                expected_obligation_sha256=contract_digest(obligation), catalog=self.catalog,
                source=self.source, independent=self.independent)
        self.assertEqual(checked(lambda x: x).check.status, LawCheckStatus.VERIFIED_FINITE_SCOPE)
        failed = checked(lambda x: curry(self.operation)(x))
        self.assertEqual(failed.check.status, LawCheckStatus.COUNTEREXAMPLE)
        self.assertEqual(len(failed.specimen_sha256), 2)
        self.assertEqual(checked(lambda x: x, lambda _: False).check.status,
                         LawCheckStatus.UNKNOWN_NO_APPLICABLE_CASES)

    def test_stateful_transformation_cannot_be_presented_as_a_repeatable_witness(self):
        obligation = FamilyObligation(ConstructionFamily.INVERSE, FamilyDisposition.REQUIRED, "fixture", SOURCE)
        count = 0
        def stateful(expression):
            nonlocal count
            count += 1
            return expression if count % 2 else curry(self.operation)(expression)
        law = LawCandidate(self.operation, SOURCE.locator, "Boolean", None, lambda _: True, stateful)
        with self.assertRaisesRegex(TypedError, "NONDETERMINISTIC"):
            verify_transformation_family(obligation, law, (self.expression,),
                expected_obligation_sha256=contract_digest(obligation), catalog=self.catalog,
                source=self.source, independent=self.independent)

    def test_numeric_wire_results_and_output_scope_do_not_broaden_core_literal(self):
        from bilqis_mlx.semantics.domains import ValueCodec
        numbers = domain(kind="Number", values=("0", "1"), codec=ValueCodec.DECIMAL_INTEGER_TEXT)
        op = Operation(1, "fixture.copy", Signature(("Number",), "Number"), "c" * 64)
        expression = curry(op)(literal("1", "Number"))
        contract = replace(self.contract, inputs=(LeafDomainBinding((0,), numbers),),
                           answer=AnswerContract(AnswerMode.FINITE_TYPED, numbers))
        class Wire:
            def __init__(self, identity, raw=False):
                self.identity, self.raw = identity, raw
            def invoke(self, operation, values, world_contract):
                return int(values[0]) if self.raw else values[0]
        def check(item, raw=False):
            return verify_domain_witness(expression, contract=item, expected_contract_sha256=contract_digest(item),
                catalog=Catalog((op,)), source=Wire("s", raw), independent=Wire("i", raw))
        self.assertEqual(check(contract).value, literal("1", "Number"))
        with self.assertRaisesRegex(TypedError, "CANONICAL_WIRE_VALUE"):
            check(contract, raw=True)
        narrow = replace(numbers, values=(literal("0", "Number"),))
        with self.assertRaisesRegex(TypedError, "OUTPUT_DOMAIN"):
            check(replace(contract, answer=replace(contract.answer, domain=narrow)))

    def test_opt_in_package_consumer_keeps_existing_checks_and_unqualified_family_debt(self):
        from bilqis_mlx.curriculum_compiler import compile_typed_candidate_package
        from bilqis_mlx.verification.curriculum import inspect_construction_contracts
        ast, template, contract = construction()
        package = compile_typed_candidate_package(ast, operations={self.operation.symbol: self.operation},
            templates={contract.capability: template}, source=self.source, independent=self.independent,
            specimens_per_split=2)
        contracts = {contract.capability: contract}
        report = inspect_construction_contracts(package, contracts=contracts,
            expected_contracts_sha256=contract_digest(contracts), catalog=self.catalog,
            source=self.source, independent=self.independent)
        self.assertEqual(report.mechanical_problems, ())
        self.assertEqual(len(report.witnesses), 4)
        self.assertFalse(report.source_qualified)
        self.assertFalse(report.training_authorized)
        self.assertIn("SOURCE_COMPLETENESS_ATTESTATION_REQUIRED", report.qualification_gaps)
        forged = replace(package, tests=(replace(package.tests[0],
            proof=replace(package.tests[0].proof, result=not package.tests[0].proof.result)), *package.tests[1:]))
        failed = inspect_construction_contracts(forged, contracts=contracts,
            expected_contracts_sha256=contract_digest(contracts), catalog=self.catalog,
            source=self.source, independent=self.independent)
        self.assertIn("GRADE_ADMISSION_CANDIDATE_PROOF_INVALID", failed.mechanical_problems)
