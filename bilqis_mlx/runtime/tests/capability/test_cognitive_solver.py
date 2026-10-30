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
        root = Path(__file__).resolve().parents[4]
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

    def test_qualified_cached_composition_precedes_neural_and_ties_stably(self):
        binding, generation, budget, add, ambiguous = _fixture()
        cached = QualifiedComposition(
            goal=add,
            source_binding_digest=generation.source_binding_digest,
            rights_epoch=binding.frontier.rights_epoch,
            correction_generation=binding.frontier.correction_generation,
            qualification_receipt_sha256="a" * 64,
        )
        calls = []

        def neural(request):
            calls.append(request)
            raise AssertionError("exact cached route must preempt neural")

        context = SolveContext(
            binding, qualified_compositions=(cached,),
            qualification_verifier=lambda item: (
                item.qualification_receipt_sha256 == "a" * 64),
            neural_proposer=neural)
        result = solve_task(ambiguous, context, generation, budget)
        self.assertEqual(result.route, RouteKind.CACHED_COMPOSITION)
        self.assertEqual(result.answer.value, 5)
        self.assertEqual(result.score, 1.0)
        self.assertEqual(calls, [])
        rejected = solve_task(
            ambiguous, SolveContext(
                binding, qualified_compositions=(cached,),
                qualification_verifier=lambda item: False),
            generation, budget)
        self.assertEqual(rejected.route, RouteKind.UNRESOLVED)

    def test_neural_proposes_only_a_source_bound_dag_for_unresolved_part(self):
        binding, generation, budget, add, ambiguous = _fixture()
        calls = []

        def neural(request):
            calls.append(request)
            self.assertEqual(request.generation_digest,
                             generation.generation_digest)
            self.assertFalse(hasattr(request, "raw_source_values"))
            return NeuralProposal(
                add, request.source_binding_digest,
                request.generation_digest,
                request.unresolved_signature,
                "b" * 64)

        result = solve_task(
            ambiguous, SolveContext(binding, neural_proposer=neural),
            generation, budget)
        self.assertEqual(result.route, RouteKind.NEURAL_COMPOSITION)
        self.assertEqual(result.answer.value, 5)
        self.assertIsNone(result.score)
        self.assertEqual(result.neural_calls, 1)
        self.assertEqual(len(calls), 1)

    def test_neural_foreign_source_binding_rejects_before_dag_execution(self):
        binding, generation, budget, add, ambiguous = _fixture()
        foreign = replace(
            add, source_visible_bindings=tuple(sorted((
                *add.source_visible_bindings, "literal:source:foreign"))))

        def neural(request):
            return NeuralProposal(
                foreign, request.source_binding_digest,
                request.generation_digest,
                request.unresolved_signature,
                "b" * 64)

        result = solve_task(
            ambiguous, SolveContext(binding, neural_proposer=neural),
            generation, budget)
        self.assertEqual(result.route, RouteKind.UNRESOLVED)
        self.assertEqual(result.neural_calls, 1)
        self.assertEqual(result.fallback_reason,
                         "BAMF_C04_NEURAL_PROPOSAL_SCOPE_DRIFT")

    def test_invalid_neural_uses_verified_deterministic_fallback(self):
        binding, generation, budget, add, ambiguous = _fixture()
        fallback = QualifiedComposition(
            add, generation.source_binding_digest,
            binding.frontier.rights_epoch,
            binding.frontier.correction_generation,
            "a" * 64)
        result = solve_task(
            ambiguous, SolveContext(
                binding,
                qualification_verifier=lambda item: True,
                neural_proposer=lambda request: "invalid neural payload",
                deterministic_fallback=fallback),
            generation, budget)
        self.assertEqual(result.route, RouteKind.DETERMINISTIC_FALLBACK)
        self.assertEqual(result.answer.value, 5)
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.neural_calls, 1)
        self.assertEqual(result.fallback_reason,
                         "BAMF_C04_NEURAL_PROPOSAL_INVALID")

    def test_one_backbone_plus_bounded_local_refinement(self):
        binding, generation, _, add, ambiguous = _fixture()
        budget = SolveBudget(DAGBudget(), max_local_refinements=1)
        calls = []

        def refine(request, attempt):
            calls.append(attempt)
            return NeuralProposal(
                add, request.source_binding_digest,
                request.generation_digest,
                request.unresolved_signature,
                "b" * 64)

        result = solve_task(
            ambiguous, SolveContext(
                binding,
                neural_proposer=lambda request: None,
                local_refiner=refine),
            generation, budget)
        self.assertEqual(result.route, RouteKind.NEURAL_COMPOSITION)
        self.assertEqual(result.answer.value, 5)
        self.assertEqual(result.neural_calls, 1)
        self.assertEqual(result.local_refinement_calls, 1)
        self.assertEqual(calls, [1])
        replay = result.replay_record()
        self.assertEqual(replay["route"], "NEURAL_COMPOSITION")
        self.assertEqual(replay["costs"]["backbone_calls"], 1)
        self.assertEqual(replay["costs"]["local_refinements"], 1)
        self.assertEqual(replay["costs"]["pure_operations"], 1)
        self.assertIsNone(replay["costs"]["decoder_decisions"])

    def test_refinement_cannot_restart_consumed_operation_budget(self):
        binding, generation, _, add, ambiguous = _fixture()
        limit = DAGBudget(max_operations=1)
        add, ambiguous = (replace(goal, budget=limit)
                          for goal in (add, ambiguous))
        sub = replace(add, allowed_operator_ids=ambiguous.allowed_operator_ids,
                      expression_or_holes=_program(replace(
            add.expression_or_holes.nodes[0], operator_id="SUB")))

        def proposal(goal, request):
            return NeuralProposal(goal, request.source_binding_digest,
                                  request.generation_digest,
                                  request.unresolved_signature, "b" * 64)

        result = solve_task(
            ambiguous, SolveContext(
                binding, neural_proposer=lambda request: proposal(sub, request),
                local_refiner=lambda request, attempt: proposal(add, request)),
            generation, SolveBudget(limit, max_local_refinements=1))
        self.assertEqual(result.route, RouteKind.UNRESOLVED)
        self.assertEqual(sum(r.operation_count for r in result.dag_receipts), 1)

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

    def test_decoder_construction_errors_use_qualified_fallback(self):
        binding, generation, budget, add, ambiguous = _fixture()
        fallback = QualifiedComposition(
            add, generation.source_binding_digest,
            binding.frontier.rights_epoch,
            binding.frontier.correction_generation, "a" * 64)
        for malformed_digest in (False, True):
            with self.subTest(malformed_digest=malformed_digest):
                def malformed(request):
                    if malformed_digest:
                        return NeuralProposal(
                            add, request.source_binding_digest, "bad",
                            request.unresolved_signature, "b" * 64)
                    raise ValueError("malformed decoder payload")
                result = solve_task(
                    ambiguous, SolveContext(
                        binding, qualification_verifier=lambda item: True,
                        neural_proposer=malformed,
                        deterministic_fallback=fallback), generation, budget)
                self.assertEqual(result.route, RouteKind.DETERMINISTIC_FALLBACK)
                self.assertEqual(result.answer.value, 5)
                self.assertEqual(result.neural_calls, 1)

    def test_unresolved_without_neural_preserves_typed_state_and_no_score(self):
        binding, generation, budget, _, ambiguous = _fixture()
        result = solve_task(
            ambiguous, SolveContext(binding), generation, budget)
        self.assertEqual(result.route, RouteKind.UNRESOLVED)
        self.assertEqual(result.answer.state, ValueState.UNRESOLVED)
        self.assertIsNone(result.score)
        self.assertEqual(result.neural_calls, 0)


if __name__ == "__main__":
    unittest.main()
