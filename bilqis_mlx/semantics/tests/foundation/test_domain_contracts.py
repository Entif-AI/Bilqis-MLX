"""Finite declarations preserve wire types and explicit coverage debt."""
from dataclasses import asdict, replace
from types import MappingProxyType
import unittest

from bilqis_mlx.curriculum_contracts import (ConstructionFamily, ContractPlanStatus,
    FamilyDisposition, FamilyObligation, LeafDomainBinding, plan_construction_contracts)
from bilqis_mlx.semantics.foundation.core import TypedError, literal
from bilqis_mlx.semantics.foundation.domains import (AnswerContract, AnswerMode, ValueCodec, contract_digest)
from tests.support.contract_fixtures import SOURCE, construction, domain


class DomainContractTests(unittest.TestCase):
    def test_decimal_text_roundtrip_keeps_python_bool_outside_integer_codec(self):
        numbers = domain(kind="Number", values=("0", "1", "2"), codec=ValueCodec.DECIMAL_INTEGER_TEXT)
        for value in range(3):
            self.assertEqual(numbers.encode(value), literal(str(value), "Number"))
            self.assertEqual(numbers.decode(numbers.encode(value)), value)
        for bad in (True, False, "1", 1.0, None):
            with self.subTest(bad=bad), self.assertRaises(TypedError):
                numbers.encode(bad)
        for bad in ("01", "-0", "+1", "1.0", " 1", "١"):
            with self.subTest(bad=bad), self.assertRaises(TypedError):
                domain(kind="Number", values=(bad,), codec=ValueCodec.DECIMAL_INTEGER_TEXT)

    def test_source_scope_duplicates_and_incomplete_boolean_fail_closed(self):
        original = domain()
        for updates in ({"source": None}, {"closed": 1}, {"values": ()},
                        {"values": (literal(True, "Boolean"),)},
                        {"values": original.values * 2}, {"world_contract": "foreign"},
                        {"values": (literal("x", "Entity"),)}):
            with self.subTest(updates=updates), self.assertRaises(TypedError):
                replace(original, **updates)

    def test_nested_mapping_contract_hash_matches_plain_values_and_detects_edits(self):
        ast, template, contract = construction()
        plain = {contract.capability: asdict(contract)}
        self.assertEqual(contract_digest({contract.capability: contract}), contract_digest(plain))
        self.assertEqual(contract_digest(MappingProxyType({contract.capability: contract})),
                         contract_digest(plain))
        self.assertNotEqual(contract_digest(contract), contract_digest(replace(contract,
            answer=replace(contract.answer, domain=replace(contract.answer.domain, revision="v2")))))

    def test_native_mappings_are_typed_immutable_bijections(self):
        boolean = domain()
        mapping = tuple(zip(boolean.values, (10, 11)))
        answer = AnswerContract(AnswerMode.NATIVE_TOKEN, boolean, mapping, "c" * 64)
        self.assertEqual(answer.token_for(literal(True, "Boolean")), 11)
        for bad in ((), mapping[:1], ((boolean.values[0], 10), (boolean.values[1], 10)),
                    ((boolean.values[0], True), (boolean.values[1], 11)),
                    list(mapping), (("bad", 10), (boolean.values[1], 11)), (None,)):
            with self.subTest(bad=bad), self.assertRaises(TypedError):
                replace(answer, native_tokens=bad)

    def test_all_families_and_exact_leaf_domains_remain_a_proposal(self):
        ast, template, contract = construction()
        plan = plan_construction_contracts(ast, templates={contract.capability: template},
            contracts={contract.capability: contract}, construction_budget=2)
        self.assertEqual(plan.status, ContractPlanStatus.UNQUALIFIED_PROPOSAL)
        self.assertFalse(plan.training_authorized)
        self.assertEqual(plan.finite_counts, ((contract.capability, 2),))
        required = replace(contract, families=tuple(replace(f, disposition=FamilyDisposition.REQUIRED)
                                                    for f in contract.families))
        plan = plan_construction_contracts(ast, templates={contract.capability: template},
            contracts={contract.capability: required}, construction_budget=1)
        self.assertEqual(len(plan.required_families), len(ConstructionFamily))
        self.assertTrue(any(item.startswith("FINITE_DOMAIN_OVER_BUDGET") for item in plan.coverage_debt))
        self.assertEqual(sum(item.startswith("MISSING_FAMILY_WITNESSES") for item in plan.coverage_debt), 8)
        for inputs in ((LeafDomainBinding((1,), domain()),),
                       (LeafDomainBinding((0,), domain(values=(True, False))),),
                       contract.inputs * 2):
            with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                plan_construction_contracts(ast, templates={contract.capability: template},
                    contracts={contract.capability: replace(contract, inputs=inputs)}, construction_budget=2)

    def test_malformed_family_and_leaf_inputs_have_contract_errors(self):
        for rationale in (None, 123, [], ""):
            with self.subTest(rationale=rationale), self.assertRaises(ValueError):
                FamilyObligation(ConstructionFamily.DIRECT, FamilyDisposition.REQUIRED, rationale, SOURCE)
        with self.assertRaises(ValueError):
            LeafDomainBinding([0], domain())
        with self.assertRaises(TypedError):
            AnswerContract(AnswerMode.BINARY, domain(), native_tokens=[])
        with self.assertRaises(ValueError):
            FamilyObligation(ConstructionFamily.DIRECT, FamilyDisposition.UNREVIEWED, "review pending", "fake-source")

    def test_plan_pins_executable_templates_and_records_missing_intermediate_scope(self):
        from bilqis_mlx.curriculum_compiler import TypedExpressionTemplate
        ast, template, contract = construction()
        plan = plan_construction_contracts(ast, templates={contract.capability: template},
            contracts={contract.capability: contract}, construction_budget=4)
        changed = replace(template, operation=replace(template.operation, contract_sha256="9" * 64))
        other = plan_construction_contracts(ast, templates={contract.capability: changed},
            contracts={contract.capability: contract}, construction_budget=4)
        self.assertNotEqual(plan.templates_sha256, other.templates_sha256)
        composed = TypedExpressionTemplate(template.operation, (template,))
        composed_contract = replace(contract, inputs=(LeafDomainBinding((0, 0), domain()),))
        incomplete = plan_construction_contracts(ast, templates={contract.capability: composed},
            contracts={contract.capability: composed_contract}, construction_budget=4)
        self.assertTrue(any(d.startswith("MISSING_INTERMEDIATE_DOMAIN") for d in incomplete.coverage_debt))
