"""C04.1 source-qualified exact/cache/neural route selection witnesses."""
from __future__ import annotations

from dataclasses import replace
import ast
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.cognitive_solver import (
    GenerationBinding, NeuralProposal, QualifiedComposition,
    RouteKind, SolveBudget, SolveContext, solve_task,
)
from bilqis_mlx.semantics.cognitive_dag import (
    DAGBudget, DAGNode, DAGOperand, RefKind,
)
from bilqis_mlx.semantics.cognitive_operators import ValueState
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.semantics.memo import PureOperationMemo
from bilqis_mlx.semantics.tests.test_cognitive_dag import (
    _goal, _literal, _program,
)
from bilqis_mlx.semantics.tests.test_cognitive_operators import (
    RELEASE, SCOPE, _case,
)

from bilqis_mlx.runtime.tests.capability.solver_helpers import _fixture

class CognitiveSolverTests(unittest.TestCase):
    def test_neural_cannot_rewrite_fixed_operands(self):
        binding, generation, budget, add, ambiguous = _fixture()
        node = add.expression_or_holes.nodes[0]
        changed = replace(add, expression_or_holes=_program(replace(
            node, operands=(node.operands[0], node.operands[0]))))
        result = solve_task(
            ambiguous, SolveContext(binding, neural_proposer=lambda request:
                NeuralProposal(changed, request.source_binding_digest,
                               request.generation_digest,
                               request.unresolved_signature, "b" * 64)),
            generation, budget)
        self.assertEqual(result.route, RouteKind.UNRESOLVED)
        self.assertEqual(sum(r.operation_count for r in result.dag_receipts), 0)


    def test_qualified_cache_and_fallback_cannot_change_fixed_question(self):
        binding, generation, budget, add, ambiguous = _fixture()
        node = add.expression_or_holes.nodes[0]
        changed = replace(add, expression_or_holes=_program(replace(
            node, operands=(node.operands[0], node.operands[0]))))
        cached = QualifiedComposition(
            changed, generation.source_binding_digest,
            binding.frontier.rights_epoch,
            binding.frontier.correction_generation, "a" * 64)
        for context in (
                SolveContext(binding, qualified_compositions=(cached,),
                             qualification_verifier=lambda item: True),
                SolveContext(binding, deterministic_fallback=cached,
                             qualification_verifier=lambda item: True)):
            result = solve_task(ambiguous, context, generation, budget)
            self.assertEqual(result.route, RouteKind.UNRESOLVED)
            self.assertEqual(sum(r.operation_count for r in result.dag_receipts), 0)


