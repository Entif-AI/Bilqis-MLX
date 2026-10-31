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
