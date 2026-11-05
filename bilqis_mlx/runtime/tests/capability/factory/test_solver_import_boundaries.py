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

from bilqis_mlx.runtime.tests.capability.factory.solver_helpers import _fixture

class CognitiveSolverTests(unittest.TestCase):
    def test_solver_transitive_imports_exclude_gold_evaluator(self):
        root = Path(__file__).resolve().parents[5]
        pending = ["bilqis_mlx.runtime.cognitive_solver"]
        seen = set()

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
                    imports = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    base = importlib.util.resolve_name(
                        "." * node.level + (node.module or ""), package)
                    imports = ([base] if node.module else []) + [
                        base + "." + alias.name for alias in node.names]
                pending.extend(item for item in imports
                               if item.startswith("bilqis_mlx.")
                               and local_path(item)[0] is not None)
        self.assertIn("bilqis_mlx.semantics.cognitive_dag", seen)
        forbidden = ("bilqis_mlx.verification", "bilqis_mlx.source_adapters",
                     "bilqis_mlx.generated_assessment", "bilqis_mlx.assessment",
                     "bilqis_mlx.factory")
        self.assertEqual([name for name in seen if name.startswith(forbidden)
                          or name.endswith("_oracle")], [])
