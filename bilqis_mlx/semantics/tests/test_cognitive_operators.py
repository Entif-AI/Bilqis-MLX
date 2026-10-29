"""Literal witnesses for source-qualified pure cognition, without neural calls."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.cognitive_operators import (
    Duration, OperatorBinding, SourceKind, SourceOperand, TypedValue,
    UnitConversion,
    ValueState, default_registry, execute_pure, numeric_domain_digest,
    source_operand_digest,
)
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextEligibility, ContextMember, ContextPolicy,
    SourceFrontier, SourceGrant, TaskScope, frame_evidence_digest,
    member_evidence_digest,
)
from bilqis_mlx.semantics.core import literal
from bilqis_mlx.semantics.domains import (
    FiniteDomain, SourceBinding, ValueCodec,
)
from bilqis_mlx.semantics.frame_schema import (
    BindingState, ConceptRef, FrameSchema, RoleOccurrence, RoleSpec,
    SourceSpan, make_frame_instance,
)
from bilqis_mlx.semantics.laws import SourceLocator


RELEASE = "a" * 64
PRINCIPAL = "synthetic:person"
TENANT = "synthetic:tenant"
JURISDICTION = "synthetic:region"
SCOPE = "synthetic:task"
PURPOSE = "TRAINING"


def _grant(handle: str, evidence: str, *, revoked: bool = False):
    return SourceGrant(
        handle, PRINCIPAL, TENANT, PUBLIC_FORMAL, RELEASE, evidence,
        (PURPOSE,), (JURISDICTION,), (SCOPE,),
        rights_epoch=1, correction_generation=1, observed_at=2,
        effective_from=0, revoked=revoked,
    )


def _base(*, numbers: bool = True):
    task = TaskScope(
        PRINCIPAL, TENANT, PURPOSE, RELEASE, JURISDICTION, SCOPE,
        observed_frontier=3, effective_time=5, causal_prefix_end=20,
    )
    policy = ContextPolicy(
        "synthetic:policy", 1, 1,
        (PURPOSE,), (PUBLIC_FORMAL,), (JURISDICTION,), (SCOPE,),
        (PUBLIC_FORMAL,), ((PUBLIC_FORMAL, PUBLIC_FORMAL),),
        ((PUBLIC_FORMAL, PUBLIC_FORMAL, PUBLIC_FORMAL),),
    )
    domain = None
    domain_handle = None
    grants = []
    if numbers:
        domain = FiniteDomain(
            "synthetic:number", "v1", "Number",
            tuple(literal(str(index), "Number") for index in range(11)),
            SourceBinding(SourceLocator("synthetic", "v1", "numbers"), "d" * 64),
            codec=ValueCodec.DECIMAL_INTEGER_TEXT, closed=True,
        )
        domain_handle = "source:numbers"
        grants.append(_grant(domain_handle, numeric_domain_digest(domain, RELEASE)))
    return task, policy, domain, domain_handle, grants


def _case(*values: tuple[str, object], numbers: bool = True):
    task, policy, domain, domain_handle, grants = _base(numbers=numbers)
    operands = []
    typed = []
    for index, (type_name, value) in enumerate(values):
        handle = "source:literal:" + str(index)
        item = TypedValue(type_name, value, RELEASE, source_handle=handle)
        operand = SourceOperand(
            item, SourceKind.TASK_VISIBLE,
            "synthetic:source:" + str(index), visible_at_prefix=8)
        operands.append(operand)
        typed.append(item)
        grants.append(_grant(handle, source_operand_digest(operand)))
    frontier = SourceFrontier(
        1, 1, tuple(sorted(grants, key=lambda grant: grant.source_handle)))
    binding = OperatorBinding(
        task, frontier, policy, default_registry(RELEASE), tuple(operands),
        numeric_domain=domain, numeric_source_handle=domain_handle)
    return binding, tuple(typed)


def _with_frame(binding, *, name="one", parent=None, state=BindingState.VALUE,
                start=0, end=8):
    concept = ConceptRef(
        "formal:entity.one", RELEASE, 1, ("Entity",),
        "synthetic:source:entity.one")
    schema = FrameSchema(
        "synthetic:frame", 1, "source:synthetic",
        (RoleSpec("subject", ("Entity",), 1, 1),),
        "ORDERED", SCOPE)
    occupant = RoleOccurrence(
        "subject", 0, concept=concept if state is BindingState.VALUE else None,
        state=state)
    frame = make_frame_instance(
        schema, source_instance_id=name, structural_path=(),
        source_span=SourceSpan(start, end),
        parent_occurrence_id=parent, bindings=(occupant,),
        causal_prefix_end=end,
    )
    frame_handle = "frame:" + name
    frame_source = "source:frame:" + name
    member = ContextMember(
        "subject", 0, "source:member:" + name, visible_at_prefix=end)
    envelope = ContextEligibility(
        frame_handle, frame, frame_source, (member,),
        PRINCIPAL, TENANT, PURPOSE, PUBLIC_FORMAL, RELEASE,
        JURISDICTION, SCOPE, PUBLIC_FORMAL, 1, 1, 1, 2, 0, None, end,
    )
    grants = (
        _grant(frame_source, frame_evidence_digest(frame)),
        _grant(member.source_handle, member_evidence_digest(frame, member)),
    )
    frontier = replace(
        binding.frontier,
        grants=tuple(sorted((*binding.frontier.grants, *grants),
                            key=lambda grant: grant.source_handle)),
    )
    return replace(binding, frontier=frontier,
                   frames=(*binding.frames, envelope)), frame, concept


def _with_unit_edge(binding, from_unit: str, to_unit: str, numerator: int,
                    denominator: int):
    handle = "source:unit:" + from_unit + ":" + to_unit
    edge = SourceOperand(
        TypedValue(
            "UnitConversion",
            UnitConversion(from_unit, to_unit, numerator, denominator),
            RELEASE, handle),
        SourceKind.ADMITTED_KNOWLEDGE, "synthetic:released-unit-table", 0,
    )
    frontier = replace(
        binding.frontier,
        grants=tuple(sorted((
            *binding.frontier.grants, _grant(handle, source_operand_digest(edge))),
            key=lambda grant: grant.source_handle)),
    )
    return replace(binding, frontier=frontier,
                   operands=(*binding.operands, edge))


class CognitiveOperatorsTests(unittest.TestCase):
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
                                (BindingState.UNKNOWN, ValueState.UNKNOWN)):
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
        path = Path(__file__).resolve().parents[1] / "cognitive_operators.py"
        source = path.read_text()
        self.assertNotIn("from ..verification", source)
        self.assertNotIn("from ..assessment", source)
        self.assertNotIn("import mlx", source)


if __name__ == "__main__":
    unittest.main()
