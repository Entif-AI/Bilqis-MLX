"""Structural test shard from test_cognitive_solver.py; assertions preserved."""
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

def _fixture():
    binding, values = _case(("Number", 2), ("Number", 3))
    add = _goal(_program(DAGNode(
        "answer", "ADD", (_literal(values[0]), _literal(values[1])),
        "Number", SCOPE)), binding)
    ambiguous = _goal(_program(DAGNode(
        "answer", None, (_literal(values[0]), _literal(values[1])),
        "Number", SCOPE, candidate_operator_ids=("ADD", "SUB"))), binding)
    generation = GenerationBinding(
        generation_digest="f" * 64,
        semantic_release=RELEASE,
        source_binding_digest=contract_digest(binding),
    )
    budget = SolveBudget(DAGBudget())
    return binding, generation, budget, add, ambiguous

class CognitiveSolverTests(unittest.TestCase):
        def test_replay_record_retains_costs_and_handles_without_source_payloads(self):
            binding, generation, budget, add, _ = _fixture()
            result = solve_task(add, SolveContext(binding), generation, budget)
            record = result.replay_record()
            self.assertEqual(record["schema_version"], "bilqis.c04.solve-replay/v1")
            self.assertEqual(record["route"], "EXACT")
            self.assertEqual(record["costs"], {
                "pure_operations": 1, "reserved_operations": 0,
                "operation_limit": 64, "lookups": 1, "memo_hits": 0,
                "backbone_calls": 0, "local_refinements": 0,
                "decoder_decisions": None})
            self.assertEqual(record["task_sha256"], contract_digest(add))
            self.assertEqual(record["outcome"], {
                "type": "Number", "state": "VALUE",
                "sha256": contract_digest(result.answer)})
            self.assertEqual(record["dag_receipts"][0]["selected_bindings"],
                             (("answer", "ADD", ("literal:source:literal:0",
                                                   "literal:source:literal:1")),))
            encoded = json.dumps(record, sort_keys=True)
            self.assertNotIn('"value"', encoded)
            self.assertNotIn('"score"', encoded)
            self.assertNotIn('"gold"', encoded)
            self.assertEqual(record, result.replay_record())

        def test_replay_counts_memo_lookup_without_compute(self):
            binding, generation, budget, add, _ = _fixture()
            context = SolveContext(binding, memo=PureOperationMemo())
            solve_task(add, context, generation, budget)
            result = solve_task(add, context, generation, budget)
            costs = result.replay_record()["costs"]
            self.assertEqual(result.answer.value, 5)
            self.assertEqual((costs["pure_operations"], costs["lookups"],
                              costs["memo_hits"], costs["reserved_operations"]),
                             (0, 1, 1, 0))

        def test_replay_reserves_unknown_executor_cost_without_inventing_work(self):
            binding, generation, budget, add, ambiguous = _fixture()
            from bilqis_mlx.runtime import cognitive_solver
            execute = cognitive_solver.execute_dag
            calls = 0

            def interrupted(goal, *args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    return execute(None, *args, **kwargs)
                return execute(goal, *args, **kwargs)

            def proposal(request):
                return NeuralProposal(add, request.source_binding_digest,
                                      request.generation_digest,
                                      request.unresolved_signature, "b" * 64)

            with patch.object(cognitive_solver, "execute_dag", interrupted):
                result = solve_task(
                    ambiguous, SolveContext(binding, neural_proposer=proposal),
                    generation, budget)
            self.assertEqual(result.route, RouteKind.UNRESOLVED)
            self.assertEqual(result.replay_record()["costs"]["pure_operations"], 0)
            self.assertEqual(result.replay_record()["costs"]["reserved_operations"], 64)

        def test_solver_transitive_imports_exclude_gold_evaluator(self):
            root = Path(__file__).resolve().parents[3]
            pending = ["bilqis_mlx.runtime.cognitive_solver"]
            seen = set()
            while pending:
                name = pending.pop()
                if name in seen:
                    continue
                path = root.joinpath(*name.split(".")).with_suffix(".py")
                if not path.is_file():
                    path = root.joinpath(*name.split("."), "__init__.py")
                if not path.is_file():
                    continue
                seen.add(name)
                pending.extend(".".join(name.split(".")[:index])
                               for index in range(1, len(name.split("."))))
                package = name if path.name == "__init__.py" else name.rpartition(".")[0]
                for node in ast.walk(ast.parse(path.read_text())):
                    imports = []
                    if isinstance(node, ast.Import):
                        imports = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        base = importlib.util.resolve_name(
                            "." * node.level + (node.module or ""), package)
                        imports = [base] + [base + "." + alias.name for alias in node.names]
                    pending.extend(item for item in imports
                                   if item.startswith("bilqis_mlx."))
            self.assertIn("bilqis_mlx.semantics.cognitive_dag", seen)
            forbidden = ("bilqis_mlx.verification", "bilqis_mlx.source_adapters",
                         "bilqis_mlx.generated_assessment", "bilqis_mlx.assessment",
                         "bilqis_mlx.factory")
            self.assertEqual([name for name in seen if name.startswith(forbidden)
                              or name.endswith("_oracle")], [])

        def test_applicable_exact_operator_wins_with_full_score_no_neural(self):
            binding, generation, budget, add, _ = _fixture()
            result = solve_task(
                add, SolveContext(binding), generation, budget)
            self.assertEqual(result.route, RouteKind.EXACT)
            self.assertEqual(result.answer.value, 5)
            self.assertEqual(result.answer.type_name, "Number")
            self.assertEqual(result.score, 1.0)
            self.assertEqual(result.neural_calls, 0)


from bilqis_mlx.runtime.tests.capability.cognitive_solver_methods_part2 import CognitiveSolverTests as _SolverPart2
from bilqis_mlx.runtime.tests.capability.cognitive_solver_methods_part3 import CognitiveSolverTests as _SolverPart3

for _source in (_SolverPart2, _SolverPart3):
    for _name, _method in vars(_source).items():
        if _name.startswith("test_"):
            setattr(CognitiveSolverTests, _name, _method)
