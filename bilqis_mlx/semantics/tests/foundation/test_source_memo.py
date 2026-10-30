"""Source calculations reuse semantic identities without sharing oracle answers."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.semantics.foundation.memo import memoize_source
from bilqis_mlx.semantics.foundation import numeric
from bilqis_mlx.verification.numeric import independent_value


class SourceMemoTests(TestCase):
    def test_equivalent_ast_instances_and_keyword_calls_reuse_one_calculation(self):
        calls = []

        @memoize_source(semantics="fixture-arithmetic/v1")
        def source(expression):
            calls.append(expression)
            return 5

        first = numeric.calculate("ADD", numeric.number(2), numeric.number(3))
        second = numeric.calculate("ADD", numeric.number(2), numeric.number(3))
        self.assertIsNot(first, second)
        self.assertEqual(source(first), 5)
        self.assertEqual(source(expression=second), 5)
        self.assertEqual(len(calls), 1)

    def test_operator_contract_types_and_world_are_part_of_the_key(self):
        calls = []

        @memoize_source(semantics="fixture/v1")
        def source(expression):
            calls.append(expression)
            return False

        first = numeric.calculate("EQ", numeric.number(2), numeric.number(3))
        changed = replace(first, operator=replace(first.operator, contract_sha256="f" * 64))
        world = replace(first, world_contract="other-world", arguments=tuple(
            replace(arg, world_contract="other-world") for arg in first.arguments))
        for expression in (first, changed, world, numeric.number(2)):
            self.assertFalse(source(expression))
            self.assertFalse(source(expression))
        self.assertEqual(len(calls), 4)

    def test_mutated_source_input_cannot_reuse_an_old_answer(self):
        calls = []

        @memoize_source(semantics="finite-world/v1")
        def source(record):
            calls.append(record["world"]["value"])
            return record["world"]["value"]

        record = {"query": "value", "world": {"value": 2}}
        self.assertEqual(source(record), 2)
        self.assertEqual(source({"world": {"value": 2}, "query": "value"}), 2)
        record["world"]["value"] = 3
        self.assertEqual(source(record), 3)
        self.assertEqual(calls, [2, 3])

    def test_source_oracle_and_semantic_revisions_have_separate_caches(self):
        calls = []

        def calculation(expression):
            calls.append(expression)
            return len(calls)

        source = memoize_source(semantics="source/v1")(calculation)
        oracle = memoize_source(semantics="oracle/v1")(calculation)
        revised = memoize_source(semantics="source/v2")(calculation)
        expression = numeric.number(2)
        self.assertEqual(source(expression), 1)
        self.assertEqual(oracle(expression), 2)
        self.assertEqual(revised(expression), 3)
        self.assertEqual(source(expression), 1)
        self.assertEqual(len(calls), 3)

    def test_failures_are_not_saved_as_answers(self):
        calls = []

        @memoize_source(semantics="partial-arithmetic/v1")
        def source(expression):
            calls.append(expression)
            raise ValueError("undefined")

        for _ in range(2):
            with self.assertRaisesRegex(ValueError, "undefined"):
                source(numeric.number(0))
        self.assertEqual(len(calls), 2)

    def test_live_numeric_evaluator_reuses_results_and_rejects_changed_contract(self):
        numeric.evaluate.cache_clear()
        expression = numeric.calculate("ADD", numeric.number(2), numeric.number(3))
        with patch.object(numeric, "number", wraps=numeric.number) as calculate:
            self.assertEqual(numeric.evaluate(expression), 5)
            first_calls = calculate.call_count
            self.assertGreater(first_calls, 0)
            self.assertEqual(numeric.evaluate(expression), 5)
            self.assertEqual(calculate.call_count, first_calls)
        changed = replace(expression, operator=replace(
            expression.operator, contract_sha256="f" * 64))
        with self.assertRaisesRegex(ValueError, "OPERATOR_CONTRACT_DRIFT"):
            numeric.evaluate(changed)

    def test_actual_independent_checker_still_computes_its_own_result(self):
        numeric.evaluate.cache_clear()
        independent_value.cache_clear()
        expression = numeric.calculate("ADD", numeric.number(2), numeric.number(3))
        self.assertEqual(numeric.evaluate(expression), 5)
        with patch("bilqis_mlx.verification.numeric.range", wraps=range, create=True) as count:
            self.assertEqual(independent_value(expression), 5)
            self.assertEqual(count.call_count, 2)
            self.assertEqual(independent_value(expression), 5)
            self.assertEqual(count.call_count, 2)
