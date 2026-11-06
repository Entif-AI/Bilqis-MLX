"""Compatibility fixtures plus public cognitive-DAG import-boundary proof."""
import ast
import importlib.util
from pathlib import Path
from unittest import TestCase

from bilqis_mlx.semantics.tests._cognitive_dag_fixtures import (
    _execute, _goal, _literal, _program, _result,
)

class CognitiveDAGImportBoundaryTests(TestCase):
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
                    if node.module:
                        imports.append(base)
                    imports.extend(base + "." + alias.name for alias in node.names)
                pending.extend(
                    candidate for candidate in imports
                    if candidate.startswith("bilqis_mlx.")
                    and local_path(candidate)[0] is not None)
        self.assertIn("bilqis_mlx.semantics.cognitive_operators.registry", seen)
        self.assertIn("bilqis_mlx.semantics.cognitive_operators.authorization", seen)
        self.assertIn("bilqis_mlx.semantics.cognitive_operators.execution", seen)
        self.assertNotIn("bilqis_mlx.semantics.cognitive_operators", seen)
        forbidden = (
            "bilqis_mlx.verification", "bilqis_mlx.source_adapters",
            "bilqis_mlx.generated_assessment", "bilqis_mlx.assessment",
            "bilqis_mlx.factory", "bilqis_mlx.runtime",
        )
        self.assertFalse(
            [name for name in seen
             if name.startswith(forbidden) or name.endswith("_oracle")],
            seen)
