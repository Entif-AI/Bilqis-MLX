"""Deterministic disposable DAG records, computation and verified memo witnesses."""
from bilqis_mlx.semantics.cognitive_dag import DAGNode, execute_dag
from bilqis_mlx.semantics.memo import PureOperationMemo
from bilqis_mlx.semantics.tests.test_cognitive_dag import (
    _literal, _result, _program, _goal,
)
from bilqis_mlx.semantics.tests.test_cognitive_operators import SCOPE, _case


def snapshots():
    binding, values = _case(("Number", 2), ("Number", 3), ("Number", 4))
    program = _program(
        DAGNode("mul", "MUL", (_literal(values[0]), _literal(values[1])), "Number", SCOPE),
        DAGNode("add", "ADD", (_result("mul"), _literal(values[2])), "Number", SCOPE))
    goal = _goal(program, binding)
    memo = PureOperationMemo()
    first = execute_dag(goal, binding, memo=memo)
    second = execute_dag(goal, binding, memo=memo)
    exhausted = execute_dag(goal, binding, memo=PureOperationMemo(), operation_limit=0)
    ambiguous = _program(DAGNode(
        "answer", None, (_literal(values[0]), _literal(values[1])),
        "Number", SCOPE, candidate_operator_ids=("ADD", "SUB")))
    unresolved = execute_dag(_goal(ambiguous, binding), binding)
    return dict(program=program, goal=goal, computed=first, memo_hit=second,
                exhausted=exhausted, ambiguous=unresolved)
