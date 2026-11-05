"""A07.3 bounded source-qualified compositional DAG execution witnesses."""
from __future__ import annotations

from dataclasses import replace
import ast
import importlib.util
from pathlib import Path
import socket
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.cognitive_dag import (
    DAGBudget, DAGNode, DAGOperand, DAGProgram, DAGResult, RefKind,
    TaskGoal, execute_dag,
)
from bilqis_mlx.semantics.cognitive_operators import (
    Duration, SourceKind, TypedValue, ValueState,
)
from bilqis_mlx.semantics.memo import PureOperationMemo
from bilqis_mlx.semantics.tests.test_cognitive_operators import (
    RELEASE, SCOPE, _case, _grant, _with_frame, _with_unit_edge,
)
from bilqis_mlx.semantics.tests.cognitive_dag.fixtures import (
    _literal, _result, _program, _goal, _execute,
)

from bilqis_mlx.semantics.tests.cognitive_dag.test_memo import CognitiveDAGTests as _memo
from bilqis_mlx.semantics.tests.cognitive_dag.test_preparation import CognitiveDAGTests as _preparation
from bilqis_mlx.semantics.tests.cognitive_dag.test_graph import CognitiveDAGTests as _graph
from bilqis_mlx.semantics.tests.cognitive_dag.test_records import CognitiveDAGTests as _records
from bilqis_mlx.semantics.tests.cognitive_dag.test_execution import CognitiveDAGTests as _execution


class CognitiveDAGTests(_memo, _preparation, _graph, _records, _execution):
    def test_dag_transitive_runtime_imports_exclude_assessment_and_gold(self):
        root = Path(__file__).resolve().parents[3]
        seen = set()
        pending = ["bilqis_mlx.semantics.cognitive_dag"]

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
        self.assertIn("bilqis_mlx.semantics.cognitive_operators", seen)
        forbidden = (
            "bilqis_mlx.verification", "bilqis_mlx.source_adapters",
            "bilqis_mlx.generated_assessment", "bilqis_mlx.assessment",
            "bilqis_mlx.factory", "bilqis_mlx.runtime",
        )
        self.assertFalse(
            [name for name in seen
             if name.startswith(forbidden) or name.endswith("_oracle")],
            seen)


del _memo, _preparation, _graph, _records, _execution
