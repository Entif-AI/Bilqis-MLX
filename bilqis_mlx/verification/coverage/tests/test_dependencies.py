"""Source-backed, neural-inert coverage evidence for cross-grade composition."""
from dataclasses import replace
from pathlib import Path
import copy
import json
import unittest

from bilqis_mlx.curriculum_compiler import compile_ast
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.live_grade_b import draw_connectives, live_course
from bilqis_mlx.registry_ast import load_registry
from bilqis_mlx.semantic_coverage import (
    affected_typed_dependency_closure, discover_composition_obligations,
    verify_micro_composition_witnesses, audit_pinned_micro_generator)
from bilqis_mlx.errors import BilqisError, SEMANTIC_COVERAGE


from bilqis_mlx.verification.coverage.tests.fixtures import CoverageFixture, LEGACY


class SemanticCoverageDependenciesTests(CoverageFixture):
    def test_new_source_typed_primitive_and_grade_regenerate_dependents(self):
        plan = self._plan()
        self.assertEqual(affected_typed_dependency_closure(plan, ("A.MAPS",)),
                         ("A.MAPS", "B.AND", "B.IFF", "B.IMPLIES", "B.NOT",
                          "B.OR", "B.XOR"))
        new_token = replace(self.registry.tokens[0], id=222,
                            identity="fixture:cogal.operator.SYNTHETIC",
                            symbol="cogal.operator.SYNTHETIC",
                            signature="Boolean->Boolean", arity="1",
                            contract_sha256="a"*64)
        registry = replace(self.registry, tokens=(*self.registry.tokens, new_token),
                           source_sha256="b"*64)
        prototype = next(x for x in self.b_ast.nodes if x.id == "B.NOT")
        new_cap = replace(prototype, id="C.SYNTHETIC", grade="C",
                          roots=(new_token.symbol,), requires=("A.IDENTITY",))
        expanded = replace(self.b_ast, nodes=(*self.b_ast.nodes, new_cap))
        extended = discover_composition_obligations(expanded, registry)
        c_edges = [e for e in extended["obligations"] if e["consumer"] == "C.SYNTHETIC"]
        self.assertEqual(len(c_edges), 12)
        self.assertEqual({e["producer"] for e in c_edges},
                         {x.id for x in self.b_ast.nodes})
        self.assertIn("C.SYNTHETIC", affected_typed_dependency_closure(
            extended, ("A.MAPS",)))
        self.assertNotIn("C.SYNTHETIC", affected_typed_dependency_closure(
            plan, ("A.MAPS",)))

        # Meaning/signature revision automatically changes the typed edges.
        changed_token = replace(new_token, signature="Entity->Boolean",
                                contract_sha256="c"*64)
        changed_registry = replace(registry, tokens=(*self.registry.tokens, changed_token),
                                   source_sha256="d"*64)
        revised = discover_composition_obligations(expanded, changed_registry)
        self.assertFalse(any(e["consumer"] == "C.SYNTHETIC"
                             for e in revised["obligations"]))
        self.assertIn("DECLARED_PREREQUISITE_HAS_NO_TYPED_COMPOSITION",
                      {e["failure"] for e in revised["unresolved"]})
