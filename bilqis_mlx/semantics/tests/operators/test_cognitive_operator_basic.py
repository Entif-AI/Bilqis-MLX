"""Pure Boolean, numeric, frame and exact-unit operator examples."""
import unittest
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.cognitive_operators import (Duration, UnitConversion,
    TypedValue, ValueState, default_registry, execute_pure)
from bilqis_mlx.semantics.frame_schema import BindingState
from bilqis_mlx.semantics.tests.test_cognitive_operators import (RELEASE, _case,
    _with_frame, _with_unit_edge)

class CognitiveOperatorBasicTests(unittest.TestCase):
    def test_registry_declares_pure_typed_implementations(self):
        registry = default_registry(RELEASE)
        self.assertEqual(registry.semantic_release, RELEASE)
        self.assertGreaterEqual(len(registry.specs), 20)
        for spec in registry.specs:
            self.assertEqual(spec.effect, "PURE")
            self.assertEqual(spec.version, "v1")
            self.assertEqual(len(spec.implementation_sha256), 64)
            self.assertEqual(registry.resolve(spec.operator_id), spec)
        self.assertEqual(
            registry.resolve("ADD").signature.inputs, ("Number", "Number"))
        self.assertEqual(
            registry.resolve("UNIT_CONVERT").signature.output, "Duration")

    def test_bounded_integer_math_and_zero_is_not_null(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        self.assertEqual(execute_pure("ADD", values, binding).value, 5)
        self.assertEqual(execute_pure("MUL", values, binding).value, 6)
        self.assertEqual(execute_pure("LT", values, binding).value, True)
        self.assertEqual(execute_pure("EQ", values, binding).value, False)
        self.assertEqual(execute_pure("SUB", values, binding).state,
                         ValueState.UNSUPPORTED)
        self.assertEqual(execute_pure("DIV", values, binding).state,
                         ValueState.UNSUPPORTED)
        zeros, zero_inputs = _case(("Number", 0), ("Number", 0))
        result = execute_pure("ADD", zero_inputs, zeros)
        self.assertEqual(result.value, 0)
        self.assertEqual(result.state, ValueState.VALUE)
        self.assertEqual(execute_pure("DIV", zero_inputs, zeros).state,
                         ValueState.UNSUPPORTED)
        too_large, large_inputs = _case(("Number", 9), ("Number", 3))
        self.assertEqual(execute_pure("ADD", large_inputs, too_large).state,
                         ValueState.UNSUPPORTED)
        self.assertEqual(execute_pure("SUCC", large_inputs[:1], too_large).value, 10)

    def test_boolean_truth_cases_without_prediction(self):
        for left in (False, True):
            for right in (False, True):
                binding, values = _case(
                    ("Boolean", left), ("Boolean", right), numbers=False)
                self.assertIs(execute_pure("BOOL_NOT", values[:1], binding).value,
                              not left)
                self.assertIs(execute_pure("BOOL_AND", values, binding).value,
                              left and right)
                self.assertIs(execute_pure("BOOL_OR", values, binding).value,
                              left or right)
                self.assertIs(execute_pure("BOOL_XOR", values, binding).value,
                              left != right)
                self.assertIs(execute_pure("BOOL_IMPLIES", values, binding).value,
                              not left or right)
                self.assertIs(execute_pure("BOOL_IFF", values, binding).value,
                              left == right)

    def test_exact_rational_unit_conversion(self):
        binding, values = _case(
            ("Duration", Duration(1, 4, "h")), ("UnitName", "min"),
            numbers=False)
        self.assertEqual(execute_pure("UNIT_CONVERT", values, binding).state,
                         ValueState.UNSUPPORTED)
        binding = _with_unit_edge(binding, "h", "min", 60, 1)
        result = execute_pure("UNIT_CONVERT", values, binding)
        self.assertEqual(result.value, Duration(15, 1, "min"))
        self.assertEqual(result.value.numerator, 15)
        inverse, inverse_values = _case(
            ("Duration", Duration(15, 1, "min")), ("UnitName", "h"),
            numbers=False)
        inverse = _with_unit_edge(inverse, "min", "h", 1, 60)
        self.assertEqual(execute_pure("UNIT_CONVERT", inverse_values, inverse).value,
                         Duration(1, 4, "h"))
        with self.assertRaises(BilqisError):
            UnitConversion("h", "min", 1, 1)
        with self.assertRaises(BilqisError):
            Duration(0.25, 1, "h")

    def test_role_lookup_identity_and_type_inspection(self):
        binding, values = _case(("RoleId", "subject"), ("Index", 0), numbers=False)
        binding, frame, concept = _with_frame(binding)
        frame_input = TypedValue(
            "FrameHandle", "frame:one", RELEASE, "source:frame:one")
        result = execute_pure("ROLE_LOOKUP", (frame_input, *values), binding)
        self.assertEqual(result.value, concept)
        self.assertEqual(result.state, ValueState.VALUE)
        concept_input = TypedValue(
            "ConceptRef", concept, RELEASE, "source:member:one")
        self.assertEqual(execute_pure(
            "TYPE_OF", (concept_input,), binding).value, ("Entity",))
        self.assertIs(execute_pure(
            "SAME_IDENTITY", (concept_input, concept_input), binding).value, True)
        binding2, values2 = _case(("TypeName", "Entity"), numbers=False)
        binding2, _, concept2 = _with_frame(binding2)
        ref2 = TypedValue("ConceptRef", concept2, RELEASE, "source:member:one")
        self.assertIs(execute_pure(
            "HAS_TYPE", (ref2, *values2), binding2).value, True)

    def test_missing_role_state_preserves_none_and_unknown(self):
        binding, values = _case(("RoleId", "subject"), ("Index", 0), numbers=False)
        frame_input = TypedValue(
            "FrameHandle", "frame:one", RELEASE, "source:frame:one")
        for state, expected in ((BindingState.NONE, ValueState.NONE),
                                (BindingState.UNKNOWN, ValueState.UNKNOWN),
                                (BindingState.ALTERNATIVES, ValueState.UNKNOWN)):
            current, _, _ = _with_frame(binding, state=state)
            self.assertEqual(execute_pure(
                "ROLE_LOOKUP", (frame_input, *values), current).state, expected)

    def test_set_membership_and_planned_event_not_occurred(self):
        binding, values = _case(
            ("Entity", "A"), ("EntitySet", ("A", "B")), numbers=False)
        self.assertIs(execute_pure("MEMBER_OF", values, binding).value, True)
        other, other_values = _case(
            ("Entity", "C"), ("EntitySet", ("A", "B")), numbers=False)
        self.assertIs(execute_pure("MEMBER_OF", other_values, other).value, False)
        planned, planned_values = _case(("EventStatus", "PLANNED"), numbers=False)
        self.assertIs(execute_pure(
            "IS_OCCURRED", planned_values, planned).value, False)
        occurred, occurred_values = _case(("EventStatus", "OCCURRED"), numbers=False)
        self.assertIs(execute_pure(
            "IS_OCCURRED", occurred_values, occurred).value, True)

