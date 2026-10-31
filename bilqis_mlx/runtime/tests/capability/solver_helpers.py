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
