"""Source-grant, source-contract and visibility adversaries."""
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics import numeric as released_numeric
from bilqis_mlx.semantics.cognitive_operators import (TypedValue, ValueState,
    default_registry, execute_pure, source_operand_digest)
from bilqis_mlx.semantics.tests.test_cognitive_operators import (RELEASE, _case, _with_frame)

class CognitiveOperatorAuthorityTests(unittest.TestCase):
    def test_released_structural_relations_use_occurrences(self):
        binding, _ = _case(numbers=False)
        binding, parent, _ = _with_frame(binding, name="parent", start=0, end=8)
        binding, child, _ = _with_frame(
            binding, name="child", parent=parent.occurrence_id, start=9, end=12)
        left = TypedValue(
            "FrameHandle", "frame:parent", RELEASE, "source:frame:parent")
        right = TypedValue(
            "FrameHandle", "frame:child", RELEASE, "source:frame:child")
        self.assertIs(execute_pure(
            "PARENT_OF", (left, right), binding).value, True)
        self.assertIs(execute_pure(
            "BEFORE", (left, right), binding).value, True)
        self.assertIs(execute_pure(
            "PARENT_OF", (right, left), binding).value, False)

    def test_forged_or_revoked_source_cannot_become_an_operand(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        self.assertEqual(execute_pure("ADD", values, binding).value, 5)
        tampered = replace(values[0], value=9)
        with self.assertRaises(BilqisError) as caught:
            execute_pure("ADD", (tampered, values[1]), binding)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_OPERATOR_OPERAND_NOT_ADMITTED")
        revoked = replace(binding.frontier.grants[0], revoked=True)
        frontier = replace(
            binding.frontier, grants=(revoked, *binding.frontier.grants[1:]))
        with self.assertRaises(BilqisError):
            execute_pure("ADD", values, replace(binding, frontier=frontier))
        foreign = replace(values[0], semantic_release="b" * 64)
        with self.assertRaises(BilqisError):
            execute_pure("ADD", (foreign, values[1]), binding)

    def test_registry_cannot_relabel_numeric_bounds_or_implementation(self):
        binding, values = _case(("Number", 9), ("Number", 3))
        original = binding.registry.resolve("ADD")
        for changed in (
            replace(original, applicability="SOURCE_BOOLEAN"),
            replace(original, version="v2"),
            replace(original, implementation_sha256="0" * 64),
        ):
            registry = replace(
                binding.registry,
                specs=tuple(changed if item.operator_id == "ADD" else item
                            for item in binding.registry.specs))
            with self.subTest(changed=changed), self.assertRaises(BilqisError):
                execute_pure("ADD", values, replace(binding, registry=registry))
        self.assertEqual(execute_pure("ADD", values, binding).state,
                         ValueState.UNSUPPORTED)

    def test_operator_requires_released_source_grant_and_numeric_contract(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        self.assertEqual(execute_pure("ADD", values, binding).value, 5)
        missing = replace(
            binding.frontier,
            grants=tuple(grant for grant in binding.frontier.grants
                         if grant.source_handle != "source:operator:ADD"))
        with self.assertRaises(BilqisError) as caught:
            execute_pure("ADD", values, replace(binding, frontier=missing))
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_OPERATOR_SOURCE_GRANT_MISSING")
        original = released_numeric.OPERATIONS["ADD"]
        with patch.dict(released_numeric.OPERATIONS, {
                "ADD": replace(original, contract_sha256="0" * 64)}):
            with self.assertRaises(BilqisError) as caught:
                execute_pure("ADD", values, binding)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_OPERATOR_SOURCE_CONTRACT_DRIFT")
        missing_native = {
            name: operation for name, operation in released_numeric.OPERATIONS.items()
            if name != "ADD"
        }
        with patch.dict(released_numeric.OPERATIONS, missing_native, clear=True):
            with self.assertRaises(BilqisError) as caught:
                default_registry(RELEASE)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_OPERATOR_NATIVE_SOURCE_MISSING")

    def test_numeric_domain_requires_exact_source_grant_and_version(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        expanded = replace(
            binding.numeric_domain, revision="v2")
        with self.assertRaises(BilqisError) as caught:
            execute_pure("ADD", values, replace(binding, numeric_domain=expanded))
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_OPERATOR_SOURCE_GRANT_INELIGIBLE")
        missing = replace(
            binding.frontier,
            grants=tuple(grant for grant in binding.frontier.grants
                         if grant.source_handle != binding.numeric_source_handle))
        with self.assertRaises(BilqisError):
            execute_pure("ADD", values, replace(binding, frontier=missing))

    def test_unknown_and_none_remain_distinct_from_zero(self):
        binding, values = _case(("Number", 0), ("Number", 3))
        unknown = replace(values[0], value=None, state=ValueState.UNKNOWN)
        null = replace(values[0], value=None, state=ValueState.NONE)
        for input_value, expected in (
            (unknown, ValueState.UNKNOWN), (null, ValueState.UNSUPPORTED)):
            operand = replace(binding.operands[0], typed=input_value)
            grants = tuple(
                replace(grant, evidence_digest=source_operand_digest(operand))
                if grant.source_handle == input_value.source_handle else grant
                for grant in binding.frontier.grants)
            scoped = replace(
                binding, operands=(operand, binding.operands[1]),
                frontier=replace(binding.frontier, grants=grants))
            self.assertEqual(
                execute_pure("ADD", (input_value, values[1]), scoped).state,
                expected)
        self.assertEqual(execute_pure("ADD", values, binding).value, 3)

    def test_invisible_and_ungranted_frame_cannot_be_read(self):
        binding, values = _case(("RoleId", "subject"), ("Index", 0), numbers=False)
        binding, _, _ = _with_frame(binding)
        frame_input = TypedValue(
            "FrameHandle", "frame:one", RELEASE, "source:frame:one")
        bad_scope = replace(binding.task, causal_prefix_end=4)
        with self.assertRaises(BilqisError):
            execute_pure(
                "ROLE_LOOKUP", (frame_input, *values),
                replace(binding, task=bad_scope))
        unknown = TypedValue(
            "FrameHandle", "frame:ungranted", RELEASE, "source:frame:one")
        with self.assertRaises(BilqisError):
            execute_pure("ROLE_LOOKUP", (unknown, *values), binding)

    def test_no_implicit_bool_number_coercion_or_gold_dependency(self):
        with self.assertRaises(BilqisError):
            TypedValue("Number", True, RELEASE)
        with self.assertRaises(BilqisError):
            TypedValue("Number", None, RELEASE)
        with self.assertRaises(BilqisError):
            TypedValue("Number", 0, RELEASE, state=ValueState.NONE)
        package = Path(__file__).resolve().parents[1] / "cognitive_operators"
        source = "\n".join(path.read_text() for path in package.glob("*.py"))
        self.assertNotIn("from ..verification", source)
        self.assertNotIn("from ..assessment", source)
        self.assertNotIn("import mlx", source)

