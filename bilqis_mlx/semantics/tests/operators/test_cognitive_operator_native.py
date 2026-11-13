"""Native numeric source and pure-operator compatibility tests."""
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.core import Operation, Signature, literal
from bilqis_mlx.semantics.frame_schema import source_node_digest
from bilqis_mlx.semantics import numeric as released_numeric
from bilqis_mlx.semantics.cognitive_operators import (ValueState, default_registry,
    execute_pure, numeric_domain_digest, source_operand_digest)
from bilqis_mlx.semantics.tests.test_cognitive_operators import RELEASE, _case

class CognitiveOperatorNativeTests(unittest.TestCase):
    def test_native_numeric_execution_matches_released_source_semantics(self):
        cases = (
            ("ADD", (2, 3), 5),
            ("SUB", (3, 2), 1),
            ("MUL", (2, 3), 6),
            ("DIV", (6, 3), 2),
            ("EQ", (2, 2), True),
            ("LT", (2, 3), True),
            ("LE", (3, 3), True),
            ("SUCC", (2,), 3),
        )
        for operator_id, numbers, expected in cases:
            with self.subTest(operator=operator_id):
                binding, inputs = _case(
                    *(("Number", number) for number in numbers))
                actual = execute_pure(operator_id, inputs, binding)
                source = released_numeric.evaluate(
                    released_numeric.calculate(
                        operator_id, *(released_numeric.number(value)
                                       for value in numbers)))
                self.assertEqual(actual.state, ValueState.VALUE)
                self.assertEqual(actual.value, expected)
                self.assertEqual(actual.value, source)
                self.assertTrue(binding.registry.resolve(
                    operator_id).source_reference.startswith(
                        "bilqis_mlx.semantics.numeric:"))
        for name in ("COUNT", "MOD"):
            self.assertEqual(
                default_registry(RELEASE).resolve(name).source_reference,
                "public-formal-law:" + name)

    def test_new_native_registry_member_cannot_redirect_formal_law_execution(self):
        binding, values = _case(("Number", 5), ("Number", 3))
        injected = Operation(
            9999, "MOD", Signature(("Number", "Number"), "Number"),
            "0" * 64)
        with patch.dict(released_numeric.OPERATIONS, {"MOD": injected}):
            with patch.object(
                    released_numeric, "calculate",
                    side_effect=AssertionError("native MOD path reached")):
                self.assertEqual(execute_pure("MOD", values, binding).value, 2)
                self.assertEqual(
                    binding.registry.resolve("MOD").source_reference,
                    "public-formal-law:MOD")

    def test_numeric_inapplicability_does_not_hide_contract_drift(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        self.assertEqual(execute_pure("DIV", values, binding).state,
                         ValueState.UNSUPPORTED)
        with patch.object(
                released_numeric, "evaluate_pure",
                side_effect=ValueError("NUMERIC_OPERATOR_CONTRACT_DRIFT")):
            with self.assertRaises(BilqisError) as caught:
                execute_pure("ADD", values, binding)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_OPERATOR_SOURCE_EXECUTION_DRIFT")

    def test_runtime_bypasses_evaluator_owned_source_cache(self):
        binding, values = _case(("Number", 2), ("Number", 3))

        def evaluator_cache_trap(*args, **kwargs):
            raise AssertionError("evaluator-owned cache reached by solver")

        with patch.object(released_numeric, "evaluate", evaluator_cache_trap):
            self.assertEqual(execute_pure("ADD", values, binding).value, 5)

    def test_source_node_digest_keeps_legacy_wire_without_assessment_import(self):
        node = {"id": "café", "arity": 2, "signature": "Number*Number->Number"}
        expected = hashlib.sha256(
            json.dumps(node, sort_keys=True, separators=(",", ":"),
                       allow_nan=False).encode("utf-8")).hexdigest()
        self.assertEqual(source_node_digest(node), expected)

    def test_source_numeric_abi_bound_is_independent_of_admitted_domain(self):
        binding, values = _case(("Number", 101), ("Number", 1))
        expanded = replace(
            binding.numeric_domain,
            values=tuple(literal(str(index), "Number") for index in range(110)))
        grants = tuple(
            replace(grant, evidence_digest=numeric_domain_digest(expanded, RELEASE))
            if grant.source_handle == binding.numeric_source_handle else grant
            for grant in binding.frontier.grants)
        binding = replace(
            binding, numeric_domain=expanded,
            frontier=replace(binding.frontier, grants=grants))
        self.assertEqual(execute_pure("ADD", values, binding).state,
                         ValueState.UNSUPPORTED)

    def test_event_unknown_and_none_never_become_occurred(self):
        binding, values = _case(("EventStatus", "PLANNED"), numbers=False)
        self.assertIs(execute_pure("IS_OCCURRED", values, binding).value, False)
        for state, expected in (
            (ValueState.UNKNOWN, ValueState.UNKNOWN),
            (ValueState.NONE, ValueState.UNSUPPORTED),
        ):
            input_value = replace(values[0], value=None, state=state)
            operand = replace(binding.operands[0], typed=input_value)
            grants = tuple(
                replace(grant, evidence_digest=source_operand_digest(operand))
                if grant.source_handle == input_value.source_handle else grant
                for grant in binding.frontier.grants)
            scoped = replace(
                binding, operands=(operand,),
                frontier=replace(binding.frontier, grants=grants))
            self.assertEqual(
                execute_pure("IS_OCCURRED", (input_value,), scoped).state,
                expected)

