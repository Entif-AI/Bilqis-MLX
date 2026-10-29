"""Literal witnesses for source-qualified pure cognition, without neural calls."""
from __future__ import annotations

import ast
from dataclasses import fields, replace
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.cognitive_operators import (
    Duration, OperatorBinding, SourceKind, SourceOperand, TypedValue,
    UnitConversion,
    ValueState, default_registry, execute_pure, numeric_domain_digest,
    operator_grant_digest, source_operand_digest,
)
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextEligibility, ContextMember, ContextPolicy,
    SourceFrontier, SourceGrant, TaskScope, frame_evidence_digest,
    member_evidence_digest,
)
from bilqis_mlx.semantics.core import Operation, Signature, literal
from bilqis_mlx.semantics.domains import (
    FiniteDomain, SourceBinding, ValueCodec,
)
from bilqis_mlx.semantics.frame_schema import (
    BindingState, ConceptRef, FrameSchema, RoleOccurrence, RoleSpec,
    SourceSpan, make_frame_instance,
)
from bilqis_mlx.semantics.laws import SourceLocator
from bilqis_mlx.semantics import numeric as released_numeric
from bilqis_mlx.semantics.frame_schema import source_node_digest


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
    grants.extend(
        _grant("source:operator:" + spec.operator_id, operator_grant_digest(spec))
        for spec in default_registry(RELEASE).specs
    )
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
        state=state,
        alternatives=(concept,) if state is BindingState.ALTERNATIVES else ())
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
    def test_solver_runtime_import_closure_has_no_gold_or_assessment_path(self):
        """Transitive production dependency guard, not a source-text smoke test."""
        root = Path(__file__).resolve().parents[3]
        seen = set()
        pending = ["bilqis_mlx.semantics.cognitive_operators"]

        def local_path(name):
            stem = root.joinpath(*name.split("."))
            if stem.with_suffix(".py").is_file():
                return stem.with_suffix(".py"), False
            if (stem / "__init__.py").is_file():
                return stem / "__init__.py", True
            return None, False

        while pending:
            name = pending.pop()
            if name in seen:
                continue
            path, is_package = local_path(name)
            if path is None:
                continue
            seen.add(name)
            package = name if is_package else name.rpartition(".")[0]
            for node in ast.walk(ast.parse(path.read_text())):
                imports = []
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    base = importlib.util.resolve_name(
                        "." * node.level + (node.module or ""), package)
                    imports.append(base)
                    imports.extend(base + "." + alias.name for alias in node.names)
                pending.extend(
                    candidate for candidate in imports
                    if candidate.startswith("bilqis_mlx.")
                    and local_path(candidate)[0] is not None)
        self.assertIn("bilqis_mlx.semantics.numeric", seen)
        forbidden = (
            "bilqis_mlx.verification", "bilqis_mlx.source_adapters",
            "bilqis_mlx.generated_assessment", "bilqis_mlx.assessment",
            "bilqis_mlx.factory", "bilqis_mlx.runtime",
        )
        self.assertFalse(
            [name for name in sorted(seen)
             if name.startswith(forbidden) or name.endswith("_oracle")],
            seen)
        self.assertFalse(
            {"gold", "answer_key", "oracle", "target_label"}
            & {field.name for record in (OperatorBinding, TypedValue)
               for field in fields(record)})



if __name__ == "__main__":
    unittest.main()
